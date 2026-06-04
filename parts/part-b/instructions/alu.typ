#import "../../../lib/instruction.typ": *

// Rows 0x40-0x45 (byte), 0x48-0x4F (byte one-byte forms),
// 0x50-0x55 (word), 0x58-0x5F (word one-byte forms).

#instruction(
  "ADDB / SUBB / ANDB / ORIB / OREB / XFRB",
  qualifier: "(two-register byte ALU)",
  summary: [
    Two-operand byte arithmetic and logic between any two 8-bit
    registers: the source operand combines with the destination
    operand and the result replaces the destination. SUBB computes
    source − destination. XFRB copies source to destination.
  ],
  encodings: (
    encoding(
      "Register-register",
      applicability: "CPU4/5/6",
      asm: "ADDB <src>, <dst>",
      diagram: bitbox(
        ((bits: 5, value: "01000"), (name: "op", bits: 3)),
        ((name: "src", bits: 4), (name: "dst", bits: 4)),
      ),
      decode: [
        ```cpu6
        op: 000 ADDB  001 SUBB  010 ANDB
            011 ORIB  100 OREB  101 XFRB
        ```
      ],
    ),
  ),
  operation: [
    ```cpu6
    a = R[src]; b = R[dst]
    ADDB: result = a + b          // F overflow, L carry
    SUBB: result = a - b          // F overflow, L = no-borrow
    ANDB: result = a AND b
    ORIB: result = a OR b         // inclusive
    OREB: result = a XOR b        // exclusive
    XFRB: result = a
    R[dst] = result<7:0>
    MINUS  = result<7>; VALUE = IsZero(result)
    ```
  ],
  flags: flags-affected(fault: [arith: overflow], link: [arith: carry],
    minus: "*", value: "*"),
  notes: [
    Row 0x48–0x4F packs the most common pairings into one byte:
    `AAB` (0x48, add `AL` to `BL`), `SABB` (0x49), `NABB` (0x4A,
    and), and `XAXB XAYB XABB XAZB XASB` (0x4B–0x4F, transfer `AL`
    to `XL YL BL ZL SL`).
  ],
)

#instruction(
  "ADD / SUB / AND / ORI / ORE / XFR",
  qualifier: "(two-register word ALU)",
  summary: [
    The 16-bit forms of the two-operand ALU row, between any two word
    registers. On the CPU6 the operand byte's low bits select extended
    sub-modes that pair a register with a memory or immediate operand.
  ],
  encodings: (
    encoding(
      "Register-register",
      applicability: "CPU4/5/6",
      asm: "ADD <src>, <dst>",
      diagram: bitbox(
        ((bits: 5, value: "01010"), (name: "op", bits: 3)),
        ((name: "src (even)", bits: 4), (name: "dst (even)", bits: 4)),
      ),
    ),
    encoding(
      "Immediate / direct / indexed",
      applicability: "CPU6",
      asm: "ADD= <imm>, <dst>   ADD/ <addr>, <dst>   ADD- <ireg>, <disp>, <dst>",
      diagram: bitbox(
        ((bits: 5, value: "01010"), (name: "op", bits: 3)),
        ((name: "src|s", bits: 4), (name: "dst|d", bits: 4)),
        ((name: "imm / addr / disp", bits: 16),),
      ),
      decode: [
        ```cpu6
        // mode = (s,d) low bits of the two nibbles:
        //   s=1,d=0  immediate word follows
        //   s=0,d=1  direct: operand at MemW[addr]
        //   s=1,d=1  indexed: operand at MemW[R[src] + disp]
        // the remaining nibble bits name the registers
        ```
      ],
    ),
  ),
  operation: [
    ```cpu6
    // as the byte row, at word width
    ```
  ],
  flags: flags-affected(fault: [arith: overflow], link: [arith: carry],
    minus: "*", value: "*"),
  notes: [
    Row 0x58–0x5F: one-byte word forms `AAB SAB NAB` (A op B) and
    `XAX XAY XAB XAZ XAS` (transfer A to X Y B Z S).
  ],
)
