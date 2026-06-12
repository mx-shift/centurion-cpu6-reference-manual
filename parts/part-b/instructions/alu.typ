#import "../../../lib/instruction.typ": *

// Two-register ALU operations, one entry per operation (per mnemonic).
// Byte forms occupy rows 0x40-0x45 (register-register) with one-byte
// shorthands at 0x48-0x4F; word forms occupy 0x50-0x55 with CPU6
// memory/immediate sub-modes and one-byte shorthands at 0x58-0x5F.

// --- shared encodings -------------------------------------------------

// Register-register form: an 8-bit opcode then a [src][dst] selector byte.
#let _rr(mnem, opcode8, reg: "src") = encoding(
  "Register-register",
  applicability: "CPU4/5/6",
  asm: mnem + " <src>, <dst>",
  diagram: bitbox(
    ((bits: 8, value: opcode8),),
    ((name: "src", bits: 4), (name: "dst", bits: 4)),
  ),
)

// CPU6 word sub-modes: the low bit of each register nibble selects an
// immediate, direct, or indexed memory operand; a 16-bit word follows.
#let _rr-mem(mnem, opcode8) = encoding(
  "Immediate / direct / indexed",
  applicability: "CPU6",
  asm: mnem + "= <imm>, <dst>   " + mnem + "/ <addr>, <dst>   " + mnem + "- <ireg>, <disp>, <dst>",
  diagram: bitbox(
    ((bits: 8, value: opcode8),),
    ((name: "src|s", bits: 4), (name: "dst|d", bits: 4)),
    ((name: "imm / addr / disp", bits: 16),),
  ),
  decode: [
    ```cpu6
    // s,d = low bits of the source and destination nibbles:
    //   s=1,d=0  immediate: the word that follows is the operand
    //   s=0,d=1  direct:    operand at MemW[addr]
    //   s=1,d=1  indexed:   operand at MemW[R[src] + disp]
    // the remaining nibble bits name the registers
    ```
  ],
)

// Operation/flags shared text for the two arithmetic members.
#let _arith-flags(borrow: false) = flags-affected(
  fault: [signed overflow], link: if borrow [no borrow] else [carry],
  minus: "*", value: "*",
)
// Logical and transfer members touch only M and V.
#let _logic-flags = flags-affected(minus: "*", value: "*")

// =====================================================================
// Byte forms (0x40-0x45)
// =====================================================================

#instruction(
  "ADDB",
  qualifier: "(add byte)",
  summary: [
    Add the source byte register to the destination byte register; the
    8-bit sum replaces the destination.
  ],
  encodings: (_rr("ADDB", "01000000"),),
  operation: [
    ```cpu6
    result = R[src] + R[dst]
    R[dst] = result<7:0>
    FAULT  = SignedOverflow; LINK = Carry
    MINUS  = result<7>;      VALUE = IsZero(result<7:0>)
    ```
  ],
  flags: _arith-flags(),
  notes: [One-byte shorthand `AAB` (0x48) adds `AL` to `BL`.],
)

#instruction(
  "SUBB",
  qualifier: "(subtract byte)",
  summary: [
    Subtract the destination byte register from the source
    (`source − destination`); the difference replaces the destination.
  ],
  encodings: (_rr("SUBB", "01000001"),),
  operation: [
    ```cpu6
    result = R[src] - R[dst]
    R[dst] = result<7:0>
    FAULT  = SignedOverflow; LINK = NoBorrow
    MINUS  = result<7>;      VALUE = IsZero(result<7:0>)
    ```
  ],
  flags: _arith-flags(borrow: true),
  notes: [One-byte shorthand `SABB` (0x49) computes `AL − BL`.],
)

#instruction(
  "ANDB",
  qualifier: "(and byte)",
  summary: [Bitwise AND of the source and destination byte registers into the destination.],
  encodings: (_rr("ANDB", "01000010"),),
  operation: [
    ```cpu6
    R[dst] = R[src] AND R[dst]
    MINUS  = result<7>; VALUE = IsZero(result)   // F, L untouched
    ```
  ],
  flags: _logic-flags,
  notes: [One-byte shorthand `NABB` (0x4A) ANDs `AL` into `BL`.],
)

#instruction(
  "ORIB",
  qualifier: "(inclusive-or byte)",
  summary: [Bitwise inclusive OR of the source and destination byte registers into the destination.],
  encodings: (_rr("ORIB", "01000011"),),
  operation: [
    ```cpu6
    R[dst] = R[src] OR R[dst]
    MINUS  = result<7>; VALUE = IsZero(result)   // F, L untouched
    ```
  ],
  flags: _logic-flags,
)

#instruction(
  "OREB",
  qualifier: "(exclusive-or byte)",
  summary: [Bitwise exclusive OR of the source and destination byte registers into the destination.],
  encodings: (_rr("OREB", "01000100"),),
  operation: [
    ```cpu6
    R[dst] = R[src] XOR R[dst]
    MINUS  = result<7>; VALUE = IsZero(result)   // F, L untouched
    ```
  ],
  flags: _logic-flags,
)

