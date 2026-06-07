"""Test-vector generation.

Vectors are derived from the manual's opcode index and addressing
grammar, with boundary-value operands. Each vector is a small code
snippet plus initial registers and a memory window; expectations come
from model.py at run time, so a vector is "what to run", never "what
should happen".

Tiers:
  0 smoke     — the kernel's own instruction subset, simple values
                (validates the harness before anything else)
  1 core      — loads/stores in every mode, branches, XFR/transfers
  2 alu       — byte/word ALU, inc/dec, clear/invert, shifts/rotates
  3 muldiv    — MUL/DIV register forms
  4 big       — BIG multi-byte ops including divide-with-remainder
  5 stack     — JSR/RSR/STK/POP
"""

import random

import model

MEMW = 0x6000  # test memory window
CAPTURE = None  # filled by run.py from the kernel labels

BYTES = [0x00, 0x01, 0x0F, 0x7F, 0x80, 0xFF, 0x55]
WORDS = [0x0000, 0x0001, 0x7FFF, 0x8000, 0xFFFF, 0x1234, 0x00FF]


class Vector:
    def __init__(self, name, code, regs=None, mem=b"\x00", mem_addr=MEMW):
        self.name = name
        self.code = bytes(code)
        self.regs = {"A": 0, "B": 0, "X": 0, "Y": 0, "Z": 0, "S": 0x5E00}
        if regs:
            self.regs.update(regs)
        self.mem = bytes(mem)
        self.mem_addr = mem_addr


def _jmp_capture(capture):
    return bytes([0x71, capture >> 8, capture & 0xFF])


def tier0(capture):
    """Kernel-trust set: every instruction the kernel itself relies
    on, with hand-picked values. If these fail, nothing else means
    anything."""
    v = []
    jc = _jmp_capture(capture)
    v.append(Vector("smoke.nop", [0x01] + list(jc)))
    v.append(Vector("smoke.ldab_imm", [0x80, 0x5A] + list(jc)))
    v.append(Vector("smoke.lda_imm", [0x90, 0x12, 0x34] + list(jc)))
    v.append(
        Vector(
            "smoke.stab_dir",
            [0x80, 0xA5, 0xA1, MEMW >> 8, MEMW & 0xFF] + list(jc),
            mem=b"\x00\x00",
        )
    )
    v.append(
        Vector(
            "smoke.ldab_dir",
            [0x81, MEMW >> 8, MEMW & 0xFF] + list(jc),
            mem=b"\xc3\x00",
        )
    )
    v.append(Vector("smoke.xfr_ab", [0x55, 0x02] + list(jc), regs={"A": 0xBEEF}))
    v.append(Vector("smoke.subb_eq", [0xC0, 0x3A, 0x41, 0x13] + list(jc), regs={"A": 0x003A}))
    v.append(Vector("smoke.srrb", [0x80, 0x81, 0x24, 0x10] + list(jc)))
    v.append(Vector("smoke.branch_bz", [0x90, 0x00, 0x00, 0x14, 0x02, 0x80, 0x01, 0x80, 0x02] + list(jc)))
    v.append(Vector("smoke.inr_x", [0x30, 0x40] + list(jc), regs={"X": 0x00FF}))
    return v


