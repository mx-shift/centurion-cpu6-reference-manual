#import "../../../lib/instruction.typ": *

// Single-register byte operations (register-constant form), one entry per
// operation. Rows 0x20-0x27; one-byte A-register aliases at 0x28-0x2D.

// Register-constant byte encoding: an 8-bit opcode then a [reg][const]
// byte. `field` is the constant's meaning ("n−1" for count-biased
// operations, "n" for clear/invert).
#let _rc(mnem, opcode8, field: "n−1", applic: "CPU4/5/6 (n > 1: CPU6)") = encoding(
  "Register-constant",
  applicability: applic,
  asm: mnem + " <reg>, <n>",
  diagram: bitbox(
    ((bits: 8, value: opcode8),),
    ((name: "reg", bits: 4), (name: field, bits: 4)),
  ),
)

#instruction(
  "INRB",
  qualifier: "(increment byte register)",
  summary: [
    Add an immediate amount in the range 1–16 (the constant field plus
    one) to an 8-bit register. The CPU6 accepts any amount; CPU4/5 only
    step by 1.
  ],
  encodings: (_rc("INRB", "00100000"),),
  operation: [
    ```cpu6
    result = R[reg] + n          // n = field + 1
    R[reg] = result<7:0>
    FAULT  = SignedOverflow
    MINUS  = result<7>; VALUE = IsZero(result<7:0>)
    ```
  ],
  flags: flags-affected(fault: [overflow], minus: "*", value: "*"),
  notes: [
    `INAB` (0x28) is a one-byte alias operating on `AL` with n = 1. The
    assembler also accepts `INC` for the byte form.
  ],
)

#instruction(
  "DCRB",
  qualifier: "(decrement byte register)",
  summary: [
    Subtract an immediate amount in the range 1–16 (the constant field
    plus one) from an 8-bit register. The CPU6 accepts any amount;
    CPU4/5 only step by 1.
  ],
  encodings: (_rc("DCRB", "00100001"),),
  operation: [
    ```cpu6
    result = R[reg] - n          // n = field + 1
    R[reg] = result<7:0>
    FAULT  = SignedOverflow
    MINUS  = result<7>; VALUE = IsZero(result<7:0>)
    ```
  ],
  flags: flags-affected(fault: [overflow], minus: "*", value: "*"),
  notes: [
    `DCAB` (0x29) is a one-byte alias operating on `AL` with n = 1. The
    assembler also accepts `DEC` for the byte form.
  ],
)

#instruction(
  "CLRB",
  qualifier: "(clear byte register)",
  summary: [
    Write the constant field directly to the register — clearing it when
    the field is 0, the common use.
  ],
  encodings: (_rc("CLRB", "00100010", field: "n", applic: "CPU4/5/6"),),
  operation: [
    ```cpu6
    R[reg] = n                   // n = field (0..15)
    FAULT  = 0; LINK = 0
    MINUS  = result<7>; VALUE = IsZero(result<7:0>)
    ```
  ],
  flags: flags-affected(fault: [cleared], link: [cleared], minus: "*", value: "*"),
  notes: [`CLAB` (0x2A) is the one-byte `AL` alias with n = 0.],
)

#instruction(
  "IVRB",
  qualifier: "(invert byte register)",
  summary: [
    Write the one's complement of the register, then add the constant
    field. `IVRB r, 1` therefore negates the register.
  ],
  encodings: (_rc("IVRB", "00100011", field: "n", applic: "CPU4/5/6"),),
  operation: [
    ```cpu6
    result = (~R[reg]) + n       // n = field (0..15)
    R[reg] = result<7:0>
    // n = 0 is a pure complement: L and F untouched.
    // n >= 1: the add's carry and signed overflow land in L and F.
    MINUS  = result<7>; VALUE = IsZero(result<7:0>)
    ```
  ],
  flags: flags-affected(fault: [n ≥ 1: add overflow], link: [n ≥ 1: add carry],
    minus: "*", value: "*"),
  notes: [
    `IVAB` (0x2B) is the one-byte `AL` alias with n = 0 — it therefore
    preserves L and F.
  ],
)

#instruction(
  "SRRB",
  qualifier: "(shift right byte register)",
  summary: [
    Arithmetic (sign-propagating) right shift of an 8-bit register by
    1–16 positions (the constant field plus one).
  ],
  encodings: (_rc("SRRB", "00100100"),),
  operation: [
    ```cpu6
    // arithmetic right shift by n; the last bit shifted out enters L
    R[reg] = ArithRightShift(R[reg], n)
    LINK   = last bit out;  FAULT preserved
    MINUS  = result<7>;     VALUE = IsZero(result<7:0>)
    ```
  ],
  flags: flags-affected(link: [last bit out], minus: "*", value: "*"),
  notes: [`SRAB` (0x2C) is the one-byte `AL` alias with n = 1.],
)

#instruction(
  "SLRB",
  qualifier: "(shift left byte register)",
  summary: [Left shift of an 8-bit register by 1–16 positions (the constant field plus one).],
  encodings: (_rc("SLRB", "00100101"),),
  operation: [
    ```cpu6
    R[reg] = LeftShift(R[reg], n)
    LINK   = last bit out of bit 7
    // F set if the sign changed at any step (a shift by the full width
    // drains the sign itself: SLRB 0xFF by 8 faults), else cleared.
    MINUS  = result<7>; VALUE = IsZero(result<7:0>)
    ```
  ],
  flags: flags-affected(fault: [sign change], link: [last bit out],
    minus: "*", value: "*"),
  notes: [`SLAB` (0x2D) is the one-byte `AL` alias with n = 1.],
)

#instruction(
  "RRRB",
  qualifier: "(rotate right byte register)",
  summary: [
    Rotate an 8-bit register right through the link flag by 1–16
    positions (the constant field plus one), forming a 9-bit rotate.
  ],
  encodings: (_rc("RRRB", "00100110"),),
  operation: [
    ```cpu6
    // 9-bit rotate right through L
    {R[reg], LINK} = RotateRight({R[reg], LINK}, n)
    FAULT preserved
    MINUS = result<7>; VALUE = IsZero(result<7:0>)
    ```
  ],
  flags: flags-affected(link: [rotated through], minus: "*", value: "*"),
)

#instruction(
  "RLRB",
  qualifier: "(rotate left byte register)",
  summary: [
    Rotate an 8-bit register left through the link flag by 1–16
    positions (the constant field plus one), forming a 9-bit rotate.
  ],
  encodings: (_rc("RLRB", "00100111"),),
  operation: [
    ```cpu6
    // 9-bit rotate left through L
    {R[reg], LINK} = RotateLeft({R[reg], LINK}, n)
    // F written on per-step sign change, like SLRB
    MINUS = result<7>; VALUE = IsZero(result<7:0>)
    ```
  ],
  flags: flags-affected(fault: [sign change], link: [rotated through],
    minus: "*", value: "*"),
)
