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


#: MMU page RAM after reset under the DIAG monitor (map 0 identity
#: through page 0x1D, boot pages 0x1E/0x1F 0x7E/0x7F; maps 1-7 clear).
RESET_PAGE_RAM = list(range(0x1E)) + [0x7E, 0x7F] + [0] * 224


class Machine:
    def __init__(self):
        # Full 256-byte register file (§A2): 16 banks of 16 bytes,
        # selected by the interrupt level; word registers A B X Y Z S
        # C P at even offsets, big-endian. Bank contents are
        # zero-initialized — vectors must write any cross-level cell
        # before reading it (real banks hold boot residue).
        self.rf = bytearray(256)
        self.level = 0
        self.f = {"F": 0, "L": 0, "M": 0, "V": 0}
        self.int_enable = 0  # A4: reset disables interrupts
        self.clock_run = 0  # A4: reset stops the clock
        self.aoo = 0
        self.pta = 0
        self.page_ram = list(RESET_PAGE_RAM)
        # DMA channel registers (B2 DMA); never enabled by vectors.
        self.dma = {"addr": 0, "count": 0, "dev": 0, "en": 0, "ilvl": 0}
        # Minimal MUX interrupt machinery for the forced-TX round trip.
        self.mux = {"ilvl": 0, "int_en": 0, "pend": 0, "cause": 0}
        self.mem = {}
        self.pc = 0

    # -- register file accessors (current bank) -----------------------
    def rget(self, idx):
        if idx in (12, 14):
            raise Trap("C/P as a named operand not modeled")
        b = (self.level << 4) | (idx & 0xE)
        return (self.rf[b] << 8) | self.rf[b + 1]

    def rset(self, idx, v):
        if idx in (12, 14):
            raise Trap("C/P as a named operand not modeled")
        b = (self.level << 4) | (idx & 0xE)
        self.rf[b] = (v >> 8) & 0xFF
        self.rf[b + 1] = v & 0xFF

    def bget(self, idx):
        return self.rf[(self.level << 4) | (idx & 0xF)]

    def bset(self, idx, v):
        self.rf[(self.level << 4) | (idx & 0xF)] = v & 0xFF

    # raw register-file access (SAR/LAR, level switching)
    def rfw(self, addr, v):
        self.rf[addr & 0xFF] = v & 0xFF

    def rfr(self, addr):
        return self.rf[addr & 0xFF]

    # -- status composition (§A4): C.lo = [V M F L][AOO][PTA] ---------
    def compose_clo(self):
        return (
            (self.f["V"] << 7) | (self.f["M"] << 6) | (self.f["F"] << 5)
            | (self.f["L"] << 4) | (self.aoo << 3) | (self.pta & 7)
        )

    def apply_clo(self, v):
        self.aoo = (v >> 3) & 1
        self.pta = v & 7

    # -- level switching (§A4 Entry / RI) ------------------------------
    def enter_level(self, target, cause=None):
        old = self.level
        base = old << 4
        self.rf[base + 14] = (self.pc >> 8) & 0xFF
        self.rf[base + 15] = self.pc & 0xFF
        self.rf[base + 13] = self.compose_clo()
        tbase = target << 4
        self.rf[tbase + 12] = (old << 4) | 5  # entry stamp
        for k in self.f:
            self.f[k] = 0
        self.apply_clo(self.rf[tbase + 13])
        self.level = target
        if cause is not None:
            self.rf[tbase + 1] = cause  # AL only; AU survives
        self.pc = (self.rf[tbase + 14] << 8) | self.rf[tbase + 15]

    def trap15(self, cause):
        self.enter_level(15, cause=cause)

    def check_interrupts(self):
        """Pending MUX interrupt entry at an instruction boundary."""
        if (
            self.int_enable
            and self.mux["int_en"]
            and self.mux["pend"]
            and self.mux["ilvl"] > self.level
        ):
            self.enter_level(self.mux["ilvl"])
            self.mux["pend"] = 0  # entry acknowledges the request

    # -- memory; the register file shadows 0x0000-0x00FF (§A3),
    #    MMIO at 0xF200-0xF20F is the MUX (interrupt subset only) ----
    def mr(self, a):
        a &= 0xFFFF
        if a < 0x100:
            return self.rf[a]
        if a == 0xF20F:
            v = self.mux["cause"]
            self.mux["cause"] = 0  # reading consumes the cause latch
            return v
        if 0xF200 <= a <= 0xF2FF and a not in (0xF20F,):
            raise Trap(f"MUX register {a:#x} read not modeled")
        return self.mem.get(a, 0)

    def mw(self, a, v):
        a &= 0xFFFF
        v &= 0xFF
        if a < 0x100:
            self.rf[a] = v
            return
        if 0xF200 <= a <= 0xF2FF:
            if a == 0xF20A:
                self.mux["ilvl"] = v & 0xF
            elif a == 0xF20C:  # force TX interrupt, ports in low nibble
                if v & 0xF:
                    self.mux["pend"] = 1
                    self.mux["cause"] = 1  # port 0, TX flag
            elif a == 0xF20D:
                self.mux["int_en"] = 0
            elif a == 0xF20E:
                self.mux["int_en"] = 1
            elif a == 0xF20F:
                self.mux["pend"] = 0
            else:
                raise Trap(f"MUX register {a:#x} write not modeled")
            return
        self.mem[a] = v

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
    # A4: HLT below level 15 traps to 15 with cause 1; the saved PC
    # points past the HLT. At level 15 it genuinely halts.
    if m.level == 15:
        raise Trap("HLT at level 15")
    m.trap15(1)


