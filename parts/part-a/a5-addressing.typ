= Addressing Modes

== The mode family

Memory-reference instructions (loads, stores, JMP, JSR) encode one of
six modes in the opcode's low three bits:

#table(
  columns: (auto, auto, auto, 1fr),
  stroke: 0.5pt,
  inset: 5pt,
  table.header([*Mode*], [*Suffix*], [*Operands*], [*Effective address*]),
  [000], [`=`], [literal byte/word], [the literal itself (stores
    overwrite it)],
  [001], [`/`], [addr₁₆], [addr],
  [010], [`$`], [addr₁₆], [MemW\[addr\]],
  [011], [(space)], [disp₈ signed], [PC + disp],
  [100], [`*`], [disp₈ signed], [MemW\[PC + disp\]],
  [101], [`+`/`−`], [mode byte (+ disp₈)], [indexed, below],
)

Modes +8…+15 of each load/store row are one-byte encodings of the
plain indexed mode for each register in turn.

== The indexed mode byte

```cpu6
[reg:4][0][disp:1][ind:1][id:2]
```

- *reg* — the index register (register-file byte index of its high
  half: 0 = A, 2 = B, 4 = X, …).
- *id* — 01: post-increment, 10: pre-decrement, by the operand width.
- *ind* — indirect: the indexed address selects a word holding the EA.
- *disp* — a signed displacement byte follows and is added.
- Bit 4 must be zero; encodings with it set are illegal (trap,
  cause 0).

Combinations compose in that order: decrement, displace, then
indirection. The assembler writes them `+A`, `+A+`, `−A−`, `+A,3`,
`+*A`, `+*A+,5`, ….

== Register-constant and register-register operands

Single-register rows (0x20–0x3F) carry `[reg:4][const:4]`. The word
rows extend through odd register nibbles to direct and indexed memory
operands (§B, INR). Two-register rows carry `[src:4][dst:4]`, with the
nibble low bits selecting immediate/direct/indexed sub-modes on the
CPU6 word rows (§B, ADD; §B, MUL).

== Extended-family operands

PAGE, DMA, BIG, and MEM each define their own selector-byte grammars,
documented with the instructions.
