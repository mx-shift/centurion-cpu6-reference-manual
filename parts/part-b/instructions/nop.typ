#import "../../../lib/instruction.typ": *

#instruction(
  "NOP",
  summary: [
    No Operation advances the program counter past the instruction and
    performs no other architecturally visible action.
  ],
  encodings: (
    encoding(
      "Implicit",
      applicability: "CPU4/5/6",
      asm: "NOP",
      diagram: bitbox(
        ((bits: 8, value: "00000001"),),
      ),
    ),
  ),
  syntax: [
    `NOP`
  ],
  operation: [
    ```cpu6
    // No operation.
    ```
  ],
  notes: [
    On the CPU6, `NOP` has no microcode body of its own: the initial
    instruction decode dispatches directly back to the start of the
    instruction loop.
  ],
)
