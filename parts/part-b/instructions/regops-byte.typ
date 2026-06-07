#import "../../../lib/instruction.typ": *

// Rows 0x20-0x2D: single-register byte operations (register-constant
// form) and their A-register one-byte aliases.

#instruction(
  "INRB / DCRB",
  qualifier: "(increment/decrement byte register)",
  summary: [
    Add to or subtract from an 8-bit register an immediate amount in
    the range 1–16, encoded as the low operand nibble plus one.
    The CPU6 accepts any amount; CPU4/5 only step by 1.
  ],
  encodings: (
    encoding(
      "Register-constant",
      applicability: "CPU4/5/6 (n > 1: CPU6)",
      asm: "INRB <reg>, <n>",
      diagram: bitbox(
        ((bits: 8, value: "0010000d"),),
        ((name: "reg", bits: 4), (name: "n−1", bits: 4)),
      ),
      decode: [
        ```cpu6
        d   = opcode<0>          // 0 = INRB, 1 = DCRB
        reg = operand<7:4>       // register-file byte index
        n   = operand<3:0> + 1
        ```
      ],
    ),
  ),
  operation: [
    ```cpu6
    result = R[reg] ± n
    R[reg] = result<7:0>
    FAULT  = SignedOverflow
    MINUS  = result<7>
    VALUE  = IsZero(result<7:0>)
    ```
  ],
  flags: flags-affected(fault: [overflow], minus: "*", value: "*"),
  notes: [
    `INAB`/`DCAB` (0x28/0x29) are one-byte aliases operating on `AL`
    with n = 1. The assembler also accepts `INC`/`DEC` for the byte
    forms.
  ],
)

#instruction(
  "CLRB / IVRB",
  qualifier: "(clear / invert byte register)",
  summary: [
    CLRB writes the constant field directly to the register (clearing
    it when the field is 0 — the common use). IVRB writes the one's
    complement of the register, then adds the constant field, allowing
    `IVRB r,1` to negate.
  ],
  encodings: (
    encoding(
      "Register-constant",
      applicability: "CPU4/5/6",
      asm: "CLRB <reg>[, <n>]",
      diagram: bitbox(
        ((bits: 8, value: "0010001d"),),
        ((name: "reg", bits: 4), (name: "n", bits: 4)),
      ),
      decode: [
        ```cpu6
        d = opcode<0>   // 0 = CLRB, 1 = IVRB
        ```
      ],
    ),
  ),
  operation: [
    ```cpu6
    result = n                  // CLRB (0x22)
    result = (~R[reg]) + n      // IVRB (0x23): carry/overflow from
    R[reg] = result<7:0>        // the add land in L and F
    ```
  ],
  flags: flags-affected(fault: [CLRB: cleared; IVRB: add overflow],
    link: [CLRB: cleared; IVRB: add carry],
    minus: "*", value: "*"),
  notes: [
    `CLAB`/`IVAB` (0x2A/0x2B) are the one-byte `AL` aliases with
    n = 0.
  ],
)

#instruction(
  "SRRB / SLRB / RRRB / RLRB",
  qualifier: "(byte shifts and rotates)",
  summary: [
    Shift or rotate an 8-bit register by 1–16 bit positions (constant
    field + 1). SRRB is an arithmetic right shift (sign-propagating);
    SLRB shifts left; RRRB and RLRB rotate through the link flag,
    forming a 9-bit rotate.
  ],
  encodings: (
    encoding(
      "Register-constant",
      applicability: "CPU4/5/6 (n > 1: CPU6)",
      asm: "SRRB <reg>, <n>",
      diagram: bitbox(
        ((bits: 8, value: "001001ss"),),
        ((name: "reg", bits: 4), (name: "n−1", bits: 4)),
      ),
      decode: [
        ```cpu6
        ss: 00 = SRRB (0x24)  01 = SLRB (0x25)
            10 = RRRB (0x26)  11 = RLRB (0x27)
        ```
      ],
    ),
  ),
  operation: [
    ```cpu6
    // SRRB: arithmetic right; last bit out enters L
    // SLRB: left; L receives the last bit shifted out of bit 7,
    //       F set if the sign changed at any step (a shift by the
    //       full width drains the sign itself: SLR 0xFFFF by 16
    //       faults — microcode-verified)
    // RRRB: 9-bit rotate through L; F cleared
    // RLRB: 9-bit rotate through L; F set on sign change per step,
    //       like SLRB
    ```
  ],
  flags: flags-affected(fault: [SLRB: sign change], link: [last bit out],
    minus: "*", value: "*"),
  notes: [
    `SRAB`/`SLAB` (0x2C/0x2D) are the one-byte `AL` shift aliases with
    n = 1.
  ],
)
