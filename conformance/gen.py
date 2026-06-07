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
        # one-byte register-pointer form (via Y = row+8+3); the X rows
        # have no such forms (0x60-0x65 / 0x68-0x6D only)
        if name not in ("ldx", "stx"):
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


# ---------------------------------------------------------------------
# Extended tiers.
# ---------------------------------------------------------------------
def tier1x(capture):
    """Addressing-mode completion: relative, relative-indirect,
    indexed-indirect and combos, plus all one-byte register-pointer
    rows."""
    v = []
    jc = list(_jmp_capture(capture))
    # relative (mode 3) and relative-indirect (mode 4) loads: the
    # operand lives inside the code snippet itself.
    # LDAB rel: 83 <disp>; data byte follows the JMP.
    code = [0x83, 0x03] + jc + [0xC9]  # disp 3 -> the 0xC9 after JMP
    v.append(Vector("ldab.rel", code))
    code = [0x93, 0x03] + jc + [0xAB, 0xCD]
    v.append(Vector("lda.rel", code))
    # relative-indirect: pointer after the JMP -> window
    code = [0x84, 0x03] + jc + [MEMW >> 8, MEMW & 0xFF]
    v.append(Vector("ldab.relind", code, mem=b"\x5e\x00"))
    code = [0x94, 0x03] + jc + [MEMW >> 8, MEMW & 0xFF]
    v.append(Vector("lda.relind", code, mem=b"\x5e\x77"))
    # store relative: STAB rel over the trailing data byte
    code = [0x80, 0x42, 0xA3, 0x03] + jc + [0x00]
    v.append(Vector("stab.rel", code))
    # indexed-indirect (+*Y): pointer at [Y] -> window+2
    for row, name, w in ((0x85, "ldab", 0), (0x95, "lda", 1), (0xA5, "stab", 0), (0xB5, "sta", 1)):
        v.append(
            Vector(
                f"{name}.idxind",
                [row, 0x64] + jc,
                regs={"A": 0xA1A2, "Y": MEMW},
                mem=bytes([(MEMW + 2) >> 8, (MEMW + 2) & 0xFF, 0x35, 0x36]),
            )
        )
        # indirect + post-increment (steps by word size)
        v.append(
            Vector(
                f"{name}.idxindpi",
                [row, 0x65] + jc,
                regs={"A": 0xA1A2, "Y": MEMW},
                mem=bytes([(MEMW + 2) >> 8, (MEMW + 2) & 0xFF, 0x37, 0x38]),
            )
        )
        # indirect + displacement
        v.append(
            Vector(
                f"{name}.idxindd",
                [row, 0x6C, 0x02] + jc,
                regs={"A": 0xA1A2, "Y": MEMW - 2},
                mem=bytes([(MEMW + 2) >> 8, (MEMW + 2) & 0xFF, 0x39, 0x3A]),
            )
        )
    # one-byte register-pointer rows via every register
    for row, name in ((0x88, "ldab"), (0x98, "lda"), (0xA8, "stab"), (0xB8, "sta"), (0xC8, "ldbb"), (0xD8, "ldb"), (0xE8, "stbb"), (0xF8, "stb")):
        for rno, rname in ((0, "A"), (1, "B"), (2, "X"), (3, "Y"), (4, "Z")):
            regs = {"A": 0xA1A2, "B": 0xB1B2, "X": 0xC1C2, "Y": 0xD1D2, "Z": 0xE1E2}
            regs[rname] = MEMW
            v.append(
                Vector(
                    f"{name}.via{rname}",
                    [row + rno] + jc,
                    regs=regs,
                    mem=bytes([0x9C, 0x9D]),
                )
            )
    # JMP modes: direct / indirect / relative / rel-indirect / indexed,
    # distinguished by which marker the landing code loads.
    tgt = model.SLOT + 0x20
    for sub, code in (
        ("dir", [0x71, tgt >> 8, tgt & 0xFF]),
        ("ind", [0x72, MEMW >> 8, MEMW & 0xFF]),
        ("rel", [0x73, 0x20 - 3]),
        ("idx", [0x75, 0x60]),
    ):
        pad = [0x01] * (0x20 - len(code))
        full = code + pad + [0x80, 0x77] + jc
        v.append(
            Vector(
                f"jmp.{sub}",
                full,
                regs={"Y": tgt},
                mem=bytes([tgt >> 8, tgt & 0xFF]),
            )
        )
    return v


