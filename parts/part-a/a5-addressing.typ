#import "../../lib/bitfield.typ": bitbox
#import "../../lib/addrdiag.typ": ea-flow, stage, idx-pipeline, step-row

= Addressing Modes

An addressing mode tells the processor how to turn the bytes that follow
an opcode into the *operand* the instruction works on.

== Operand styles

Every instruction begins with a one-byte opcode. It helps to picture the
256 opcodes as a 16×16 map (Appendix A): the high nibble selects a *row*
of sixteen opcodes and the low nibble a column within it. Related
instructions occupy contiguous rows, and this chapter — like the rest of
the manual — names blocks of opcodes that way, for instance "the
load/store rows" or "the `0x20–0x3F` rows". The operand-encoding bits
described below are carved from the low bits of the opcode and from the
bytes that follow it.

The CPU6 has two operand styles:

- *Memory-reference* operands, used by the loads, stores, `JMP`, and
  `JSR`. The opcode's low three bits select one of six modes (§A5.2);
  the bytes that follow are interpreted accordingly to form an
  _effective address_ (EA), and the operand is the byte or word at that
  address. The diagrams in §A5.2 trace that derivation for each mode.
- *Register* operands, used by the register-to-constant and
  register-to-register instructions, which name their operands directly
  in a selector byte rather than reaching into memory (§A5.4).

The extended instruction families add their own operand grammars
(§A5.5).

== The six memory-reference modes

The mode occupies the low three bits of the opcode:

#table(
  columns: (auto, auto, auto, 1fr),
  stroke: 0.5pt,
  inset: 5pt,
  table.header([*Mode*], [*Suffix*], [*Operand bytes*], [*Effective address*]),
  [000], [`=`], [literal byte/word], [— (the literal _is_ the operand)],
  [001], [`/`], [addr₁₆], [addr],
  [010], [`$`], [addr₁₆], [`MemW[addr]`],
  [011], [(space)], [disp₈, signed], [`PC + disp`],
  [100], [`*`], [disp₈, signed], [`MemW[PC + disp]`],
  [101], [`+`/`−`], [mode byte (+ disp₈)], [indexed — see §A5.3],
)

In the diagrams below, a box is a field in the instruction stream or a
location in memory; the gray tag under a memory box is the address it
sits at; the shaded box is the final operand the instruction uses.

#v(0.4em)
*`=` immediate (000).* The operand bytes _are_ the operand — no address
is formed. A one-byte operation takes one literal byte, a word operation
two. For a store, this field is the destination written to (the
instruction modifies its own operand in place).

#ea-flow(
  (stage([literal], role: "operand field", hi: true),),
  (),
)

#v(0.4em)
*`/` direct (001).* The operand bytes are the address; the operand is
what lives there.

#ea-flow(
  (
    stage([addr], role: "operand field"),
    stage([operand], role: "memory", addr: "addr", hi: true),
  ),
  ([address],),
)

#v(0.4em)
*`$` indirect (010).* The operand bytes address a _pointer_ word; the
operand is what that pointer points to — two memory hops.

#ea-flow(
  (
    stage([addr], role: "operand field"),
    stage([pointer], role: "memory", addr: "addr"),
    stage([operand], role: "memory", addr: "pointer", hi: true),
  ),
  ([address of], [points to]),
)

#v(0.4em)
*`(space)` PC-relative (011).* A signed 8-bit displacement is added to
the program counter to form the address. Used for position-independent
references near the instruction.

#ea-flow(
  (
    stage([PC + disp], role: "computed"),
    stage([operand], role: "memory", addr: "PC+disp", hi: true),
  ),
  ([address],),
)

#v(0.4em)
*`*` PC-relative indirect (100).* As above, but `PC + disp` addresses a
pointer word, and the operand is what it points to.

#ea-flow(
  (
    stage([PC + disp], role: "computed"),
    stage([pointer], role: "memory", addr: "PC+disp"),
    stage([operand], role: "memory", addr: "pointer", hi: true),
  ),
  ([address of], [points to]),
)

#v(0.4em)
*`+`/`−` indexed (101).* The richest mode: a following _mode byte_
selects an index register and optional displacement, indirection, and
auto-increment/decrement. It has its own section.