# Illegal opcodes trap to level 15 with cause 0 (§A4).
@op(0x0B, 0x70, 0x87, 0x97, 0xA7, 0xB7, 0xC7, 0xE7)
def _illegal(m, op_):
    m.trap15(0)


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
    # n = 0: pure complement, L and F untouched; n >= 1: the add's
    # carry and overflow land in L and F (microcode-verified).
    b = m.fetch()
    reg, n = b >> 4, b & 15
    inv = (~m.bget(reg)) & 0xFF
    res = inv + n
    if n:
        m.f["L"] = 1 if res > 0xFF else 0
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
    write_f = kind in (1, 3)  # right shifts/rotates PRESERVE F
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
    if write_f:
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
    # Unlike the two-byte IVRB, the alias PRESERVES L and F
    # (microcode-verified).
    inv = (~m.bget(1)) & 0xFF
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
    if n:
        m.f["L"] = 1 if res > 0xFFFF else 0
        m.f["F"] = 1 if not -32768 <= _s16(inv) + n <= 32767 else 0
    st(res & 0xFFFF)
    m.mv(res & 0xFFFF, 16)


def _shift16(m, kind, b):
    n = (b & 15) + 1
    ld, st = _rc_target(m, b)
    v = ld()
    f = 0
    write_f = kind in (1, 3)
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
    if write_f:
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
    # s=1,d=1 indexed: operand at MemW[R[src] + disp16] (B2 ADD)
    disp = m.fetchw()
    src = m.mrw((m.rget(s & 0xE) + disp) & 0xFFFF)
    m.rset(d & 0xE, _alu16(m, op_ & 7, src, m.rget(d & 0xE)))


# B2 MUL (0x77) / DIV (0x78), register-register form only.
def _mul_result(m, d, prod):
    """B2 MUL: pair leaders A/X/Z take the 32-bit product across the
    (leader, follower) pair; other destinations the low word only."""
    if d in (0, 4, 8):
        m.rset(d, (prod >> 16) & 0xFFFF)
        m.rset(d + 2, prod & 0xFFFF)
    else:
        m.rset(d, prod & 0xFFFF)
    m.f["V"] = 1 if prod == 0 else 0
    m.f["F"] = 1 if prod > 0xFFFF else 0
    m.f["M"] = (prod >> 31) & 1 if prod > 0xFFFF else (prod >> 15) & 1
    m.f["L"] = 0  # microcode-verified: MUL writes L low


@op(0x77)
def _mul(m, op_):
    b = m.fetch()
    s, d = b >> 4, b & 15
    if s % 2 == 0 and d % 2 == 0:
        _mul_result(m, d, m.rget(s) * m.rget(d))
        return
    if s % 2 == 1 and d % 2 == 0:
        # immediate: src nibble names the multiplicand register
        operand = m.fetchw()
        _mul_result(m, d, operand * m.rget(s & 0xE))
        return
    if s % 2 == 0 and d % 2 == 1:
        # direct: operand in memory, src nibble names the multiplicand
        operand = m.mrw(m.fetchw())
        _mul_result(m, d & 0xE, operand * m.rget(s))
        return
    # indexed: operand at MemW[R[src]+disp]; multiplies dst itself
    disp = m.fetchw()
    operand = m.mrw((m.rget(s & 0xE) + disp) & 0xFFFF)
    _mul_result(m, d & 0xE, operand * m.rget(d & 0xE))