def tier2x(capture):
    """ALU completion: more register pairs, word ops with Y/Z/S,
    rc-row memory forms, the 0x58-0x5F aliases, flag ops, PCX,
    STR forms, LST/SST, word-ALU sub-modes."""
    v = []
    jc = list(_jmp_capture(capture))
    # byte rr across distinct pairs including upper halves + same-reg
    pairs = [(1, 3), (3, 1), (0, 1), (2, 5), (7, 9), (1, 1), (4, 6)]
    for opb, name in ((0x40, "addb"), (0x41, "subb"), (0x42, "andb"), (0x45, "xfrb")):
        for s, d in pairs:
            v.append(
                Vector(
                    f"{name}.r{s}r{d}",
                    [opb, (s << 4) | d] + jc,
                    regs={"A": 0x7FF1, "B": 0x80E2, "X": 0x01C3, "Y": 0xFFD4, "Z": 0x55A5},
                )
            )
    # word rr with Y/Z/S operands (S as dst exercises stack-swap path)
    for opw, name in ((0x50, "add"), (0x51, "sub"), (0x55, "xfr")):
        for s, d in ((6, 8), (8, 6), (0, 10), (10, 0), (6, 6)):
            v.append(
                Vector(
                    f"{name}.w{s}w{d}",
                    [opw, (s << 4) | d] + jc,
                    regs={"A": 0x8001, "Y": 0x7FFF, "Z": 0x0101, "S": 0x5E00},
                )
            )
    # word-ALU indexed sub-mode: ADD -B,2,A
    v.append(
        Vector(
            "add.idx",
            [0x50, 0x31, 0x00, 0x02] + jc,
            regs={"A": 0x0011, "B": MEMW},
            mem=bytes([0, 0, 0x12, 0x34]),
        )
    )
    # rc rows on more registers + memory forms
    for opw in range(0x30, 0x38):
        v.append(
            Vector(
                f"rcw.{opw:02x}.regB",
                [opw, 0x21] if False else [opw, 0x20] + jc,
                regs={"B": 0x8001},
            )
        )
        # direct memory form (odd nibble 1)
        v.append(
            Vector(
                f"rcw.{opw:02x}.dir",
                [opw, 0x10 | 0x01, MEMW >> 8, MEMW & 0xFF] + jc,
                mem=bytes([0x7F, 0xFF, 0xAA]),
            )
        )
        # indexed memory form (nibble 3 = B + disp16)
        v.append(
            Vector(
                f"rcw.{opw:02x}.idx",
                [opw, 0x30 | 0x01, 0x00, 0x01] + jc,
                regs={"B": MEMW},
                mem=bytes([0xEE, 0x80, 0x01, 0xBB]),
            )
        )
    # one-byte word aliases
    for opc, name in ((0x58, "aab"), (0x59, "sab"), (0x5A, "nab"), (0x5B, "xax"), (0x5C, "xay"), (0x5D, "xab"), (0x5E, "xaz"), (0x5F, "xas")):
        for a, b in ((0x8001, 0x8001), (0x0000, 0xFFFF), (0x7FFF, 0x0001)):
            v.append(Vector(f"alias.{name}.{a:04x}", [opc] + jc, regs={"A": a, "B": b, "S": 0x5E00}))
    # flag ops & PCX
    for opc, name in ((0x02, "sf"), (0x03, "rf"), (0x06, "sl"), (0x07, "rl"), (0x08, "cl"), (0x0C, "syn"), (0x0D, "pcx"), (0x0E, "dly")):
        v.append(Vector(f"ctrl.{name}", [opc] + jc))
        v.append(Vector(f"ctrl.{name}.2", [0x06, opc] + jc))  # with L set first
    # STR forms
    v.append(Vector("str.rr", [0xD6, 0x20] + jc, regs={"A": 0x1234}))  # B -> ?? dst hi
    v.append(Vector("str.dir", [0xD6, 0x01, MEMW >> 8, MEMW & 0xFF] + jc, regs={"A": 0xBEE5}, mem=b"\x00\x00"))
    v.append(Vector("str.imm", [0xD6, 0x10, 0x00, 0x00] + jc, regs={"A": 0xFACE}))
    v.append(Vector("str.idx", [0xD6, 0x21, 0x00, 0x02] + jc, regs={"B": MEMW, "X": 0xC0DE}, mem=b"\x00\x00\x00\x00"))
    # LST/SST
    v.append(Vector("sst.dir", [0x06, 0x02, 0x6F, MEMW >> 8, MEMW & 0xFF] + jc, mem=b"\x00\x00"))
    v.append(Vector("lst.dir", [0x6E, MEMW >> 8, MEMW & 0xFF] + jc, mem=b"\xa0\x00"))
    v.append(Vector("lst.dir.f", [0x6E, MEMW >> 8, MEMW & 0xFF] + jc, mem=b"\xf0\x00"))
    # SAR/LAR within the modeled bank
    v.append(Vector("sar.b", [0xD7, 0x02] + jc, regs={"A": 0x4455, "B": 0x0000}))
    v.append(Vector("lar.b", [0xE6, 0x02] + jc, regs={"A": 0x0000, "B": 0x6677}))
    return v


