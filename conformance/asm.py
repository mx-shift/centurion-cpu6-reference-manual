"""Minimal CPU6 assembler for the conformance kernel.

Emits machine code for the small instruction subset the test kernel
needs. Every opcode used here is looked up in ../data/opcodes.yaml —
the manual's own opcode index — at import time, so the kernel cannot
silently drift from the document it is testing.

Register numbering (manual §A2): the register file is byte-addressed;
word registers live at even offsets A=0 B=2 X=4 Y=6 Z=8 S=10 C=12 P=14,
byte registers at AU=0 AL=1 BU=2 BL=3 ...
"""

import pathlib
import re

_DATA = pathlib.Path(__file__).resolve().parent.parent / "data" / "opcodes.yaml"

# Word register file indexes (manual §A2).
A, B, X, Y, Z, S, C, P = 0, 2, 4, 6, 8, 10, 12, 14
# Byte register indexes.
AU, AL, BU, BL, XU, XL, YU, YL, ZU, ZL = range(10)


def _load_opcode_index():
    """Parse data/opcodes.yaml (flat `0xNN: { mnemonic: M, ... }` lines)."""
    table = {}
    pat = re.compile(r"^0x([0-9a-fA-F]{2}):\s*\{\s*mnemonic:\s*([A-Za-z0-9]+)")
    for line in _DATA.read_text().splitlines():
        m = pat.match(line.strip())
        if m:
            table[int(m.group(1), 16)] = m.group(2)
    return table


_OPS = _load_opcode_index()


def _op(code, mnemonic):
    """Assert `code` is `mnemonic` in the manual's opcode index."""
    got = _OPS.get(code)
    if got != mnemonic:
        raise AssertionError(
            f"opcode 0x{code:02X}: manual says {got!r}, kernel wants {mnemonic!r}"
        )
    return code