def _div_exec(m, d, dividend, divisor):
    if divisor == 0:
        m.f["F"] = 1
        return
    m.f["F"] = 0  # microcode-verified: success clears the fault flag
    q, r = divmod(dividend, divisor)
    if d in (0, 4, 8):
        m.rset(d, r & 0xFFFF)
        m.rset(d + 2, q & 0xFFFF)
    else:
        m.rset(d, q & 0xFFFF)
    m.f["V"] = 1 if q & 0xFFFF == 0 else 0
    m.f["M"] = (q >> 15) & 1
    m.f["L"] = 1 if r != 0 else 0


@op(0x78)
def _div(m, op_):
    b = m.fetch()
    s, d = b >> 4, b & 15
    if s % 2 == 1 and d % 2 == 0:
        # immediate divisor; src nibble names the dividend register
        divisor = m.fetchw()
        _div_exec(m, d, m.rget(s & 0xE), divisor)
        return
    if s % 2 == 0 and d % 2 == 1:
        # direct divisor; src nibble names the dividend register
        divisor = m.mrw(m.fetchw())
        _div_exec(m, d & 0xE, m.rget(s), divisor)
        return
    if s % 2 == 1 and d % 2 == 1:
        disp = m.fetchw()
        divisor = m.mrw((m.rget(s & 0xE) + disp) & 0xFFFF)
        _div_exec(m, d & 0xE, m.rget(d & 0xE), divisor)
        return
    # Microcode-verified: the dividend is the 16-bit dst register
    # itself (NOT a 32-bit pair).
    divisor = m.rget(s)
    _div_exec(m, d, m.rget(d), divisor)


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

    shared = {}

    def spec_addr(spec, is_src, llen):
        if spec == 0:
            return m.fetchw()
        if spec == 1:
            v0 = m.fetch()
            regh, regl = v0 >> 4, v0 & 15
            disp = m.fetchw() if regh & 1 else _s8(m.fetch()) & 0xFFFF
            ea = (m.rget(regh & 0xE) + disp) & 0xFFFF
            if regl:
                ea = (ea + m.rget(regl & 0xE)) & 0xFFFF
            return ea
        if spec == 2:
            if "b" not in shared:
                shared["b"] = m.fetch()
            b = shared["b"]
            return m.rget((b >> 4) & 0xE) if is_src else m.rget(b & 0xE)
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
    elif subop == 8:
        _big_ctb(m, lenb, src, dst, dl)
    elif subop == 9:
        # first operand = template, second = the value
        _big_cfb(m, lenb, src, dst, dl)
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
    names = {"A": 0, "B": 2, "X": 4, "Y": 6, "Z": 8, "S": 10}
    for k, v in regs.items():
        m.rset(names[k], v)
    # Kernel entry flags: CLRB clears F and L; the register loads are
    # mv-only, ending with LDA of the requested A value.
    m.f["F"] = 0
    m.f["L"] = 0
    m.mv(m.rget(0), 16)
    for i, b in enumerate(mem_bytes):
        m.mem[(mem_addr + i) & 0xFFFF] = b
    for i, b in enumerate(code):
        m.mem[(SLOT + i) & 0xFFFF] = b
    m.pc = SLOT
    for _ in range(max_steps):
        m.check_interrupts()
        if m.pc == capture_addr:
            if m.level != 0:
                raise Trap("capture reached above level 0")
            flags = (m.f["F"] << 3) | (m.f["L"] << 2) | (m.f["M"] << 1) | m.f["V"]
            out = bytes(m.mem.get((mem_addr + i) & 0xFFFF, 0) for i in range(len(mem_bytes)))
            regs_out = {k: m.rget(i) for k, i in names.items()}
            return flags, regs_out, out
        m.step()
    raise Trap("model: step limit")


# ---------------------------------------------------------------------
# Control row (B2 control: SF/RF/SL/RL/CL, SYN, PCX, DLY).
# ---------------------------------------------------------------------
@op(0x02)
def _sf(m, op_):
    m.f["F"] = 1


@op(0x03)
def _rf(m, op_):
    m.f["F"] = 0


@op(0x06)
def _sl(m, op_):
    m.f["L"] = 1