def tier6(capture):
    """MEM block operations."""
    v = []
    jc = list(_jmp_capture(capture))
    src, dst = MEMW, MEMW + 8

    def both(name, code, mem, regs=None):
        v.append(Vector(name, code + jc, regs=regs, mem=mem))

    # FIL: literal fill (spec src=3, dst=0), 4 bytes
    both("mem.fil.lit", [0x47, 0x9C, 0x03, 0xEE, dst >> 8, dst & 0xFF],
         bytes(16))
    # MVF: absolute -> absolute
    both("mem.mvf.abs", [0x47, 0x40, 0x03, src >> 8, src & 0xFF, dst >> 8, dst & 0xFF],
         bytes([1, 2, 3, 4, 0, 0, 0, 0]) + bytes(8))
    # MVF: literal -> absolute
    both("mem.mvf.lit", [0x47, 0x4C, 0x02, 0xDE, 0xAD, 0xBF, dst >> 8, dst & 0xFF],
         bytes(16))
    # MVF: register-indirect both (shared byte: src=Y dst=Z)
    both("mem.mvf.reg", [0x47, 0x4A, 0x03, 0x68],
         bytes([9, 8, 7, 6, 0, 0, 0, 0]) + bytes(8),
         regs={"Y": src, "Z": dst})
    # ANC/ORC/XRC absolute
    for sub, name in ((5, "anc"), (6, "orc"), (7, "xrc")):
        both(f"mem.{name}", [0x47, (sub << 4) | 0x00, 0x03, src >> 8, src & 0xFF, dst >> 8, dst & 0xFF],
             bytes([0xF0, 0x0F, 0xAA, 0x00, 0, 0, 0, 0, 0x33, 0x33, 0xFF, 0x00]) + bytes(4))
    # CPF equal / less / greater
    for tag, a, b in (("eq", 5, 5), ("lt", 4, 9), ("gt", 9, 4)):
        both(f"mem.cpf.{tag}",
             [0x47, 0x80, 0x01, src >> 8, src & 0xFF, dst >> 8, dst & 0xFF],
             bytes([a, a, 0, 0, 0, 0, 0, 0, b, b]) + bytes(6))
    # MVV with and without match
    both("mem.mvv.hit", [0x47, 0x20, 0x05, 0x03, src >> 8, src & 0xFF, dst >> 8, dst & 0xFF],
         bytes([1, 2, 3, 4, 5, 6, 0, 0]) + bytes(8))
    both("mem.mvv.miss", [0x47, 0x20, 0x03, 0x77, src >> 8, src & 0xFF, dst >> 8, dst & 0xFF],
         bytes([1, 2, 3, 4, 0, 0, 0, 0]) + bytes(8))
    # 0x67 row: length from AL (regs A low byte = 2 -> 3 bytes)
    both("mem.mvf.al", [0x67, 0x40, src >> 8, src & 0xFF, dst >> 8, dst & 0xFF],
         bytes([0xCA, 0xFE, 0x42, 0, 0, 0, 0, 0]) + bytes(8),
         regs={"A": 0x0002})
    # MVL
    both("mvl", [0xF7], bytes([0xDE, 0xAD, 0xBE, 0xEF, 0, 0, 0, 0]) + bytes(8),
         regs={"A": 3, "B": src, "Y": dst})
    return v


