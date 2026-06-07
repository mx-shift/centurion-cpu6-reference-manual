#!/usr/bin/env python3
"""Bisect failing soup vectors to the first instruction where the
manual model and the microcode oracle disagree."""
import json, subprocess, sys, os
sys.path.insert(0, ".")
import model

ORACLE = os.path.expanduser("~/Projects/centurion-emu/harness/oracle-mc.js")
DENO = os.path.expanduser("~/.deno/bin/deno")
SCRATCH = os.path.expanduser("~/.cache/claude/scratch.SSAzOK/shrink")
os.makedirs(SCRATCH, exist_ok=True)

def reg_prefix(regs):
    # LDA= y; XFR A,Y; ... ; LDB= b; LDX= x; LDA= a  (mirrors kernel)
    p = []
    for val, x in ((regs["Y"], 6), (regs["Z"], 8)):
        p += [0x90, val >> 8, val & 0xFF, 0x55, x]
    p += [0xD0, regs["B"] >> 8, regs["B"] & 0xFF]
    p += [0x60, regs["X"] >> 8, regs["X"] & 0xFF]
    p += [0x90, regs["A"] >> 8, regs["A"] & 0xFF]
    return p

def run_oracle(code, mem, n):
    img = bytearray(0x200)
    body = bytes(code)
    img[:len(body)] = body
    # window copy at 0x1100 (MEMW remapped: patch code? we instead
    # relocate window accesses: soup uses MEMW=0x6000; oracle image is
    # small but bpl memory is full -- just POKE via a loader prefix?
    # Easier: write mem bytes into the image is impossible (0x6000).
    # Use driver's binary at 0x1000 and a second file? oracle-mc loads
    # one image; so prepend stores: LDAB= b; STAB/ addr  per byte.
    raise SystemExit("unused")

def main():
    fails = []
    for l in open("report.jsonl"):
        r = json.loads(l)
        if r["verdict"] == "fail" and r["name"].startswith("soup"):
            fails.append(r)
    print(len(fails), "failing soup vectors")
    firsts = {}
    import gen, kernel
    img, labels = kernel.build()
    cap = labels["CAPTURE"]
    vecs = {v.name: v for v in gen.tier9(cap)}
    for r in fails:
        vec = vecs[r["name"]]
        code = list(vec.code[:-3])  # strip JMP capture
        # build full program: mem pokes + reg prefix + code + HLT
        pokes = []
        for i, b in enumerate(vec.mem):
            a = vec.mem_addr + i
            pokes += [0x80, b, 0xA1, a >> 8, a & 0xFF]
        prog = pokes + reg_prefix(vec.regs) + code + [0x00]
        binp = f"{SCRATCH}/t.bin"
        open(binp, "wb").write(bytes(prog))
        out = subprocess.run(
            [DENO, "run", "--allow-read", ORACLE, binp, "1000", "1000", "400"],
            capture_output=True, text=True, timeout=120,
            cwd=os.path.dirname(ORACLE))
        rows = [json.loads(l) for l in out.stdout.splitlines() if l.startswith("{")]
        # model: execute the same full program
        m = model.Machine()
        for i, b in enumerate(bytes(prog)):
            m.mem[0x1000 + i] = b
        m.pc = 0x1000
        # lockstep: oracle rows are per-instruction "before" states
        diverged = None
        for i, row in enumerate(rows):
            mf = (m.f["V"] << 7) | (m.f["M"] << 6) | (m.f["F"] << 5) | (m.f["L"] << 4)
            ok = (row["pc"] == m.pc and row["a"] == m.r["A"] and row["b"] == m.r["B"]
                  and row["x"] == m.r["X"] and row["y"] == m.r["Y"]
                  and row["z"] == m.r["Z"] and (row["cc"] & 0xF0) == mf)
            if not ok:
                prev_op = rows[i - 1]["op"] if i else None
                diverged = (prev_op, row, m.pc, dict(m.r), mf)
                break
            if row["op"] == 0x00:
                break
            try:
                m.step()
            except model.Trap as e:
                diverged = (row["op"], f"model trap {e}", None, None, None)
                break
        if diverged:
            prev_op = diverged[0]
            key = f"{prev_op:02x}" if isinstance(prev_op, int) else str(prev_op)
            firsts.setdefault(key, []).append((r["name"], diverged))
    for k, items in sorted(firsts.items()):
        name, d = items[0]
        print(f"op {k}: {len(items)} vectors, e.g. {name}")
        if isinstance(d[1], dict):
            row = d[1]
            print(f"   oracle pc={row['pc']:04x} a={row['a']:04x} b={row['b']:04x} y={row['y']:04x} cc={row['cc']:02x}")
            print(f"   model  pc={d[2]:04x} a={d[3]['A']:04x} b={d[3]['B']:04x} y={d[3]['Y']:04x} cc={d[4]:02x}")

main()