@op(0x07)
def _rl(m, op_):
    m.f["L"] = 0


@op(0x08)
def _cl(m, op_):
    m.f["L"] ^= 1


@op(0x0A)
def _ri(m, op_):
    # B2 RI: return to the level recorded in this bank's C high
    # nibble; this bank's own P and C.lo are saved on the way out.
    target = m.rf[(m.level << 4) | 12] >> 4
    base = m.level << 4
    m.rf[base + 14] = (m.pc >> 8) & 0xFF
    m.rf[base + 15] = m.pc & 0xFF
    m.rf[base + 13] = m.compose_clo()
    if target == m.level:
        return  # observed self-switch fall-through (P updated above)
    tbase = target << 4
    clo = m.rf[tbase + 13]
    m.f["V"] = (clo >> 7) & 1
    m.f["M"] = (clo >> 6) & 1
    m.f["F"] = (clo >> 5) & 1
    m.f["L"] = (clo >> 4) & 1
    m.apply_clo(clo)
    m.level = target
    m.pc = (m.rf[tbase + 14] << 8) | m.rf[tbase + 15]


@op(0x04)
def _ei(m, op_):
    m.int_enable = 1


@op(0x05)
def _di(m, op_):
    m.int_enable = 0


@op(0xB6)
def _eck(m, op_):
    m.clock_run = 1


@op(0xC6)
def _dck(m, op_):
    m.clock_run = 0


@op(0x0C)
def _syn(m, op_):
    pass  # front-panel indicator only


@op(0x0D)
def _pcx(m, op_):
    m.rset(4, m.pc)  # X = address of the next instruction


@op(0x0E)
def _dly(m, op_):
    pass  # ~4.55 ms delay; no architectural effect


# BI/BCK branch on the modeled enable bits; vectors normalize the
# state first (DI/EI, DCK/ECK) so the entry value never matters.
@op(0x1E)
def _bi(m, op_):
    d = _s8(m.fetch())
    if m.int_enable:
        m.pc = (m.pc + d) & 0xFFFF


@op(0x1F)
def _bck(m, op_):
    d = _s8(m.fetch())
    if m.clock_run:
        m.pc = (m.pc + d) & 0xFFFF


# ---------------------------------------------------------------------
# One-byte word ALU aliases 0x58-0x5F (B2 ALU notes).
# ---------------------------------------------------------------------
@op(0x58)
def _aab(m, op_):
    m.rset(2, _alu16(m, 0, m.rget(0), m.rget(2)))


@op(0x59)
def _sab(m, op_):
    m.rset(2, _alu16(m, 1, m.rget(0), m.rget(2)))


@op(0x5A)
def _nab(m, op_):
    m.rset(2, _alu16(m, 2, m.rget(0), m.rget(2)))


@op(0x5B, 0x5C, 0x5D, 0x5E, 0x5F)
def _xa_word(m, op_):
    dst = {0x5B: 4, 0x5C: 6, 0x5D: 2, 0x5E: 8, 0x5F: 10}[op_]
    m.rset(dst, _alu16(m, 5, m.rget(0), m.rget(dst)))


# ---------------------------------------------------------------------
# STR (0xD6): store any word register (B2 system).
# ---------------------------------------------------------------------
@op(0xD6)
def _str(m, op_):
    b = m.fetch()
    n1, n2 = b >> 4, b & 15
    if n1 % 2 == 0 and n2 % 2 == 0:
        # register-register: dst in the HIGH nibble (reversed vs XFR)
        v = m.rget(n2)
        m.rset(n1, v)
        m.mv(v, 16)
        return
    if n1 % 2 == 1 and n2 % 2 == 0:
        # store low nibble's register over the inline word
        a = m.pc
        m.pc = (m.pc + 2) & 0xFFFF
        v = m.rget(n2)
        m.mww(a, v)
        m.mv(v, 16)
        return
    if n1 % 2 == 0 and n2 % 2 == 1:
        a = m.fetchw()
        v = m.rget(n1)
        m.mww(a, v)
        m.mv(v, 16)
        return
    disp = m.fetchw()
    a = (m.rget(n1 & 0xE) + disp) & 0xFFFF
    v = m.rget(n2 & 0xE)
    m.mww(a, v)
    m.mv(v, 16)