def tier7(capture):
    """BIG completion: CTB/CFB, register-pointer and based specs,
    multiply, wider DRM."""
    v = []
    jc = list(_jmp_capture(capture))
    # CTB: "00123" decimal in window -> 2 binary bytes at window+8
    mem = b"\xb0\xb0\xb1\xb2\xb3\x00\x00\x00" + bytes(8)
    v.append(
        Vector(
            "big.ctb.123",
            [0x46, 0x81, 0x80, MEMW >> 8, MEMW & 0xFF, (MEMW + 8) >> 8, (MEMW + 8) & 0xFF] + jc,
            regs={"A": 0x0005},
            mem=mem,
        )
    )
    # CTB zero digits
    v.append(
        Vector(
            "big.ctb.zero",
            [0x46, 0x81, 0x80, MEMW >> 8, MEMW & 0xFF, (MEMW + 8) >> 8, (MEMW + 8) & 0xFF] + jc,
            regs={"A": 0x0000},
            mem=bytes(16),
        )
    )
    # CFB: value 1000 over template [C0 C0 C0 C0 A3 C0], pad A0
    mem = bytes([0xC0, 0xC0, 0xC0, 0xC0, 0xA3, 0xC0, 0, 0, 0x03, 0xE8]) + bytes(6)
    v.append(
        Vector(
            "big.cfb.1000",
            [0x46, 0x81, 0x90, MEMW >> 8, MEMW & 0xFF, (MEMW + 8) >> 8, (MEMW + 8) & 0xFF] + jc,
            regs={"A": 0x0006, "B": 0x00A0},
            mem=mem,
        )
    )
    # CFB: value 0 (all zero-fill / pad behavior)
    v.append(
        Vector(
            "big.cfb.zero",
            [0x46, 0x81, 0x90, MEMW >> 8, MEMW & 0xFF, (MEMW + 8) >> 8, (MEMW + 8) & 0xFF] + jc,
            regs={"A": 0x0006, "B": 0x00A0},
            mem=bytes([0xC0, 0xC0, 0xC0, 0xC0, 0xA3, 0xC0, 0, 0, 0x00, 0x00]) + bytes(6),
        )
    )
    # BIG with register-pointer specs (spec 2 both, shared byte Y/Z)
    v.append(
        Vector(
            "big.zad.regptr",
            [0x46, 0x12, 0x3A, 0x68] + jc,
            regs={"Y": MEMW, "Z": MEMW + 8},
            mem=bytes([0x12, 0x34, 0, 0, 0, 0, 0, 0]) + bytes(8),
        )
    )
    # BIG based spec (spec 1): src = B + disp8
    v.append(
        Vector(
            "big.zad.based",
            [0x46, 0x12, 0x34, 0x20, 0x02, (MEMW + 8) >> 8, (MEMW + 8) & 0xFF] + jc,
            regs={"B": MEMW},
            mem=bytes([0, 0, 0x56, 0x78, 0, 0, 0, 0]) + bytes(8),
        )
    )
    # BIG multiply
    v.append(
        Vector(
            "big.mul",
            [0x46, 0x03, 0x5C, 0x07, MEMW >> 8, MEMW & 0xFF] + jc,
            mem=bytes([0x00, 0x00, 0x00, 0x64]) + bytes(4),
        )
    )
    # DRM remainder lengths > 1
    v.append(
        Vector(
            "big.drm.wide",
            [0x46, 0x13, 0x7C, 0x00, 0x64, MEMW >> 8, MEMW & 0xFF] + jc,
            regs={"A": MEMW + 8},
            mem=bytes([0x00, 0x01, 0x86, 0xA5]) + bytes(12),
        )
    )
    return v