def tier1(capture):
    v = []
    jc = list(_jmp_capture(capture))
    rows = {
        "ldab": 0x80,
        "lda": 0x90,
        "ldbb": 0xC0,
        "ldb": 0xD0,
        "ldx": 0x60,
        "stab": 0xA0,
        "sta": 0xB0,
        "stbb": 0xE0,
        "stb": 0xF0,
        "stx": 0x68,
    }
    wide = {"lda", "ldb", "ldx", "sta", "stb", "stx"}
    for name, row in rows.items():
        w = name in wide
        load = name.startswith("ld")
        if load:
            # immediate
            if w:
                for x in WORDS[:4]:
                    v.append(Vector(f"{name}.imm.{x:04x}", [row, x >> 8, x & 0xFF] + jc))
            else:
                for x in BYTES[:4]:
                    v.append(Vector(f"{name}.imm.{x:02x}", [row, x] + jc))
        # direct
        mem = bytes([0x12, 0x34])
        v.append(
            Vector(
                f"{name}.dir",
                [row + 1, MEMW >> 8, MEMW & 0xFF] + jc,
                regs={"A": 0xA1A2, "B": 0xB1B2, "X": 0xC1C2},
                mem=mem,
            )
        )
        # indirect: pointer at MEMW -> MEMW+4
        v.append(
            Vector(
                f"{name}.ind",
                [row + 2, MEMW >> 8, MEMW & 0xFF] + jc,
                regs={"A": 0xA1A2, "B": 0xB1B2, "X": 0xC1C2},
                mem=bytes([(MEMW + 4) >> 8, (MEMW + 4) & 0xFF, 0, 0, 0x77, 0x88]),
            )
        )
        # indexed via Y, plain / post-inc / pre-dec / displaced
        for sub, mb, extra in (
            ("idx", [0x60], []),
            ("idxpi", [0x61], []),
            ("idxpd", [0x62], []),
            ("idxd", [0x68], [0x02]),
        ):
            v.append(
                Vector(
                    f"{name}.{sub}",
                    [row + 5] + mb + extra + jc,
                    regs={"A": 0xA1A2, "B": 0xB1B2, "X": 0xC1C2, "Y": MEMW + 2},
                    mem=bytes([0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6]),
                )
            )
        # one-byte register-pointer form (via Y = row+8+3)
        v.append(
            Vector(
                f"{name}.viaY",
                [row + 8 + 3] + jc,
                regs={"A": 0xA1A2, "B": 0xB1B2, "X": 0xC1C2, "Y": MEMW},
                mem=bytes([0x9A, 0x9B]),
            )
        )
    # branches: each taken and not taken, distinguishing by a marker
    for opb, fl, val in (
        (0x10, "L", 1),
        (0x11, "L", 0),
        (0x12, "F", 1),
        (0x13, "F", 0),
        (0x14, "V", 1),
        (0x15, "V", 0),
        (0x16, "M", 1),
        (0x17, "M", 0),
    ):
        # Flag prelude: SLRB on a chosen value sets L; LDAB sets M/V;
        # INRB overflow sets F. The generator only needs *some* state;
        # the model computes what the prelude actually produces.
        for prelude, tag in (
            ([0x80, 0x00], "z"),  # A=0: V=1 M=0
            ([0x80, 0x80], "m"),  # M=1 V=0
            ([0x80, 0xFF, 0x25, 0x10], "l"),  # SLRB AL,1: L=1 (bit7 out)
            ([0x80, 0x7F, 0x20, 0x10], "f"),  # INRB AL,1: 7F+1 overflow F=1
        ):
            code = prelude + [opb, 0x05, 0x80, 0x11, 0x71, 0, 0, 0x80, 0x22]
            vec = Vector(f"bcc.{opb:02x}.{tag}", code + jc)
            # fix the inline JMP target to skip to capture-join
            base = model.SLOT + len(prelude)
            join = base + 2 + 2 + 3 + 2  # after the second LDAB
            code[len(prelude) + 5] = join >> 8
            code[len(prelude) + 6] = join & 0xFF
            vec.code = bytes(code + jc)
            v.append(vec)
    return v


def tier2(capture, seed=1):
    rng = random.Random(seed)
    v = []
    jc = list(_jmp_capture(capture))
    # byte rr ALU: every op x register pair (AL,BL) over boundary bytes
    for opb, name in ((0x40, "addb"), (0x41, "subb"), (0x42, "andb"), (0x43, "orib"), (0x44, "oreb"), (0x45, "xfrb")):
        for a in BYTES:
            for b in BYTES[:5]:
                v.append(
                    Vector(
                        f"{name}.{a:02x}.{b:02x}",
                        [0x80, a, 0xC0, b, opb, 0x31] + jc,  # src=BL dst=AL
                    )
                )
    # word rr ALU over boundary words (registers preloaded)
    for opw, name in ((0x50, "add"), (0x51, "sub"), (0x52, "and"), (0x53, "ori"), (0x54, "ore"), (0x55, "xfr")):
        for a in WORDS:
            for b in WORDS[:5]:
                v.append(
                    Vector(
                        f"{name}.{a:04x}.{b:04x}",
                        [opw, 0x20] + jc,  # src=B dst=A
                        regs={"A": b, "B": a},
                    )
                )
        # immediate and direct sub-modes
        v.append(Vector(f"{name}.imm", [opw, 0x10, 0x12, 0x34] + jc, regs={"A": 0x0FF0}))
        v.append(
            Vector(
                f"{name}.dir",
                [opw, 0x01, MEMW >> 8, MEMW & 0xFF] + jc,
                regs={"A": 0x0FF0},
                mem=b"\x43\x21",
            )
        )
    # rc rows: inc/dec/clear/invert/shift/rotate, byte and word
    for opb in range(0x20, 0x28):
        for reg in (1, 3):  # AL, BL
            for n in (1, 2, 8, 16):
                for x in BYTES[:5]:
                    code = [0x80 if reg == 1 else 0xC0, x, opb, (reg << 4) | (n - 1)] + jc
                    v.append(Vector(f"rcb.{opb:02x}.r{reg}.n{n}.{x:02x}", code))
    for opw in range(0x30, 0x38):
        for n in (1, 2, 16):
            for x in WORDS[:5]:
                v.append(
                    Vector(
                        f"rcw.{opw:02x}.n{n}.{x:04x}",
                        [opw, (0 << 4) | (n - 1)] + jc,  # on A
                        regs={"A": x},
                    )
                )
    # one-byte aliases
    for opc in (0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F):
        for x in (0x0000, 0x7FFF, 0x8000, 0xFFFF, rng.randrange(0x10000)):
            v.append(Vector(f"alias.{opc:02x}.{x:04x}", [opc] + jc, regs={"A": x, "X": x}))
    return v


