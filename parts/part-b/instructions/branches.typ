#import "../../../lib/instruction.typ": *

// Row 0x10-0x1F: conditional branches. All take a signed 8-bit
// displacement relative to the address of the next instruction.

#instruction(
  "Bcc",
  qualifier: "(conditional branches)",
  summary: [
    The sixteen conditional branches test a flag, a flag combination,
    a front-panel sense switch, or a processor enable, and on success
    continue at `PC + disp`, where `disp` is a signed 8-bit
    displacement from the address of the *next* instruction
    (range −128…+127).
  ],
  encodings: (
    encoding(
      "PC-relative",
      applicability: "CPU4/5/6 (BI, BCK: CPU6)",
      asm: "Bcc <label>",
      diagram: bitbox(
        ((bits: 4, value: "0001"), (name: "cond", bits: 4)),
        ((name: "disp (signed)", bits: 8),),
      ),
    ),
  ),
  syntax: [
    #table(
      columns: (auto, auto, auto, auto),
      stroke: 0.5pt,
      inset: 4pt,
      table.header([*Op*], [*Mnemonic*], [*Taken when*], [*Notes*]),
      [10], [`BL`],  [L = 1], [link/carry set],
      [11], [`BNL`], [L = 0], [],
      [12], [`BF`],  [F = 1], [fault set],
      [13], [`BNF`], [F = 0], [],
      [14], [`BZ`],  [V = 1], [result was zero],
      [15], [`BNZ`], [V = 0], [],
      [16], [`BM`],  [M = 1], [minus set],
      [17], [`BP`],  [M = 0], [plus (not minus)],
      [18], [`BGZ`], [M = 0 and V = 0], [greater than zero],
      [19], [`BLE`], [M = 1 or V = 1], [less than or equal to zero],
      [1A], [`BS1`], [sense switch 1], [front panel],
      [1B], [`BS2`], [sense switch 2], [front panel],
      [1C], [`BS3`], [sense switch 3], [front panel],
      [1D], [`BS4`], [sense switch 4], [front panel],
      [1E], [`BI`],  [interrupts enabled], [EI/DI state; CPU6],
      [1F], [`BCK`], [clock running], [ECK/DCK state; CPU6],
    )
  ],
  operation: [
    ```cpu6
    disp = SignExtend(operand<7:0>)
    if Condition(cond) then
        PC = PC + disp     // PC = address of next instruction
    ```
  ],
  flags: none,
  notes: [
    `BZ`/`BNZ` test the V flag, which the load/ALU instructions set
    when their *result* is zero — V reads as "value is zero", the
    inverse sense of most other architectures' Z usage. `BI` and `BCK`
    test live processor enables, not condition flags; both are
    microcode-verified against the reference simulator.
  ],
)