#instruction(
  "XFRB",
  qualifier: "(transfer byte)",
  summary: [Copy the source byte register to the destination byte register.],
  encodings: (_rr("XFRB", "01000101"),),
  operation: [
    ```cpu6
    R[dst] = R[src]
    MINUS  = result<7>; VALUE = IsZero(result)   // F, L untouched
    ```
  ],
  flags: _logic-flags,
  notes: [
    One-byte shorthands `XAXB XAYB XABB XAZB XASB` (0x4B–0x4F) copy
    `AL` to `XL YL BL ZL SL`.
  ],
)

// =====================================================================
// Word forms (0x50-0x55) — register-register plus CPU6 memory sub-modes
// =====================================================================

#instruction(
  "ADD",
  qualifier: "(add word)",
  summary: [
    Add the source operand to the destination word register; the 16-bit
    sum replaces the destination. On the CPU6 the source may be an
    immediate, direct, or indexed memory operand.
  ],
  encodings: (_rr("ADD", "01010000"), _rr-mem("ADD", "01010000")),
  operation: [
    ```cpu6
    result = operand + R[dst]
    R[dst] = result<15:0>
    FAULT  = SignedOverflow; LINK = Carry
    MINUS  = result<15>;     VALUE = IsZero(result<15:0>)
    ```
  ],
  flags: _arith-flags(),
  notes: [One-byte shorthand `AAB` (0x58) adds `A` to `B`.],
)

#instruction(
  "SUB",
  qualifier: "(subtract word)",
  summary: [
    Subtract the destination word register from the source operand
    (`source − destination`); the difference replaces the destination.
    On the CPU6 the source may be an immediate, direct, or indexed
    memory operand.
  ],
  encodings: (_rr("SUB", "01010001"), _rr-mem("SUB", "01010001")),
  operation: [
    ```cpu6
    result = operand - R[dst]
    R[dst] = result<15:0>
    FAULT  = SignedOverflow; LINK = NoBorrow
    MINUS  = result<15>;     VALUE = IsZero(result<15:0>)
    ```
  ],
  flags: _arith-flags(borrow: true),
  notes: [One-byte shorthand `SAB` (0x59) computes `A − B`.],
)

#instruction(
  "AND",
  qualifier: "(and word)",
  summary: [
    Bitwise AND of the source operand and the destination word register
    into the destination. On the CPU6 the source may be an immediate,
    direct, or indexed memory operand.
  ],
  encodings: (_rr("AND", "01010010"), _rr-mem("AND", "01010010")),
  operation: [
    ```cpu6
    R[dst] = operand AND R[dst]
    MINUS  = result<15>; VALUE = IsZero(result)   // F, L untouched
    ```
  ],
  flags: _logic-flags,
  notes: [One-byte shorthand `NAB` (0x5A) ANDs `A` into `B`.],
)

#instruction(
  "ORI",
  qualifier: "(inclusive-or word)",
  summary: [
    Bitwise inclusive OR of the source operand and the destination word
    register into the destination. On the CPU6 the source may be an
    immediate, direct, or indexed memory operand.
  ],
  encodings: (_rr("ORI", "01010011"), _rr-mem("ORI", "01010011")),
  operation: [
    ```cpu6
    R[dst] = operand OR R[dst]
    MINUS  = result<15>; VALUE = IsZero(result)   // F, L untouched
    ```
  ],
  flags: _logic-flags,
)

#instruction(
  "ORE",
  qualifier: "(exclusive-or word)",
  summary: [
    Bitwise exclusive OR of the source operand and the destination word
    register into the destination. On the CPU6 the source may be an
    immediate, direct, or indexed memory operand.
  ],
  encodings: (_rr("ORE", "01010100"), _rr-mem("ORE", "01010100")),
  operation: [
    ```cpu6
    R[dst] = operand XOR R[dst]
    MINUS  = result<15>; VALUE = IsZero(result)   // F, L untouched
    ```
  ],
  flags: _logic-flags,
)

#instruction(
  "XFR",
  qualifier: "(transfer word)",
  summary: [
    Copy the source operand to the destination word register. On the
    CPU6 the source may be an immediate, direct, or indexed memory
    operand.
  ],
  encodings: (_rr("XFR", "01010101"), _rr-mem("XFR", "01010101")),
  operation: [
    ```cpu6
    R[dst] = operand
    MINUS  = result<15>; VALUE = IsZero(result)   // F, L untouched
    ```
  ],
  flags: _logic-flags,
  notes: [
    One-byte shorthands `XAX XAY XAB XAZ XAS` (0x5B–0x5F) copy `A` to
    `X Y B Z S`.
  ],
)