def tier3(capture):
    v = []
    jc = list(_jmp_capture(capture))
    cases = [(3, 5), (0x100, 0x100), (0xFFFF, 2), (0x7FFF, 0x7FFF), (0, 5), (5, 0), (1000, 14)]
    for a, b in cases:
        # MUL src=B dst=A (pair leader: result in A:B)
        v.append(Vector(f"mul.A.{a:04x}x{b:04x}", [0x77, 0x20] + jc, regs={"A": b, "B": a}))
        # MUL dst=B (follower only)
        v.append(Vector(f"mul.B.{a:04x}x{b:04x}", [0x77, 0x02] + jc, regs={"B": b, "A": a}))
        # DIV leader A by X: quotient -> B, remainder -> A
        v.append(
            Vector(
                f"div.{a:04x}div{b:04x}",
                [0x78, 0x40] + jc,
                regs={"A": a, "B": 0xBBBB, "X": b},
            )
        )
        # DIV follower-only dst: quotient replaces B
        v.append(
            Vector(
                f"div.B.{a:04x}div{b:04x}",
                [0x78, 0x42] + jc,
                regs={"A": 0xAAAA, "B": a, "X": b},
            )
        )
    return v


def tier4(capture):
    v = []
    jc = list(_jmp_capture(capture))
    # BIG ZAD/ZSU/A/S/C with inline literal -> window
    for sub, name in ((0, "add"), (1, "sub"), (2, "cmp"), (3, "zad"), (4, "zsu")):
        sel = (sub << 4) | (3 << 2) | 0
        for lit in (0x00, 0x01, 0x7F, 0xFF):
            v.append(
                Vector(
                    f"big.{name}.{lit:02x}",
                    [0x46, 0x02, sel, lit, MEMW >> 8, MEMW & 0xFF] + jc,
                    mem=bytes([0x00, 0x00, 0x0E, 0xAA]),
                )
            )
    # divide-with-remainder: the DRM remainder-to-[A] rule (B2.36)
    for d, s in ((14, 14), (1000, 14), (16, 14), (0x123456, 0x11)):
        memv = bytes([(d >> 16) & 0xFF, (d >> 8) & 0xFF, d & 0xFF, 0xAA])
        sel = (7 << 4) | (3 << 2) | 0
        v.append(
            Vector(
                f"big.drm.{d}div{s}",
                [0x46, 0x02, sel, s, MEMW >> 8, MEMW & 0xFF] + jc,
                regs={"A": MEMW + 3},
                mem=memv,
            )
        )
    return v


def tier5(capture):
    v = []
    jc = list(_jmp_capture(capture))
    stk = 0x6100
    # JSR/RSR round trip: call a routine that loads a marker
    code = [
        0x79,
        0,
        0,  # JSR sub (fixed below)
        0x80,
        0x22,  # LDAB= 22 after return
    ]
    base = model.SLOT
    sub = base + len(code) + len(jc)
    code[1], code[2] = sub >> 8, sub & 0xFF
    full = code + jc + [0x80, 0x11, 0x09]  # sub: LDAB= 11; RSR
    v.append(Vector("stack.jsr_rsr", full, regs={"S": stk}))
    # STK/POP round trip of A..B (4 bytes)
    v.append(
        Vector(
            "stack.stk_pop",
            [0x7E, 0x03, 0x90, 0x00, 0x00, 0xD0, 0x00, 0x00, 0x7F, 0x03] + jc,
            regs={"A": 0x1122, "B": 0x3344, "S": stk},
        )
    )
    v.append(Vector("stack.stk_only", [0x7E, 0x03] + jc, regs={"A": 0xAB12, "B": 0xCD34, "S": stk}))
    return v


TIERS = {0: tier0, 1: tier1, 2: tier2, 3: tier3, 4: tier4, 5: tier5}


def generate(tiers, capture):
    out = []
    for t in tiers:
        out.extend(TIERS[t](capture))
    return out