def tier8(capture):
    """SVC/RSV round trip: the supervisor entry at 0x0100 is planted
    through the memory window; the handler bumps B and returns with
    RSV."""
    v = []
    jc = list(_jmp_capture(capture))
    # One window at 0x0100 holds the supervisor entry (INR B,1; RSV)
    # AND the stack top, so the SVC frame lands inside the readback:
    # S = 0x0110, frame pushed at 0x010B-0x010F.
    handler = bytes([0x30, 0x20, 0x0F]) + bytes(13)
    for tag, regs in (
        ("roundtrip", {"S": 0x0110, "B": 0x0010, "X": 0x1111}),
        ("frame", {"S": 0x0110, "B": 0x8000, "X": 0xCAFE}),
    ):
        v.append(
            Vector(
                f"svc.{tag}",
                [0x66, 0x42] + jc,
                regs=regs,
                mem_addr=0x0100,
                mem=handler,
            )
        )
    return v


TIERS.update({6: tier6, 7: tier7, 8: tier8, 11: tier1x, 12: tier2x})


def tier9(capture, seed=0xCE6, n=400):
    """Soup: seeded random straight-line compositions of safe ops.
    Catches flag/register interactions between instructions that the
    single-op vectors cannot."""
    rng = random.Random(seed)
    v = []
    jc = list(_jmp_capture(capture))
    REGS = [0, 2, 4, 6, 8]  # word regs A B X Y Z (S left alone)
    BREGS = list(range(10))

    def rnd_op(out):
        k = rng.randrange(12)
        if k == 0:  # byte rr ALU
            out += [rng.choice([0x40, 0x41, 0x42, 0x43, 0x44, 0x45]),
                    (rng.choice(BREGS) << 4) | rng.choice(BREGS)]
        elif k == 1:  # word rr ALU
            out += [rng.choice([0x50, 0x51, 0x52, 0x53, 0x54, 0x55]),
                    (rng.choice(REGS) << 4) | rng.choice(REGS)]
        elif k == 2:  # rc byte
            out += [rng.randrange(0x20, 0x28),
                    (rng.choice(BREGS) << 4) | rng.randrange(16)]
        elif k == 3:  # rc word (register form)
            out += [rng.randrange(0x30, 0x38),
                    (rng.choice(REGS) << 4) | rng.randrange(16)]
        elif k == 4:  # load imm
            r = rng.choice([0x80, 0xC0])
            out += [r, rng.randrange(256)]
        elif k == 5:
            r = rng.choice([0x90, 0xD0, 0x60])
            out += [r, rng.randrange(256), rng.randrange(256)]
        elif k == 6:  # load/store window direct
            r = rng.choice([0x81, 0x91, 0xA1, 0xB1, 0xC1, 0xD1, 0xE1, 0xF1])
            a = MEMW + rng.randrange(14)
            out += [r, a >> 8, a & 0xFF]
        elif k == 7:  # one-byte aliases
            out += [rng.choice([0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D,
                                0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F,
                                0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F,
                                0x58, 0x59, 0x5A, 0x5B, 0x5C, 0x5D, 0x5E])]
        elif k == 8:  # flag ops
            out += [rng.choice([0x02, 0x03, 0x06, 0x07, 0x08])]
        elif k == 9:  # MUL/DIV rr
            out += [rng.choice([0x77, 0x78]),
                    (rng.choice(REGS) << 4) | rng.choice(REGS)]
        elif k == 10:  # forward branch over one NOP
            out += [rng.randrange(0x10, 0x1A), 0x01, 0x01]
        else:  # XFR / STR rr
            out += [rng.choice([0x55, 0xD6]),
                    (rng.choice(REGS) << 4) | rng.choice(REGS)]

    for i in range(n):
        code = []
        for _ in range(rng.randrange(4, 9)):
            rnd_op(code)
        regs = {r: rng.randrange(0x10000) for r in ("A", "B", "X", "Y", "Z")}
        regs["S"] = 0x5E00
        mem = bytes(rng.randrange(256) for _ in range(16))
        v.append(Vector(f"soup.{i:04d}", code + jc, regs=regs, mem=mem))
    return v


TIERS[9] = tier9
ALL_TIERS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12]