# ---------------------------------------------------------------------
# SAR/LAR (0xD7/0xE6): cross-level register-file access; no flags.
# ---------------------------------------------------------------------
@op(0xD7)
def _sar(m, op_):
    n = m.fetch()
    a = m.rget(0)
    m.rfw(n, a >> 8)
    m.rfw(n + 1, a & 0xFF)


@op(0xE6)
def _lar(m, op_):
    n = m.fetch()
    m.rset(0, (m.rfr(n) << 8) | m.rfr(n + 1))


# ---------------------------------------------------------------------
# LST/SST (0x6E/0x6F): flag nibble <-> status byte (B2 loads/stores
# notes; SST's low nibble reads 0x0F at level 0). Status layout
# [V M F L | low nibble].
# ---------------------------------------------------------------------
def _ccpack(m):
    return (m.f["V"] << 7) | (m.f["M"] << 6) | (m.f["F"] << 5) | (m.f["L"] << 4)


def _ccunpack(m, v):
    m.f["V"] = (v >> 7) & 1
    m.f["M"] = (v >> 6) & 1
    m.f["F"] = (v >> 5) & 1
    m.f["L"] = (v >> 4) & 1


@op(0x6E)
def _lst(m, op_):
    a = m.fetchw()
    _ccunpack(m, m.mr(a))


@op(0x6F)
def _sst(m, op_):
    a = m.fetchw()
    m.mw(a, _ccpack(m) | 0x0F)


# ---------------------------------------------------------------------
# MVL (0xF7): move A+1 bytes from [B] to [Y]; registers and flags
# untouched (B2 system).
# ---------------------------------------------------------------------
@op(0xF7)
def _mvl(m, op_):
    n = m.rget(0) + 1
    b, y = m.rget(2), m.rget(6)
    for i in range(n):
        m.mw((y + i) & 0xFFFF, m.mr((b + i) & 0xFFFF))


# ---------------------------------------------------------------------
# MEM (0x47 length byte / 0x67 length from AL) — B2.37.
# ---------------------------------------------------------------------
@op(0x47, 0x67)
def _mem(m, op_):
    sel = m.fetch()
    subop = sel >> 4
    if subop == 0:
        _mem_binload(m, sel)
        return
    if subop in (1, 3):
        raise Trap(f"MEM subop {subop} not modeled")
    if op_ == 0x47:
        count = m.fetch() + 1
    else:
        count = m.bget(1) + 1
    matchb = m.fetch() if subop == 2 else 0
    sspec, dspec = (sel >> 2) & 3, sel & 3
    shared = {}

    def spec(spec_, is_src):
        if spec_ == 0:
            return m.fetchw()
        if spec_ == 1:
            v0 = m.fetch()
            regh, regl = v0 >> 4, v0 & 15
            disp = m.fetchw() if regh & 1 else _s8(m.fetch()) & 0xFFFF
            ea = (m.rget(regh & 0xE) + disp) & 0xFFFF
            if regl:
                ea = (ea + m.rget(regl & 0xE)) & 0xFFFF
            return ea
        if spec_ == 2:
            if "b" not in shared:
                shared["b"] = m.fetch()
            b = shared["b"]
            return m.rget((b >> 4) & 0xE) if is_src else m.rget(b & 0xE)
        if is_src:  # 3: inline literal
            lit_len = 1 if subop == 9 else count
            a = m.pc
            m.pc = (m.pc + lit_len) & 0xFFFF
            return a
        raise Trap("MEM dst spec 3")

    src = spec(sspec, True)
    dst = spec(dspec, False)

    if subop == 2:  # MVV copy-until-match
        found = None
        for i in range(count):
            b = m.mr((src + i) & 0xFFFF)
            m.mw((dst + i) & 0xFFFF, b)
            if b == matchb:
                found = i
                break
        off = found if found is not None else count
        m.rset(6, (src + off) & 0xFFFF)
        m.rset(8, (dst + off) & 0xFFFF)
        m.f["F"] = 0 if found is not None else 1
    elif subop in (4, 5, 6, 7):  # MVF/ANC/ORC/XRC
        z = 0
        for i in range(count):
            sv = m.mr((src + i) & 0xFFFF)
            if subop == 4:
                res = sv
            elif subop == 5:
                res = m.mr((dst + i) & 0xFFFF) & sv
            elif subop == 6:
                res = m.mr((dst + i) & 0xFFFF) | sv
            else:
                res = m.mr((dst + i) & 0xFFFF) ^ sv
            z |= res
            m.mw((dst + i) & 0xFFFF, res)
        m.f["V"] = 1 if z == 0 else 0
        m.f["M"] = 1 if z & 0x80 else 0
    elif subop == 8:  # CPF
        for i in range(count):
            sv = m.mr((src + i) & 0xFFFF)
            dv = m.mr((dst + i) & 0xFFFF)
            m.f["V"] = 1 if dv == sv else 0
            m.f["M"] = 1 if dv < sv else 0
            if dv != sv:
                break
    elif subop == 9:  # FIL: no flag effects
        b = m.mr(src)
        for i in range(count):
            m.mw((dst + i) & 0xFFFF, b)


