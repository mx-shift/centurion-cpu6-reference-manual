#import "../../lib/template.typ": front-chapter

#front-chapter[About This Manual]

== Organization

- *Part A — Architecture*: the programmers' model — registers, condition
  flags, data types, memory model and MMU, interrupt levels and context
  switching, and addressing modes.
- *Part B — Instruction Set*: the per-instruction descriptions, in
  alphabetical order, followed by the illegal-opcode behaviour.
- *Appendices*: the opcode map, assembler syntax summary, the pseudocode
  definition, indexes, and processor-generation differences.

== Numbering conventions

Chapters are numbered within parts (A1, B2, …); sections within chapters
(B2.3). Binary values are written as digit strings in encoding diagrams;
hexadecimal values use the `0x` prefix.

== Typographical conventions

`Monospace` text shows assembler syntax, opcodes, and pseudocode.
_Italic_ fields in encoding diagrams are variable; fixed bits are shown
one digit per cell.
