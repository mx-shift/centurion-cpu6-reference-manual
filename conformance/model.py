"""Reference model transcribed from the CPU6 ISA manual.

This is the conformance suite's oracle: an interpreter for the subset
of the instruction set the generated tests exercise, written *from
the manual's Operation pseudocode* and nothing else. It deliberately
shares no code with any emulator. Each handler cites the manual
section it transcribes; where the manual is ambiguous the reading is
flagged with `# READING:` — disagreements with real hardware at those
points are manual findings, not necessarily implementation bugs.

State mirrors what the on-target kernel can set and capture: the six
word registers A B X Y Z S, the four flags F L M V, and memory. PC is
internal (tests express control flow as memory/register effects).
"""


class Trap(Exception):
    """The model hit something the kernel cannot survive (or a case
    the model does not implement). Generated tests must avoid these;
    hitting one marks the vector unusable, not failed."""


class Machine:
    def __init__(self):
        self.r = {"A": 0, "B": 0, "X": 0, "Y": 0, "Z": 0, "S": 0}
        self.f = {"F": 0, "L": 0, "M": 0, "V": 0}
        self.mem = {}
        self.pc = 0

    # -- register file (§A2): byte-addressed, big-endian word pairs ---
    _WORDS = {0: "A", 2: "B", 4: "X", 6: "Y", 8: "Z", 10: "S"}

    def rget(self, idx):
        if idx not in self._WORDS:
            raise Trap(f"register {idx} (C/P) not modeled")
        return self.r[self._WORDS[idx]]

    def rset(self, idx, v):
        if idx not in self._WORDS:
            raise Trap(f"register {idx} (C/P) not modeled")
        self.r[self._WORDS[idx]] = v & 0xFFFF

    def bget(self, idx):
        w = self.rget(idx & 0xE)
        return (w >> 8) & 0xFF if idx % 2 == 0 else w & 0xFF

    def bset(self, idx, v):
        w = self.rget(idx & 0xE)
        v &= 0xFF
        w = (v << 8) | (w & 0xFF) if idx % 2 == 0 else (w & 0xFF00) | v
        self.rset(idx & 0xE, w)

    # -- memory; the register file shadows 0x0000-0x00FF (§A3) -------
    def mr(self, a):
        a &= 0xFFFF
        if a < 0x100:
            if a < 12:  # A..S as the kernel knows them
                return self.bget(a)
            raise Trap(f"regfile byte {a:#x} not modeled")
        return self.mem.get(a, 0)

    def mw(self, a, v):
        a &= 0xFFFF
        if a < 0x100:
            if a < 12:
                self.bset(a, v)
                return
            raise Trap(f"regfile byte {a:#x} not modeled")
        self.mem[a] = v & 0xFF

    def mrw(self, a):
        return (self.mr(a) << 8) | self.mr(a + 1)

    def mww(self, a, v):
        self.mw(a, (v >> 8) & 0xFF)
        self.mw(a + 1, v & 0xFF)

    # -- flag policies ----------------------------------------------
    def mv(self, v, bits):
        """'mv' policy (§B1): MINUS = sign bit, VALUE = IsZero."""
        self.f["M"] = (v >> (bits - 1)) & 1
        self.f["V"] = 1 if v & ((1 << bits) - 1) == 0 else 0

    # -- fetch helpers ------------------------------------------------
    def fetch(self):
        v = self.mr(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return v

    def fetchw(self):
        return (self.fetch() << 8) | self.fetch()

    # -- the six-mode EA family (§A5) ---------------------------------
    def ea(self, mode, width):
        if mode == 0:  # immediate: EA is the literal's own address
            a = self.pc
            self.pc = (self.pc + (2 if width == 16 else 1)) & 0xFFFF
            return a
        if mode == 1:
            return self.fetchw()
        if mode == 2:
            return self.mrw(self.fetchw())
        if mode == 3:
            d = self.fetch()
            return (self.pc + _s8(d)) & 0xFFFF
        if mode == 4:
            d = self.fetch()
            return self.mrw((self.pc + _s8(d)) & 0xFFFF)
        if mode == 5:
            return self.ea_indexed(width)
        raise Trap(f"mode {mode}")

    def ea_indexed(self, width):
        """§A5 mode byte [reg:3][0][disp:1][ind:1][id:2]
        (microcode-verified bit positions: 0x10 must be clear — the
        register nibble is even — 0x08 = displacement byte follows,
        0x04 = indirect); decrement, displace, then indirect.
        Indirection steps the register by word size."""
        mb = self.fetch()
        if mb & 0x10:
            raise Trap("illegal indexed mode (odd register nibble)")
        reg = (mb >> 4) & 0xE
        idmode = mb & 3
        step = 2 if mb & 0x04 else width // 8
        base = self.rget(reg)
        if idmode == 2:  # pre-decrement
            base = (base - step) & 0xFFFF
            self.rset(reg, base)
        elif idmode == 1:  # post-increment
            self.rset(reg, (base + step) & 0xFFFF)
        elif idmode == 3:
            raise Trap("indexed id=11")
        a = base
        if mb & 0x08:
            a = (a + _s8(self.fetch())) & 0xFFFF
        if mb & 0x04:
            a = self.mrw(a)
        return a

    # -- one architectural step --------------------------------------
    def step(self):
        op = self.fetch()
        h = _DISPATCH.get(op)
        if h is None:
            raise Trap(f"opcode {op:#04x} not modeled")
        h(self, op)


def _s8(v):
    return v - 256 if v & 0x80 else v


def _s16(v):
    return v - 65536 if v & 0x8000 else v


# ---------------------------------------------------------------------
# Instruction handlers. Section references are to the ISA manual.
# ---------------------------------------------------------------------
_DISPATCH = {}


def op(*codes):
    def reg(fn):
        for c in codes:
            _DISPATCH[c] = fn
        return fn

    return reg


@op(0x01)
def _nop(m, op_):
    pass


@op(0x00)
def _hlt(m, op_):
    raise Trap("HLT")


# B2 Bcc: PC-relative, disp from the next instruction; no flags.
_BR = {
    0x10: lambda f: f["L"] == 1,
    0x11: lambda f: f["L"] == 0,
    0x12: lambda f: f["F"] == 1,
    0x13: lambda f: f["F"] == 0,
    0x14: lambda f: f["V"] == 1,
    0x15: lambda f: f["V"] == 0,
    0x16: lambda f: f["M"] == 1,
    0x17: lambda f: f["M"] == 0,
    0x18: lambda f: f["M"] == 0 and f["V"] == 0,
    0x19: lambda f: f["M"] == 1 or f["V"] == 1,
}


@op(*range(0x10, 0x1A))
def _bcc(m, op_):
    d = _s8(m.fetch())
    if _BR[op_](m.f):
        m.pc = (m.pc + d) & 0xFFFF


# B2 JMP/JSR (modes per §A5); JSR: S -= 2, MemW[S] = return.
@op(0x71, 0x72, 0x73, 0x74, 0x75)
def _jmp(m, op_):
    m.pc = m.ea(op_ & 7, 16) if op_ & 7 != 1 else m.fetchw()


@op(0x79, 0x7A, 0x7B, 0x7C, 0x7D)
def _jsr(m, op_):
    tgt = m.ea(op_ & 7, 16) if op_ & 7 != 1 else m.fetchw()
    s = (m.rget(10) - 2) & 0xFFFF
    m.rset(10, s)
    m.mww(s, m.pc)
    m.pc = tgt


@op(0x09)
def _rsr(m, op_):
    s = m.rget(10)
    m.pc = m.mrw(s)
    m.rset(10, (s + 2) & 0xFFFF)


# B2 INRB/DCRB (rc): result = R +/- n; F overflow, M, V; L unchanged.
@op(0x20, 0x21)
def _inrb(m, op_):
    b = m.fetch()
    reg, n = b >> 4, (b & 15) + 1
    a = m.bget(reg)
    n = n if op_ == 0x20 else -n
    res = a + n
    sa, sn = _s8(a), n
    m.f["F"] = 1 if not -128 <= sa + sn <= 127 else 0
    m.bset(reg, res)
    m.mv(res & 0xFF, 8)


# B2 CLRB/IVRB: CLRB writes n, clears F and L; IVRB = ~R + n (mv only).
@op(0x22)
def _clrb(m, op_):
    b = m.fetch()
    reg, n = b >> 4, b & 15
    m.bset(reg, n)
    m.f["F"] = 0
    m.f["L"] = 0
    m.mv(n, 8)


@op(0x23)
def _ivrb(m, op_):
    b = m.fetch()
    reg, n = b >> 4, b & 15
    inv = (~m.bget(reg)) & 0xFF
    res = inv + n
    m.f["L"] = 1 if res > 0xFF else 0  # microcode-verified carry
    m.f["F"] = 1 if not -128 <= _s8(inv) + n <= 127 else 0
    m.bset(reg, res & 0xFF)
    m.mv(res & 0xFF, 8)


# B2 SRRB/SLRB/RRRB/RLRB: shift by n; L = last bit out; SLRB sets F on
# any sign change. READING: F is cleared by the right shifts and
# rotates, and by SLRB when no sign change occurs.
def _shift8(m, op_, b):
    reg, n = b >> 4, (b & 15) + 1
    v = m.bget(reg)
    kind = op_ & 3
    f = 0
    for _ in range(n):
        if kind == 0:  # SRRB arithmetic right
            l = v & 1
            v = (v >> 1) | (v & 0x80)
        elif kind == 1:  # SLRB
            l = (v >> 7) & 1
            nv = (v << 1) & 0xFF
            if (nv ^ v) & 0x80:
                f = 1
            v = nv
        elif kind == 2:  # RRRB through L
            l = v & 1
            v = (v >> 1) | (m.f["L"] << 7)
        else:  # RLRB; F on sign change like SLRB (microcode-verified)
            l = (v >> 7) & 1
            nv = ((v << 1) & 0xFF) | m.f["L"]
            if (nv ^ v) & 0x80:
                f = 1
            v = nv
        m.f["L"] = l
    m.f["F"] = f
    m.bset(reg, v)
    m.mv(v, 8)


@op(0x24, 0x25, 0x26, 0x27)
def _srrb(m, op_):
    _shift8(m, op_, m.fetch())


# One-byte AL aliases (B2 notes), reg = AL, n = 1.
@op(0x28, 0x29)
def _inab_dcab(m, op_):
    a = m.bget(1)
    n = 1 if op_ == 0x28 else -1
    m.f["F"] = 1 if not -128 <= _s8(a) + n <= 127 else 0
    res = a + n
    m.bset(1, res)
    m.mv(res & 0xFF, 8)


@op(0x2A)
def _clab(m, op_):
    m.bset(1, 0)
    m.f["F"] = 0
    m.f["L"] = 0
    m.mv(0, 8)


@op(0x2B)
def _ivab(m, op_):
    inv = (~m.bget(1)) & 0xFF
    m.f["L"] = 0  # n = 0: no carry possible
    m.f["F"] = 0
    m.bset(1, inv)
    m.mv(inv, 8)


@op(0x2C)
def _srab(m, op_):
    _shift8(m, 0x24, 1 << 4 | 0)


@op(0x2D)
def _slab(m, op_):
    _shift8(m, 0x25, 1 << 4 | 0)


# B2 word rc row 0x30-0x37 (register form only; memory forms via odd
# nibble are modeled for the direct case).
def _rc_target(m, b):
    """Returns (load, store) accessors per the even/odd nibble rule."""
    nib = b >> 4
    if nib % 2 == 0:
        return (lambda: m.rget(nib)), (lambda v: m.rset(nib, v))
    addr = m.fetchw()
    if nib != 1:
        addr = (addr + m.rget(nib - 1)) & 0xFFFF
    return (lambda: m.mrw(addr)), (lambda v: m.mww(addr, v))


@op(0x30, 0x31)
def _inr(m, op_):
    b = m.fetch()
    n = (b & 15) + 1
    ld, st = _rc_target(m, b)
    a = ld()
    n = n if op_ == 0x30 else -n
    m.f["F"] = 1 if not -32768 <= _s16(a) + n <= 32767 else 0
    res = a + n
    st(res)
    m.mv(res & 0xFFFF, 16)


@op(0x32)
def _clr(m, op_):
    b = m.fetch()
    n = b & 15
    _, st = _rc_target(m, b)
    st(n)
    m.f["F"] = 0
    m.f["L"] = 0
    m.mv(n, 16)


@op(0x33)
def _ivr(m, op_):
    b = m.fetch()
    n = b & 15
    ld, st = _rc_target(m, b)
    inv = (~ld()) & 0xFFFF
    res = inv + n
    m.f["L"] = 1 if res > 0xFFFF else 0
    m.f["F"] = 1 if not -32768 <= _s16(inv) + n <= 32767 else 0
    st(res & 0xFFFF)
    m.mv(res & 0xFFFF, 16)


def _shift16(m, kind, b):
    n = (b & 15) + 1
    ld, st = _rc_target(m, b)
    v = ld()
    f = 0
    for _ in range(n):
        if kind == 0:
            l = v & 1
            v = (v >> 1) | (v & 0x8000)
        elif kind == 1:
            l = (v >> 15) & 1
            nv = (v << 1) & 0xFFFF
            if (nv ^ v) & 0x8000:
                f = 1
            v = nv
        elif kind == 2:
            l = v & 1
            v = (v >> 1) | (m.f["L"] << 15)
        else:  # RLR; F on sign change
            l = (v >> 15) & 1
            nv = ((v << 1) & 0xFFFF) | m.f["L"]
            if (nv ^ v) & 0x8000:
                f = 1
            v = nv
        m.f["L"] = l
    m.f["F"] = f
    st(v)
    m.mv(v, 16)


@op(0x34, 0x35, 0x36, 0x37)
def _srr(m, op_):
    _shift16(m, op_ & 3, m.fetch())


# One-byte A/X aliases (B2 notes): INA DCA CLA IVA SRA SLA, INX DCX.
@op(0x38, 0x39)
def _ina_dca(m, op_):
    a = m.rget(0)
    n = 1 if op_ == 0x38 else -1
    m.f["F"] = 1 if not -32768 <= _s16(a) + n <= 32767 else 0
    res = a + n
    m.rset(0, res)
    m.mv(res & 0xFFFF, 16)


@op(0x3A)
def _cla(m, op_):
    m.rset(0, 0)
    m.f["F"] = 0
    m.f["L"] = 0
    m.mv(0, 16)


@op(0x3B)
def _iva(m, op_):
    inv = (~m.rget(0)) & 0xFFFF
    m.f["L"] = 0
    m.f["F"] = 0
    m.rset(0, inv)
    m.mv(inv, 16)


@op(0x3C)
def _sra(m, op_):
    _shift16(m, 0, 0x00)


@op(0x3D)
def _sla(m, op_):
    _shift16(m, 1, 0x00)


@op(0x3E, 0x3F)
def _inx_dcx(m, op_):
    # Microcode-verified: INX/DCX step X by ONE, not the word size.
    a = m.rget(4)
    n = 1 if op_ == 0x3E else -1
    m.f["F"] = 1 if not -32768 <= _s16(a) + n <= 32767 else 0
    res = a + n
    m.rset(4, res)
    m.mv(res & 0xFFFF, 16)


# B2 byte rr ALU 0x40-0x45: dst = op(src, dst); SUBB = src - dst.
def _alu8(m, kind, a, b):
    """a = src value, b = dst value; returns result, sets flags."""
    if kind == 0:  # ADDB: F overflow, L carry
        res = a + b
        m.f["L"] = 1 if res > 0xFF else 0
        m.f["F"] = 1 if not -128 <= _s8(a) + _s8(b) <= 127 else 0
    elif kind == 1:  # SUBB: src - dst; L = no-borrow
        res = a - b
        m.f["L"] = 1 if a >= b else 0
        m.f["F"] = 1 if not -128 <= _s8(a) - _s8(b) <= 127 else 0
    elif kind == 2:
        res = a & b
    elif kind == 3:
        res = a | b
    elif kind == 4:
        res = a ^ b
    else:  # XFRB
        res = a
    res &= 0xFF
    m.mv(res, 8)
    return res


@op(0x40, 0x41, 0x42, 0x43, 0x44, 0x45)
def _byte_rr(m, op_):
    b = m.fetch()
    src, dst = b >> 4, b & 15
    m.bset(dst, _alu8(m, op_ & 7, m.bget(src), m.bget(dst)))


# One-byte aliases 0x48-0x4F (B2 notes).
@op(0x48)
def _aab(m, op_):
    m.bset(3, _alu8(m, 0, m.bget(1), m.bget(3)))


@op(0x49)
def _sabb(m, op_):
    m.bset(3, _alu8(m, 1, m.bget(1), m.bget(3)))


@op(0x4A)
def _nabb(m, op_):
    m.bset(3, _alu8(m, 2, m.bget(1), m.bget(3)))


@op(0x4B, 0x4C, 0x4D, 0x4E, 0x4F)
def _xa_b(m, op_):
    dst = {0x4B: 5, 0x4C: 7, 0x4D: 3, 0x4E: 9, 0x4F: 11}[op_]
    m.bset(dst, _alu8(m, 5, m.bget(1), m.bget(dst)))


# B2 word rr ALU 0x50-0x55 with CPU6 immediate/direct/indexed
# sub-modes selected by the nibble low bits (s=1,d=0 imm; s=0,d=1
# direct; s=1,d=1 indexed).
def _alu16(m, kind, a, b):
    if kind == 0:
        res = a + b
        m.f["L"] = 1 if res > 0xFFFF else 0
        m.f["F"] = 1 if not -32768 <= _s16(a) + _s16(b) <= 32767 else 0
    elif kind == 1:
        res = a - b
        m.f["L"] = 1 if a >= b else 0
        m.f["F"] = 1 if not -32768 <= _s16(a) - _s16(b) <= 32767 else 0
    elif kind == 2:
        res = a & b
    elif kind == 3:
        res = a | b
    elif kind == 4:
        res = a ^ b
    else:
        res = a
    res &= 0xFFFF
    m.mv(res, 16)
    return res


@op(0x50, 0x51, 0x52, 0x53, 0x54, 0x55)
def _word_rr(m, op_):
    b = m.fetch()
    s, d = b >> 4, b & 15
    if s % 2 == 0 and d % 2 == 0:
        src = m.rget(s)
        m.rset(d, _alu16(m, op_ & 7, src, m.rget(d)))
        return
    if s % 2 == 1 and d % 2 == 0:  # immediate
        src = m.fetchw()
        m.rset(d & 0xE, _alu16(m, op_ & 7, src, m.rget(d & 0xE)))
        return
    if s % 2 == 0 and d % 2 == 1:  # direct
        addr = m.fetchw()
        src = m.mrw(addr)
        m.rset(d & 0xE, _alu16(m, op_ & 7, src, m.rget(d & 0xE)))
        return
    raise Trap("word ALU indexed sub-mode not modeled")


# B2 MUL (0x77) / DIV (0x78), register-register form only.
@op(0x77)
def _mul(m, op_):
    b = m.fetch()
    s, d = b >> 4, b & 15
    if s % 2 or d % 2:
        raise Trap("MUL sub-mode not modeled")
    prod = m.rget(s) * m.rget(d)
    if d in (0, 4, 8):  # pair leader A/X/Z? READING: leader = even pair
        pass
    # Pair leader rule (B2): leaders are A,X,Z? The manual defines the
    # pair as (leader, follower) = (reg, reg+2): A/B, X/Y, Z/S.
    if d in (0, 4, 8):
        m.rset(d, (prod >> 16) & 0xFFFF)
        m.rset(d + 2, prod & 0xFFFF)
    else:
        m.rset(d, prod & 0xFFFF)
    m.f["V"] = 1 if prod == 0 else 0
    m.f["F"] = 1 if prod > 0xFFFF else 0
    m.f["M"] = (prod >> 31) & 1 if prod > 0xFFFF else (prod >> 15) & 1


@op(0x78)
def _div(m, op_):
    b = m.fetch()
    s, d = b >> 4, b & 15
    if s % 2 or d % 2:
        raise Trap("DIV sub-mode not modeled")
    divisor = m.rget(s)
    if divisor == 0:
        m.f["F"] = 1
        return
    # Microcode-verified: the dividend is the 16-bit dst register
    # itself (NOT a 32-bit pair). Pair-leader dst: quotient to the
    # follower, remainder to the leader; otherwise quotient replaces
    # dst and the remainder is discarded.
    dividend = m.rget(d)
    q, r = divmod(dividend, divisor)
    if d in (0, 4, 8):
        m.rset(d, r & 0xFFFF)
        m.rset(d + 2, q & 0xFFFF)
    else:
        m.rset(d, q & 0xFFFF)
    m.f["V"] = 1 if q & 0xFFFF == 0 else 0
    m.f["M"] = (q >> 15) & 1
    m.f["L"] = 1 if r != 0 else 0


# B2 loads/stores: rows 0x60 LDX, 0x80 LDAB, 0x90 LDA, 0xA0 STAB,
# 0xB0 STA, 0xC0 LDBB, 0xD0 LDB, 0xE0 STBB, 0xF0 STB; modes 0-5 plus
# the one-byte register-pointer forms (+8..+15).
def _ld(m, op_, breg, wreg):
    mode = op_ & 7
    width = 8 if breg is not None else 16
    if op_ & 8:
        a = m.rget((op_ & 7) * 2)
    else:
        a = m.ea(mode, width)
    if breg is not None:
        v = m.mr(a)
        m.bset(breg, v)
        m.mv(v, 8)
    else:
        v = m.mrw(a)
        m.rset(wreg, v)
        m.mv(v, 16)


def _st(m, op_, breg, wreg):
    mode = op_ & 7
    width = 8 if breg is not None else 16
    if op_ & 8:
        a = m.rget((op_ & 7) * 2)
    else:
        a = m.ea(mode, width)
    if breg is not None:
        v = m.bget(breg)
        m.mw(a, v)
        m.mv(v, 8)
    else:
        v = m.rget(wreg)
        m.mww(a, v)
        m.mv(v, 16)


@op(*range(0x60, 0x66))
def _ldx(m, op_):
    _ld(m, op_ & 7, None, 4)


@op(*range(0x68, 0x6E))
def _stx(m, op_):
    _st(m, op_ & 7, None, 4)


@op(*range(0x80, 0x90))
def _ldab(m, op_):
    _ld(m, op_, 1, None)


@op(*range(0x90, 0xA0))
def _lda(m, op_):
    _ld(m, op_, None, 0)


@op(*range(0xA0, 0xB0))
def _stab(m, op_):
    _st(m, op_, 1, None)


@op(*range(0xB0, 0xC0))
def _sta(m, op_):
    _st(m, op_, None, 0)


@op(*range(0xC0, 0xD0))
def _ldbb(m, op_):
    _ld(m, op_, 3, None)


@op(*range(0xD0, 0xE0))
def _ldb(m, op_):
    _ld(m, op_, None, 2)


@op(*range(0xE0, 0xF0))
def _stbb(m, op_):
    _st(m, op_, 3, None)


@op(*range(0xF0, 0x100))
def _stb(m, op_):
    _st(m, op_, None, 2)


# B2 STK/POP (0x7E/0x7F).
@op(0x7E)
def _stk(m, op_):
    b = m.fetch()
    reg, cnt = b >> 4, (b & 15) + 1
    s = m.rget(10)
    for i in range(cnt - 1, -1, -1):
        s = (s - 1) & 0xFFFF
        m.mw(s, m.bget(reg + i))
    m.rset(10, s)


@op(0x7F)
def _pop(m, op_):
    b = m.fetch()
    reg, cnt = b >> 4, (b & 15) + 1
    s = m.rget(10)
    for i in range(cnt):
        m.bset(reg + i, m.mr(s))
        s = (s + 1) & 0xFFFF
    m.rset(10, s)


# B2.36 BIG (0x46): length byte, selector byte, operand specs.
@op(0x46)
def _big(m, op_):
    lenb = m.fetch()
    sel = m.fetch()
    sl, dl = (lenb >> 4) + 1, (lenb & 15) + 1
    subop = sel >> 4
    sspec, dspec = (sel >> 2) & 3, sel & 3

    def spec_addr(spec, is_src, llen):
        if spec == 0:
            return m.fetchw()
        if spec == 3 and is_src:
            a = m.pc
            m.pc = (m.pc + llen) & 0xFFFF
            return a
        raise Trap(f"BIG spec {spec} not modeled")

    src = spec_addr(sspec, True, sl)
    dst = spec_addr(dspec, False, dl)

    def rd(a, n):
        v = 0
        neg = m.mr(a) & 0x80
        for i in range(n):
            v = (v << 8) | m.mr(a + i)
        if neg:
            v -= 1 << (8 * n)
        return v

    def wr(a, n, v):
        for i in range(n):
            m.mw(a + i, (v >> (8 * (n - 1 - i))) & 0xFF)

    def setmv(v, n):
        bits = 8 * n
        masked = v & ((1 << bits) - 1)
        m.f["V"] = 1 if masked == 0 else 0
        m.f["M"] = (masked >> (bits - 1)) & 1

    if subop in (0, 1, 2):  # add / sub / compare (dst - src)
        s_, d_ = rd(src, sl), rd(dst, dl)
        mask = (1 << (8 * dl)) - 1
        if subop == 0:
            res = (d_ & mask) + (s_ & mask)
            m.f["L"] = 1 if res > mask else 0
        else:
            res = (d_ & mask) - (s_ & mask)
            m.f["L"] = 1 if (d_ & mask) >= (s_ & mask) else 0
        setmv(res, dl)
        if subop != 2:
            wr(dst, dl, res)
    elif subop in (3, 4):  # ZAD move / ZSU negate-move
        v = rd(src, sl)
        if subop == 4:
            v = -v
        wr(dst, dl, v)
        setmv(v, dl)
    elif subop == 5:  # multiply
        v = rd(dst, dl) * rd(src, sl)
        wr(dst, dl, v)
        setmv(v, dl)
    elif subop in (6, 7):  # divide / divide with remainder
        s_ = rd(src, sl)
        if s_ == 0:
            m.f["F"] = 1
            return
        d_ = rd(dst, dl)
        q = int(d_ / s_)  # trunc toward zero
        wr(dst, dl, q)
        if subop == 7:
            # B2.36: the remainder is stored at the address held in A.
            wr(m.rget(0), sl, d_ - q * s_)
        setmv(q, dl)
    else:
        raise Trap(f"BIG subop {subop} not modeled")


# ---------------------------------------------------------------------
# Test-vector execution: run a code snippet exactly as the kernel does.
# ---------------------------------------------------------------------
SLOT = 0x4D00
CAPTURE_SENTINEL = 0xFFFF


def run_vector(regs, mem_addr, mem_bytes, code, capture_addr, max_steps=10000):
    """Returns (flags_nibble, regs_dict, mem_bytes_after) or raises Trap."""
    m = Machine()
    for k, v in regs.items():
        m.r[k] = v & 0xFFFF
    # Kernel entry flags: CLRB clears F and L; the register loads are
    # mv-only, ending with LDA of the requested A value.
    m.f["F"] = 0
    m.f["L"] = 0
    m.mv(m.r["A"], 16)
    for i, b in enumerate(mem_bytes):
        m.mem[(mem_addr + i) & 0xFFFF] = b
    for i, b in enumerate(code):
        m.mem[(SLOT + i) & 0xFFFF] = b
    m.pc = SLOT
    for _ in range(max_steps):
        if m.pc == capture_addr:
            flags = (m.f["F"] << 3) | (m.f["L"] << 2) | (m.f["M"] << 1) | m.f["V"]
            out = bytes(m.mem.get((mem_addr + i) & 0xFFFF, 0) for i in range(len(mem_bytes)))
            return flags, dict(m.r), out
        m.step()
    raise Trap("model: step limit")