class Asm:
    """Two-pass assembler: emit bytes, reference labels, resolve at end."""

    def __init__(self, org):
        self.org = org
        self.buf = bytearray()
        self.labels = {}
        self.fixups = []  # (offset, kind, label) kind: 'w'=abs16, 'r'=rel8

    # -- core -----------------------------------------------------------
    def here(self):
        return self.org + len(self.buf)

    def label(self, name):
        self.labels[name] = self.here()

    def db(self, *vals):
        for v in vals:
            self.buf.append(v & 0xFF)

    def dw(self, v):
        self.db((v >> 8) & 0xFF, v & 0xFF)

    def _word_ref(self, target):
        if isinstance(target, str):
            self.fixups.append((len(self.buf), "w", target))
            self.dw(0)
        else:
            self.dw(target)

    def _rel_ref(self, target):
        if isinstance(target, str):
            self.fixups.append((len(self.buf), "r", target))
            self.db(0)
        else:
            off = target - (self.here() + 1)
            assert -128 <= off <= 127, f"branch out of range: {off}"
            self.db(off & 0xFF)

    def finish(self):
        for off, kind, label in self.fixups:
            tgt = self.labels[label]
            if kind == "w":
                self.buf[off] = (tgt >> 8) & 0xFF
                self.buf[off + 1] = tgt & 0xFF
            else:
                rel = tgt - (self.org + off + 1)
                assert -128 <= rel <= 127, f"branch to {label} out of range: {rel}"
                self.buf[off] = rel & 0xFF
        return bytes(self.buf)

    # -- instructions (each opcode checked against the manual) -----------
    def nop(self):
        self.db(_op(0x01, "NOP"))

    def hlt(self):
        self.db(_op(0x00, "HLT"))

    def rsr(self):
        self.db(_op(0x09, "RSR"))

    # Conditional branches, PC-relative from the next instruction.
    def _bcc(self, code, name, target):
        self.db(_op(code, name))
        self._rel_ref(target)

    def bl(self, t):
        self._bcc(0x10, "BL", t)

    def bnl(self, t):
        self._bcc(0x11, "BNL", t)

    def bf(self, t):
        self._bcc(0x12, "BF", t)

    def bnf(self, t):
        self._bcc(0x13, "BNF", t)

    def bz(self, t):
        self._bcc(0x14, "BZ", t)

    def bnz(self, t):
        self._bcc(0x15, "BNZ", t)

    def bm(self, t):
        self._bcc(0x16, "BM", t)

    def bp(self, t):
        self._bcc(0x17, "BP", t)

    def jmp(self, target):
        self.db(_op(0x71, "JMP"))
        self._word_ref(target)

    def jsr(self, target):
        self.db(_op(0x79, "JSR"))
        self._word_ref(target)

    # Loads/stores. A-register rows; direct and immediate modes.
    def lda_imm(self, v):
        self.db(_op(0x90, "LDA"))
        self.dw(v)

    def lda_dir(self, addr):
        self.db(_op(0x91, "LDA"))
        self._word_ref(addr)

    def sta_dir(self, addr):
        self.db(_op(0xB1, "STA"))
        self._word_ref(addr)

    def ldb_imm(self, v):
        self.db(_op(0xD0, "LDB"))
        self.dw(v)

    def ldb_dir(self, addr):
        self.db(_op(0xD1, "LDB"))
        self._word_ref(addr)

    def stb_dir(self, addr):
        self.db(_op(0xF1, "STB"))
        self._word_ref(addr)

    def ldx_imm(self, v):
        self.db(_op(0x60, "LDX"))
        self.dw(v)

    def ldx_dir(self, addr):
        self.db(_op(0x61, "LDX"))
        self._word_ref(addr)

    def stx_dir(self, addr):
        self.db(_op(0x69, "STX"))
        self._word_ref(addr)

    def ldab_imm(self, v):
        self.db(_op(0x80, "LDAB"), v & 0xFF)

    def ldab_dir(self, addr):
        self.db(_op(0x81, "LDAB"))
        self._word_ref(addr)

    def stab_dir(self, addr):
        self.db(_op(0xA1, "STAB"))
        self._word_ref(addr)

    def ldbb_imm(self, v):
        self.db(_op(0xC0, "LDBB"), v & 0xFF)

    # One-byte register-pointer forms: EA = R[reg] (rows x8-xF).
    def ldab_via(self, reg):
        assert reg % 2 == 0
        self.db(_op(0x88 + reg // 2, "LDAB"))

    def stab_via(self, reg):
        assert reg % 2 == 0
        self.db(_op(0xA8 + reg // 2, "STAB"))

    # Word ALU row (0x50-0x57): register-register, even nibbles.
    def xfr(self, src, dst):
        self.db(_op(0x55, "XFR"), ((src & 0xF) << 4) | (dst & 0xF))

    def add_rr(self, src, dst):
        self.db(_op(0x50, "ADD"), ((src & 0xF) << 4) | (dst & 0xF))

    def sub_rr(self, src, dst):
        self.db(_op(0x51, "SUB"), ((src & 0xF) << 4) | (dst & 0xF))

    # Byte ALU row (0x40-0x47).
    def addb_rr(self, src, dst):
        self.db(_op(0x40, "ADDB"), ((src & 0xF) << 4) | (dst & 0xF))

    def subb_rr(self, src, dst):
        self.db(_op(0x41, "SUBB"), ((src & 0xF) << 4) | (dst & 0xF))

    def andb_rr(self, src, dst):
        self.db(_op(0x42, "ANDB"), ((src & 0xF) << 4) | (dst & 0xF))

    def orib_rr(self, src, dst):
        self.db(_op(0x43, "ORIB"), ((src & 0xF) << 4) | (dst & 0xF))

    def xfrb_rr(self, src, dst):
        self.db(_op(0x45, "XFRB"), ((src & 0xF) << 4) | (dst & 0xF))

    # Register-constant rows.
    def inr(self, reg, n=1):
        self.db(_op(0x30, "INR"), ((reg & 0xF) << 4) | ((n - 1) & 0xF))

    def dcr(self, reg, n=1):
        self.db(_op(0x31, "DCR"), ((reg & 0xF) << 4) | ((n - 1) & 0xF))

    def inrb(self, breg, n=1):
        self.db(_op(0x20, "INRB"), ((breg & 0xF) << 4) | ((n - 1) & 0xF))

    def dcrb(self, breg, n=1):
        self.db(_op(0x21, "DCRB"), ((breg & 0xF) << 4) | ((n - 1) & 0xF))

    def clrb(self, breg, n=0):
        self.db(_op(0x22, "CLRB"), ((breg & 0xF) << 4) | (n & 0xF))

    def srrb(self, breg, n=1):
        self.db(_op(0x24, "SRRB"), ((breg & 0xF) << 4) | ((n - 1) & 0xF))

    def slrb(self, breg, n=1):
        self.db(_op(0x25, "SLRB"), ((breg & 0xF) << 4) | ((n - 1) & 0xF))
