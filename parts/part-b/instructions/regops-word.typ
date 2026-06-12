#import "../../../lib/instruction.typ": *

// Single-operand word operations (row 0x30-0x37), one entry per
// operation. Each has the register-constant form plus the CPU6 memory
// direct and memory indexed forms; A/X one-byte aliases live at
// 0x38-0x3F.

// The three word encodings shared by every operation in the row. `field`
// is the constant's meaning ("n−1" for count-biased operations, "n" for
// clear/invert).
#let _word-encs(mnem, opcode8, field: "n−1") = (
  encoding(
    "Register-constant",
    applicability: "CPU4/5/6 (counts > 1 and memory forms: CPU6)",
    asm: mnem + " <reg>, <n>",
    diagram: bitbox(
      ((bits: 8, value: opcode8),),
      ((name: "reg (even)", bits: 4), (name: field, bits: 4)),
    ),
  ),
  encoding(
    "Memory direct",
    applicability: "CPU6",
    asm: mnem + "/ <addr>[, <n>]",
    diagram: bitbox(
      ((bits: 8, value: opcode8),),
      ((bits: 4, value: "0001"), (name: field, bits: 4)),
      ((name: "addr", bits: 16),),
    ),
    decode: [
      ```cpu6
      // odd register nibble 1: operate on MemW[addr]
      ```
    ],
  ),
  encoding(
    "Memory indexed",
    applicability: "CPU6",
    asm: mnem + "- <ireg>, <disp>[, <n>]",
    diagram: bitbox(
      ((bits: 8, value: opcode8),),
      ((name: "2·ireg+1", bits: 4), (name: field, bits: 4)),
      ((name: "disp", bits: 16),),
    ),
    decode: [
      ```cpu6
      // odd register nibbles 3,5,7,…: operate on MemW[R[ireg] + disp];
      // nibble 3 = B, 5 = X, 7 = Y, … . A cannot index (nibble 1 is the
      // direct form). The 16-bit displacement always follows, 0 when
      // omitted.
      ```
    ],
  ),
)

#instruction(
  "INR",
  qualifier: "(increment word register or memory)",
  summary: [
    Add an immediate amount in the range 1–16 (the constant field plus
    one) to a 16-bit register or memory word.
  ],
  encodings: _word-encs("INR", "00110000"),
  operation: [
    ```cpu6
    operand = R[reg]  or  MemW[ea]
    result  = operand + n              // n = field + 1
    writeback result
    FAULT   = SignedOverflow
    MINUS   = result<15>; VALUE = IsZero(result<15:0>)
    ```
  ],
  flags: flags-affected(fault: [overflow], minus: "*", value: "*"),
  notes: [
    `INA` (0x38) is the one-byte `A` alias (n = 1) and `INX` (0x3E)
    steps `X` by 1 (microcode-verified — by 1, not by the word size,
    despite the name). The assembler also accepts `INC`.

    The memory forms were verified instruction-by-instruction against the
    microcode simulator (optest suite, tests 30–37): an odd register
    nibble means a 16-bit address word always follows — used directly for
    nibble 1, and added to the selected index register for higher odd
    nibbles. This applies to every operation in the row.
  ],
)

#instruction(
  "DCR",
  qualifier: "(decrement word register or memory)",
  summary: [
    Subtract an immediate amount in the range 1–16 (the constant field
    plus one) from a 16-bit register or memory word.
  ],
  encodings: _word-encs("DCR", "00110001"),
  operation: [
    ```cpu6
    operand = R[reg]  or  MemW[ea]
    result  = operand - n              // n = field + 1
    writeback result
    FAULT   = SignedOverflow
    MINUS   = result<15>; VALUE = IsZero(result<15:0>)
    ```
  ],
  flags: flags-affected(fault: [overflow], minus: "*", value: "*"),
  notes: [
    `DCA` (0x39) is the one-byte `A` alias (n = 1) and `DCX` (0x3F)
    steps `X` by 1 (microcode-verified). The assembler also accepts
    `DEC`.
  ],
)

#instruction(
  "CLR",
  qualifier: "(clear word register or memory)",
  summary: [Write the constant field directly to a 16-bit register or memory word — clearing it when the field is 0.],
  encodings: _word-encs("CLR", "00110010", field: "n"),
  operation: [
    ```cpu6
    result = n                         // n = field (0..15)
    writeback result
    FAULT  = 0; LINK = 0
    MINUS  = result<15>; VALUE = IsZero(result<15:0>)
    ```
  ],
  flags: flags-affected(fault: [cleared], link: [cleared], minus: "*", value: "*"),
  notes: [`CLA` (0x3A) is the one-byte `A` alias (n = 0). The assembler also accepts `CAD`.],
)

