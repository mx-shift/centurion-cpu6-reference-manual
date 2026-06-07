"""The on-target conformance kernel.

A small CPU6 program, loaded into RAM through TOS's M command and
started with G, that executes host-supplied test programs and reports
the resulting machine state over the console MUX port.

Wire protocol (all ASCII, uppercase hex, CR-terminated):

  kernel -> host on start:   "CK1\r\n"
  host   -> kernel:          "P"          ping
  kernel -> host:            "+"
  host   -> kernel:
      ':' A(4) B(4) X(4) Y(4) Z(4) S(4)   initial registers
          MEMADDR(4) MEMLEN(4) CODELEN(4) (lengths >= 1)
          membytes(2*MEMLEN) codebytes(2*CODELEN)
          CKSUM(2) CR
      CKSUM = two's-sum of all decoded binary bytes, mod 256.
  kernel: writes membytes at MEMADDR, copies code to the slot, loads
      the registers, jumps to the slot. The host must end the code
      with JMP /CAPTURE (kernel.CAPTURE). On bad checksum: "!".
  kernel -> host after capture:
      '=' FLAGS(2) A(4) B(4) X(4) Y(4) Z(4) S(4)
          membytes(2*MEMLEN re-read) CKSUM(2) CR LF
      FLAGS bit3..0 = F L M V, each sampled with its conditional
      branch (the only architecturally clean way to read live flags).

The kernel itself uses only instructions whose encodings it verifies
against the manual's opcode index (see asm.py) and whose semantics
the tier-0 smoke tests cover first.
"""

from asm import A, AL, B, BL, S, X, Y, YL, Z, ZL, Asm

ORG = 0x4000
SLOT = 0x4D00  # test code lands here; host appends JMP /CAPTURE
SLOT_MAX = 0xC0
DATA = 0x4E00
KSTACK = 0x5F00

MUX_ST = 0xF200
MUX_DAT = 0xF201

# Data-area layout.
INREGS = DATA  # 12 bytes: A B X Y Z S (big-endian words)
MEMA = DATA + 12  # 2: memory window address
MEMLEN = DATA + 14  # 2: window length (word; received as 4 hex)
CODELEN = DATA + 16  # 2
FLAGS = DATA + 18  # 1: captured F<<3|L<<2|M<<1|V
OUTREGS = DATA + 20  # 12
CNT = DATA + 32  # 2: scratch loop counter