# ---------------------------------------------------------------------
# SVC (0x66) / RSV (0x0F) — B2 system; map switches are invisible here
# (the monitor environment runs map 0 already).
# ---------------------------------------------------------------------
@op(0x66)
def _svc(m, op_):
    num = m.fetch()
    s = m.rget(10)
    for v in (m.compose_clo(), 0x05, m.rget(4) & 0xFF, m.rget(4) >> 8, num):
        s = (s - 1) & 0xFFFF
        m.mw(s, v)
    m.rset(10, s)
    m.rset(4, m.pc)  # X = return address
    for k in m.f:
        m.f[k] = 0
    m.pta = 0  # supervisor address space (identity here)
    m.pc = 0x0100


@op(0x0F)
def _rsv(m, op_):
    s = m.rget(10)
    frame_x = (m.mr((s + 1) & 0xFFFF) << 8) | m.mr((s + 2) & 0xFFFF)
    frame_cc = m.mr((s + 4) & 0xFFFF)
    m.rset(10, (s + 5) & 0xFFFF)
    m.pc = m.rget(4)
    m.rset(4, frame_x)
    m.pta = frame_cc & 7  # flags unchanged


# ---------------------------------------------------------------------
# BIG CTB (sub 8) and CFB (sub 9) — B2.36.
# ---------------------------------------------------------------------
def _big_ctb(m, lenb, src, dst, dl):
    base = (lenb >> 4) + 2
    count = m.bget(1)  # AL = digit count
    v = 0
    for i in range(count):
        c = m.mr((src + i) & 0xFFFF)
        if c == 0:
            continue
        digit = c & 0x4F
        if digit > 15:
            digit -= 55
        v = v * base + digit
    for i in range(dl):
        m.mw((dst + i) & 0xFFFF, (v >> (8 * (dl - 1 - i))) & 0xFF)
    bits = 8 * dl
    masked = v & ((1 << bits) - 1)
    m.f["V"] = 1 if masked == 0 else 0
    m.f["M"] = 1 if masked & 0x80 else 0
    m.f["L"] = 0


def _big_cfb(m, lenb, template, valaddr, vl):
    base = (lenb >> 4) + 2
    dst_len = m.bget(1)  # AL
    pad = m.bget(3)  # BL
    v = 0
    for i in range(vl):
        v = (v << 8) | m.mr((valaddr + i) & 0xFFFF)
    a_out = (template - 1) & 0xFFFF
    pad_mode = False
    for i in range(dst_len - 1, -1, -1):
        p = (template + i) & 0xFFFF
        b = m.mr(p)
        if b & 0x7F not in (0x40, 0x23):
            continue
        if b & 0x7F == 0x23:
            pad_mode = True
        if v != 0:
            d = v % base
            v //= base
            a_out = (p - 1) & 0xFFFF
            out = 0x80 | (0x30 + d if d < 10 else 0x41 + d - 10)
        elif pad_mode:
            out = pad
        else:
            a_out = (p - 1) & 0xFFFF
            out = 0x80 | 0x30
        m.mw(p, out)
    m.f["F"] = 1 if v != 0 else 0
    m.rset(0, a_out)


