= Pseudocode Definition

The `Operation` sections in Part B use a small pseudocode language,
defined here.

== Data types

`bit`, `byte` (8 bits), `word` (16 bits), `bits(N)`, `boolean`, and
unbounded `integer`.

== Processor state

- `A`, `B`, `X`, `Y`, `Z`, `S`, `C`, `P` — the word registers of the
  current interrupt level; `.U`/`.L` select byte halves.
- `R[i]` — the register file of the current level, indexed by the 4-bit
  register-file byte index `i` (byte access) or even index (word access).
- `PC` — the live program counter.
- `FAULT`, `LINK`, `MINUS`, `VALUE` — the condition flags.
- `IPL` — the current interrupt priority level (0–15).
- `Mem[a]` / `MemW[a]` — byte / word memory access at virtual address `a`.

== Operators and helpers

`+`, `-`, `AND`, `OR`, `XOR`, `NOT`; `x<h:l>` bit-slice; `:` bit
concatenation; `SignExtend()`, `ZeroExtend()`, `IsZero()`,
`Overflow()`; `AddWithCarry()`, `Push()`, `Pop()`, `Branch()`,
`ContextSwitch()`, `Trap()`.

// M5 work item: complete formal definitions of each helper.