def build():
    a = Asm(ORG)

    # -- entry ------------------------------------------------------
    a.label("ENTRY")
    a.lda_imm(KSTACK)
    a.xfr(A, S)
    for ch in "CK1\r\n":
        a.ldbb_imm(ord(ch))
        a.jsr("PUTC")

    # -- main dispatch ------------------------------------------------
    a.label("MAIN")
    a.jsr("GETC")  # char in AL
    a.ldbb_imm(ord(":"))
    a.subb_rr(AL, BL)  # BL = AL - ':' ; V set when equal
    a.bz("FRAME")
    a.ldbb_imm(ord("P"))
    a.subb_rr(AL, BL)
    a.bnz("MAIN")
    a.ldbb_imm(ord("+"))
    a.jsr("PUTC")
    a.jmp("MAIN")

    # -- frame receive --------------------------------------------------
    a.label("FRAME")
    a.clrb(ZL, 0)  # ZL = running checksum
    # 18 header bytes: regs(12) mema(2) memlen(2) codelen(2)
    a.ldx_imm(INREGS)
    a.lda_imm(18)
    a.sta_dir(CNT)
    a.label("RXHDR")
    a.lda_dir(CNT)
    a.bz("RXMEM0")
    a.dcr(A, 1)
    a.sta_dir(CNT)
    a.jsr("GETHEX2")  # byte in AL (YL, BL clobbered)
    a.addb_rr(AL, ZL)  # checksum
    a.stab_via(X)
    a.inr(X, 1)
    a.jmp("RXHDR")

    # memory window bytes -> [MEMA]
    a.label("RXMEM0")
    a.ldx_dir(MEMA)
    a.lda_dir(MEMLEN)
    a.sta_dir(CNT)
    a.label("RXMEM")
    a.lda_dir(CNT)
    a.bz("RXCODE0")
    a.dcr(A, 1)
    a.sta_dir(CNT)
    a.jsr("GETHEX2")
    a.addb_rr(AL, ZL)
    a.stab_via(X)
    a.inr(X, 1)
    a.jmp("RXMEM")

    # code bytes -> SLOT
    a.label("RXCODE0")
    a.ldx_imm(SLOT)
    a.lda_dir(CODELEN)
    a.sta_dir(CNT)
    a.label("RXCODE")
    a.lda_dir(CNT)
    a.bz("RXSUM")
    a.dcr(A, 1)
    a.sta_dir(CNT)
    a.jsr("GETHEX2")
    a.addb_rr(AL, ZL)
    a.stab_via(X)
    a.inr(X, 1)
    a.jmp("RXCODE")

    # checksum + CR
    a.label("RXSUM")
    a.jsr("GETHEX2")
    a.subb_rr(AL, ZL)  # ZL = frame_sum - our_sum
    a.bz("RXCR")
    a.ldbb_imm(ord("!"))
    a.jsr("PUTC")
    a.jmp("MAIN")
    a.label("RXCR")
    a.jsr("GETC")  # consume the CR

    # -- execute ----------------------------------------------------
    # Load Y, Z, S through A (XFR is the only path to them), then the
    # directly loadable registers, A last. After S is loaded the
    # kernel stack is gone: JMP only until CAPTURE restores it.
    # CLRB first: it clears F and L (manual B2), and everything after
    # is mv-only, so the slot always starts with F=0 L=0 and M/V from
    # the final load of A — deterministic entry flags the model mirrors.
    a.clrb(AL, 0)
    a.lda_dir(INREGS + 6)
    a.xfr(A, Y)
    a.lda_dir(INREGS + 8)
    a.xfr(A, Z)
    a.lda_dir(INREGS + 10)
    a.xfr(A, S)
    a.ldb_dir(INREGS + 2)
    a.ldx_dir(INREGS + 4)
    a.lda_dir(INREGS + 0)
    a.jmp(SLOT)

    # -- capture ------------------------------------------------------
    # Flag tree first: conditional branches are the only flag readers
    # and (per the manual) affect no flags themselves. Each leaf
    # records F<<3|L<<2|M<<1|V before anything else runs.
    a.label("CAPTURE")
    a.bf("CF1")
    # F=0
    a.bl("C0L1")
    a.bm("C00M1")
    a.bz("LEAF1")  # F0 L0 M0 V1
    a.jmp("LEAF0")  # F0 L0 M0 V0
    a.label("C00M1")
    a.bz("LEAF3")  # F0 L0 M1 V1
    a.jmp("LEAF2")
    a.label("C0L1")
    a.bm("C01M1")
    a.bz("LEAF5")  # F0 L1 M0 V1
    a.jmp("LEAF4")
    a.label("C01M1")
    a.bz("LEAF7")
    a.jmp("LEAF6")
    for n in range(8):
        a.label(f"LEAF{n}")
        a.sta_dir(OUTREGS + 0)
        a.ldab_imm(n)
        a.stab_dir(FLAGS)
        a.jmp("SAVE")
    a.label("CF1")
    a.bl("C1L1")
    a.bm("C10M1")
    a.bz("LEAF9")
    a.jmp("LEAF8")
    a.label("C10M1")
    a.bz("LEAF11")
    a.jmp("LEAF10")
    a.label("C1L1")
    a.bm("C11M1")
    a.bz("LEAF13")
    a.jmp("LEAF12")
    a.label("C11M1")
    a.bz("LEAF15")
    a.jmp("LEAF14")
    # Leaves: save A before the leaf number lands in AL. Two banks so
    # every tree branch stays within the signed-8 displacement.
    for n in range(8, 16):
        a.label(f"LEAF{n}")
        a.sta_dir(OUTREGS + 0)
        a.ldab_imm(n)
        a.stab_dir(FLAGS)
        a.jmp("SAVE")

    # Register capture; every store clobbers M/V but flags are done.
    a.label("SAVE")
    a.stb_dir(OUTREGS + 2)
    a.stx_dir(OUTREGS + 4)
    a.xfr(Y, A)
    a.sta_dir(OUTREGS + 6)
    a.xfr(Z, A)
    a.sta_dir(OUTREGS + 8)
    a.xfr(S, A)
    a.sta_dir(OUTREGS + 10)
    a.lda_imm(KSTACK)  # kernel stack back
    a.xfr(A, S)

    # -- respond ------------------------------------------------------
    a.ldbb_imm(ord("="))
    a.jsr("PUTC")
    a.clrb(ZL, 0)
    a.ldab_dir(FLAGS)
    a.addb_rr(AL, ZL)
    a.jsr("PUTHEX2")
    # 12 register bytes
    a.ldx_imm(OUTREGS)
    a.lda_imm(12)
    a.sta_dir(CNT)
    a.label("TXREG")
    a.lda_dir(CNT)
    a.bz("TXMEM0")
    a.dcr(A, 1)
    a.sta_dir(CNT)
    a.ldab_via(X)
    a.addb_rr(AL, ZL)
    a.jsr("PUTHEX2")
    a.inr(X, 1)
    a.jmp("TXREG")
    # memory window re-read
    a.label("TXMEM0")
    a.ldx_dir(MEMA)
    a.lda_dir(MEMLEN)
    a.sta_dir(CNT)
    a.label("TXMEM")
    a.lda_dir(CNT)
    a.bz("TXSUM")
    a.dcr(A, 1)
    a.sta_dir(CNT)
    a.ldab_via(X)
    a.addb_rr(AL, ZL)
    a.jsr("PUTHEX2")
    a.inr(X, 1)
    a.jmp("TXMEM")
    a.label("TXSUM")
    a.xfrb_rr(ZL, AL)
    a.jsr("PUTHEX2")
    a.ldbb_imm(0x0D)
    a.jsr("PUTC")
    a.ldbb_imm(0x0A)
    a.jsr("PUTC")
    a.jmp("MAIN")

    # -- console primitives ---------------------------------------------
    # GETC: poll RX-full (status bit 0), read the byte into AL.
    a.label("GETC")
    a.ldab_dir(MUX_ST)
    a.srrb(AL, 1)  # bit 0 -> L
    a.bnl("GETC")
    a.ldab_dir(MUX_DAT)
    a.rsr()

    # PUTC: char in BL; poll TX-ready (status bit 1), write.
    a.label("PUTC")
    a.ldab_dir(MUX_ST)
    a.srrb(AL, 2)  # bit 1 -> L
    a.bnl("PUTC")
    a.xfrb_rr(BL, AL)
    a.stab_dir(MUX_DAT)
    a.rsr()

    # GETNIB: read one hex digit (uppercase) -> BL.
    a.label("GETNIB")
    a.jsr("GETC")
    a.ldbb_imm(0x3A)  # ':' — first char past '9'
    a.subb_rr(AL, BL)  # BL = AL - 0x3A, M set when AL < ':'
    a.bm("GNDIG")
    a.ldbb_imm(0x37)  # 'A'-10
    a.subb_rr(AL, BL)
    a.rsr()
    a.label("GNDIG")
    a.ldbb_imm(0x30)
    a.subb_rr(AL, BL)
    a.rsr()

    # GETHEX2: two digits -> AL (clobbers BL, YL).
    a.label("GETHEX2")
    a.jsr("GETNIB")
    a.xfrb_rr(BL, YL)
    a.slrb(YL, 4)
    a.jsr("GETNIB")
    a.xfrb_rr(YL, AL)
    a.orib_rr(BL, AL)
    a.rsr()

    # PUTHEX2: AL -> two uppercase digits (clobbers AL, BL, YL).
    a.label("PUTHEX2")
    a.xfrb_rr(AL, YL)
    a.srrb(AL, 4)  # arithmetic: mask the sign fill
    a.ldbb_imm(0x0F)
    a.andb_rr(BL, AL)
    a.jsr("PUTNIB")
    a.xfrb_rr(YL, AL)
    a.ldbb_imm(0x0F)
    a.andb_rr(BL, AL)
    a.jsr("PUTNIB")
    a.rsr()

    a.label("PUTNIB")
    a.ldbb_imm(0x0A)
    a.subb_rr(AL, BL)  # BL = AL - 10, M set when digit
    a.bm("PNDIG")
    a.ldbb_imm(0x37)
    a.jmp("PNADD")
    a.label("PNDIG")
    a.ldbb_imm(0x30)
    a.label("PNADD")
    a.addb_rr(BL, AL)  # AL += base
    a.xfrb_rr(AL, BL)
    a.jsr("PUTC")
    a.rsr()

    image = a.finish()
    assert ORG + len(image) < SLOT, f"kernel overruns slot: {len(image)}"
    return image, a.labels


if __name__ == "__main__":
    img, labels = build()
    print(f"kernel: {len(img)} bytes at {ORG:04X}")
    for k in ("ENTRY", "MAIN", "CAPTURE", "GETC", "PUTC"):
        print(f"  {k:8} {labels[k]:04X}")
