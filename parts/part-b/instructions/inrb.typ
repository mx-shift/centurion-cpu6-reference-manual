#import "../../../lib/instruction.typ": *

#instruction(
  "INRB",
  summary: [
    Increment Register (byte) adds an immediate value in the range 1–16
    to an 8-bit register and writes the result back to that register.
    The condition flags are updated from the result.
  ],
  encodings: (
    encoding(
      "Register-constant",
      applicability: "CPU4/5/6",
      asm: "INRB <reg>, <n>",
      diagram: bitbox(
        ((bits: 8, value: "00100000"),),
        ((name: "reg", bits: 4), (name: "n−1", bits: 4)),
      ),
      decode: [
        ```cpu6
        reg = operand<7:4>    // register-file byte index
        n   = operand<3:0> + 1
        ```
      ],
    ),
  ),
  syntax: [
    `INRB <reg>, <n>`

    where:

    #syntax-field("<reg>", [
      Any 8-bit register (`AU`, `AL`, `BU`, `BL`, …): the 4-bit
      register-file byte index of the operand.
    ])
    #syntax-field("<n>", [
      The amount to add, 1–16. If omitted, the assembler encodes 1
      (a constant field of 0). The alias `INC <reg>` is accepted.
    ])
  ],
  operation: [
    ```cpu6
    result = R[reg] + n
    R[reg] = result<7:0>
    FAULT  = Overflow(R[reg], n)   // signed overflow
    MINUS  = result<7>
    VALUE  = IsZero(result<7:0>)
    ```
  ],
  flags: flags-affected(
    fault: [overflow],
    link: "—",
    minus: "*",
    value: "*",
  ),
  notes: [
    Incrementing by more than 1 (a non-zero constant field) is a CPU6
    extension; CPU4 and CPU5 increment only by 1. The link flag is *not*
    updated; use word arithmetic when a carry chain is needed.
  ],
)