== Indexed mode

Mode 101 is followed by a mode byte:

#bitbox(((name: "reg", bits: 4), (name: "disp", bits: 1), (name: "ind", bits: 1), (name: "id", bits: 2)))

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt,
  inset: 5pt,
  table.header([*Field*], [*Meaning*]),
  [`reg`], [Index register, as the register-file byte index of its high
    half: 0 = A, 2 = B, 4 = X, 6 = Y, … . The index must be *even* —
    bit 4 of the mode byte is the register number's low bit and must be
    zero; encodings with it set are illegal (trap, cause 0).],
  [`disp`], [If 1, a signed displacement byte follows and is added to the
    register value.],
  [`ind`], [If 1, _indirect_: the address formed so far selects a word
    that holds the real EA.],
  [`id`], [Auto-update: `01` = post-increment, `10` = pre-decrement,
    `00` = none. (`11` is unused.)],
)

The fields apply in a fixed order — pre-decrement, then displacement,
then indirection, with post-increment last. Reading the pipeline
top-to-bottom gives the EA; dashed stages happen only when their bit is
set:

#idx-pipeline((
  step-row(`R ← R − step`, gate: "id = 10"),
  step-row(`base ← R`),
  step-row(`base ← base + disp`, gate: "disp = 1"),
  step-row(`base ← MemW[base]`, gate: "ind = 1"),
  step-row(`EA = base`, final: true),
  step-row(`R ← R + step`, gate: "id = 01"),
))

`step` is the operand width — 1 for a byte operation, 2 for a word — so
the register walks an array element at a time. *Indirection forces a
word step*: when `ind = 1` the increment or decrement is 2 regardless of
the operand width, because it is walking a table of pointers.

=== Worked examples

Take index register `X = 0x2000`, a word operation (`step = 2`), and
memory holding `MemW[0x2000] = 0x4500` and `MemW[0x2005] = 0x4780`:

#table(
  columns: (auto, auto, auto, 1fr, auto),
  stroke: 0.5pt,
  inset: 5pt,
  align: (col, row) => if row == 0 { center } else { left },
  table.header([*Assembler*], [*Set bits*], [*step*], [*Effective address*], [*X after*]),
  [`+X`], [—], [—], [`0x2000` (register value)], [`0x2000`],
  [`+X,3`], [disp], [—], [`0x2000 + 3 = 0x2003`], [`0x2000`],
  [`+X+`], [id=01], [2], [`0x2000`, then step], [`0x2002`],
  [`−X−`], [id=10], [2], [`0x2000 − 2 = 0x1FFE`], [`0x1FFE`],
  [`+*X`], [ind], [—], [`MemW[0x2000] = 0x4500`], [`0x2000`],
  [`+*X+,5`], [disp, ind, id=01], [2], [`MemW[0x2000+5] = 0x4780`], [`0x2002`],
)

For `+*X+,5` the steps are: displace (`0x2000 + 5 = 0x2005`),
dereference (`EA = MemW[0x2005] = 0x4780`), then post-increment the
register by the word step (`X ← 0x2002`) — the displacement offsets the
access but is not written back.

Modes `+8 … +15` of each load/store opcode row are one-byte shorthands
for the plain indexed mode (`disp = ind = id = 0`) on each register in
turn. Bit positions in the mode byte are microcode-verified (conformance
suite, idx group).

== Register-constant and register-register operands

These instructions name their operands in a *selector byte* that follows
the opcode, instead of forming a memory address.

The *register–constant* rows (`0x20–0x3F`) carry a `[reg:4][const:4]`
selector: a register and a 4-bit immediate constant. On the word rows
these encodings extend through the odd register nibbles to reach direct
and indexed memory operands as well (§B, `INR`).

The *register–register* rows carry a `[src:4][dst:4]` selector naming a
source and a destination register, with the nibble low bits selecting
immediate/direct/indexed sub-modes on the CPU6 word rows (§B, `ADD`; §B,
`MUL`).

== Extended-family operands

`PAGE`, `DMA`, `BIG`, and `MEM` each define their own selector-byte
grammars, documented with the instructions in §B3.