# ---------------------------------------------------------------------
# PAGE (0x2E) — B2: page-table access. The monitor runs map 0; the
# load/store sub-ops move entries between the page RAM and memory.
# ---------------------------------------------------------------------
@op(0x2E)
def _page(m, op_):
    sel = m.fetch()
    sub = sel >> 4
    form = sel & 0xF
    cnt = m.fetch()
    n, mapn = cnt >> 3, cnt & 7
    if form == 0xC:
        addr = m.fetchw()
    elif form == 0xD:
        v0 = m.fetch()
        reg = v0 >> 4
        disp = _s8(m.fetch())
        m.fetch()  # padding zero byte per the encoding
        addr = (m.rget(reg & 0xE) + disp) & 0xFFFF
        raise Trap("PAGE register-indexed form untested here")
    else:
        raise Trap(f"PAGE form {form:#x}")
    if sub == 0:  # load entries 0..n from memory
        for i in range(n + 1):
            m.page_ram[mapn * 32 + i] = m.mr((addr + i) & 0xFFFF) & 0xFF
    elif sub == 1:  # store entries 0..n to memory
        for i in range(n + 1):
            m.mw((addr + i) & 0xFFFF, m.page_ram[mapn * 32 + i])
    elif sub == 2:  # load single entry n
        m.page_ram[mapn * 32 + n] = m.mr(addr) & 0xFF
    elif sub == 3:  # store single entry n
        m.mw(addr, m.page_ram[mapn * 32 + n])
    elif sub == 4:  # rotated full-map load
        for i in range(32):
            m.page_ram[mapn * 32 + ((n + i) % 32)] = m.mr((addr + i) & 0xFFFF) & 0xFF
    else:
        raise Trap(f"PAGE sub {sub}")


# ---------------------------------------------------------------------
# DMA (0x2F) — B2: channel register access. Vectors never enable a
# transfer; the register file round-trips are what is testable.
# ---------------------------------------------------------------------
@op(0x2F)
def _dma(m, op_):
    sel = m.fetch()
    reg, sub = (sel >> 4) & 0xE, sel & 0xF
    if sub == 0:
        m.dma["addr"] = m.rget(reg)
    elif sub == 1:
        m.rset(reg, m.dma["addr"])
    elif sub == 2:
        m.dma["count"] = m.rget(reg)
    elif sub == 3:
        m.rset(reg, m.dma["count"])
    elif sub in (4, 5):
        m.dma["dev"] = (sel >> 4) & 3
    elif sub == 6:
        raise Trap("DMA enable not modeled (no device)")
    elif sub == 7:
        m.dma["en"] = 0
    elif sub == 8:
        m.dma["ilvl"] = (sel >> 4) & 0xF
    else:
        raise Trap(f"DMA sub {sub} not modeled")


# ---------------------------------------------------------------------
# MEM sub-op 0: the record loader (B2.37 notes; stream layout
# [type][len][offset16][payload...][checksum], byte sum == 0 mod 256).
# ---------------------------------------------------------------------
def _mem_binload(m, sel):
    sspec, dspec = (sel >> 2) & 3, sel & 3
    if sspec == 0:
        base_ptr = m.fetchw()
    elif sspec == 2:
        b = m.fetch()
        base_ptr = m.rget((b >> 4) & 0xE)
    else:
        raise Trap("binload src spec")
    if dspec != 2:
        raise Trap("binload dst spec")
    rec_reg = m.fetch() & 0xF
    base = m.mrw(base_ptr)
    z = m.rget(rec_reg & 0xE)
    b0 = m.mr(z)
    if b0 == 0x80:
        m.rset(rec_reg & 0xE, (z + 1) & 0xFFFF)
        m.f["V"] = 1
        m.f["L"] = 1
        return
    if b0 > 1:
        m.f["F"] = 1
        return
    ln = m.mr((z + 1) & 0xFFFF)
    off = (m.mr((z + 2) & 0xFFFF) << 8) | m.mr((z + 3) & 0xFFFF)
    dst = (base + off) & 0xFFFF
    total = sum(m.mr((z + i) & 0xFFFF) for i in range(4))
    if b0 == 0:
        for i in range(ln):
            byt = m.mr((z + 4 + i) & 0xFFFF)
            total += byt
            m.mw((dst + i) & 0xFFFF, byt)
    else:
        total += sum(m.mr((z + 4 + i) & 0xFFFF) for i in range(ln))
        i = 0
        while i + 1 < ln:
            w = m.mrw((z + 4 + i) & 0xFFFF)
            t = (base + w) & 0xFFFF
            m.mww(t, (m.mrw(t) + dst) & 0xFFFF)
            i += 2
    total += m.mr((z + 4 + ln) & 0xFFFF)
    m.rset(0, dst)
    if total & 0xFF == 0:
        m.rset(rec_reg & 0xE, (z + 5 + ln) & 0xFFFF)
        if ln == 0:
            m.f["V"] = 1
    else:
        m.f["F"] = 1