#instruction(
  "IVR",
  qualifier: "(invert word register or memory)",
  summary: [
    Write the one's complement of the operand, then add the constant
    field. `IVR r, 1` therefore negates the operand.
  ],
  encodings: _word-encs("IVR", "00110011", field: "n"),
  operation: [
    ```cpu6
    operand = R[reg]  or  MemW[ea]
    result  = (~operand) + n           // n = field (0..15)
    writeback result
    // n = 0 is a pure complement: L and F untouched.
    // n >= 1: the add's carry and signed overflow land in L and F.
    MINUS   = result<15>; VALUE = IsZero(result<15:0>)
    ```
  ],
  flags: flags-affected(fault: [n ≥ 1: add overflow], link: [n ≥ 1: add carry],
    minus: "*", value: "*"),
  notes: [`IVA` (0x3B) is the one-byte `A` alias (n = 0). The assembler also accepts `IAD` or `NOT`.],
)

#instruction(
  "SRR",
  qualifier: "(shift right word register or memory)",
  summary: [Arithmetic (sign-propagating) right shift of a 16-bit register or memory word by 1–16 positions (the constant field plus one).],
  encodings: _word-encs("SRR", "00110100"),
  operation: [
    ```cpu6
    operand = R[reg]  or  MemW[ea]
    result  = ArithRightShift(operand, n)
    writeback result
    LINK    = last bit out;  FAULT preserved
    MINUS   = result<15>;    VALUE = IsZero(result<15:0>)
    ```
  ],
  flags: flags-affected(link: [last bit out], minus: "*", value: "*"),
  notes: [`SRA` (0x3C) is the one-byte `A` alias (n = 1). The assembler also accepts `SHR`.],
)

#instruction(
  "SLR",
  qualifier: "(shift left word register or memory)",
  summary: [Left shift of a 16-bit register or memory word by 1–16 positions (the constant field plus one).],
  encodings: _word-encs("SLR", "00110101"),
  operation: [
    ```cpu6
    operand = R[reg]  or  MemW[ea]
    result  = LeftShift(operand, n)
    writeback result
    LINK    = last bit out of bit 15
    // F set if the sign changed at any step (a shift by the full width
    // drains the sign itself: SLR 0xFFFF by 16 faults), else cleared.
    MINUS   = result<15>; VALUE = IsZero(result<15:0>)
    ```
  ],
  flags: flags-affected(fault: [sign change], link: [last bit out],
    minus: "*", value: "*"),
  notes: [`SLA` (0x3D) is the one-byte `A` alias (n = 1). The assembler also accepts `SHL`.],
)

#instruction(
  "RRR",
  qualifier: "(rotate right word register or memory)",
  summary: [Rotate a 16-bit register or memory word right through the link flag by 1–16 positions (the constant field plus one), forming a 17-bit rotate.],
  encodings: _word-encs("RRR", "00110110"),
  operation: [
    ```cpu6
    operand = R[reg]  or  MemW[ea]
    {result, LINK} = RotateRight({operand, LINK}, n)
    writeback result
    FAULT preserved
    MINUS = result<15>; VALUE = IsZero(result<15:0>)
    ```
  ],
  flags: flags-affected(link: [rotated through], minus: "*", value: "*"),
  notes: [The assembler also accepts `RTR`.],
)

#instruction(
  "RLR",
  qualifier: "(rotate left word register or memory)",
  summary: [Rotate a 16-bit register or memory word left through the link flag by 1–16 positions (the constant field plus one), forming a 17-bit rotate.],
  encodings: _word-encs("RLR", "00110111"),
  operation: [
    ```cpu6
    operand = R[reg]  or  MemW[ea]
    {result, LINK} = RotateLeft({operand, LINK}, n)
    writeback result
    // F written on per-step sign change, like SLR
    MINUS = result<15>; VALUE = IsZero(result<15:0>)
    ```
  ],
  flags: flags-affected(fault: [sign change], link: [rotated through],
    minus: "*", value: "*"),
  notes: [The assembler also accepts `RTL`.],
)
