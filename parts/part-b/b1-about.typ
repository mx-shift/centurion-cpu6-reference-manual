= About the Instruction Descriptions

== Format of instruction descriptions

Each instruction entry in this part contains, in order: the instruction
name and a one-paragraph summary; one *Encoding* block per addressing
variant, with the CPU generations it applies to, the assembler form, and
a boxed bit-level encoding diagram; the *Assembler syntax* with a
`where:` glossary of operand fields; the *Operation* in pseudocode (see
the pseudocode appendix); the *Flags affected* box (F fault, L link,
M minus, V value); *Exceptions*; and optional *Notes* and a worked
*Example*.

== Registers and operand fields

The CPU6 has eight word registers — `A`, `B`, `X`, `Y`, `Z`, `S`, `C`,
and `P` — each addressable as upper and lower byte halves (e.g. `AU`,
`AL`). Register operand fields in encoding diagrams hold the 4-bit
register-file byte index of the operand: word operands use even indexes
(`A`=0, `B`=2, …, `P`=14); byte operands address any of the 16 register
bytes directly.

== Flags

The condition flags live in the low byte of the `C` (context) register:

- *V* (value), bit 7 — set when the result is zero. Note the inverted
  sense relative to most architectures' Z flag.
- *M* (minus), bit 6 — set when the result is negative.
- *F* (fault), bit 5 — arithmetic overflow, or a block-operation fault.
- *L* (link), bit 4 — carry, borrow, or the shifted-out bit.

== Documentation status

Entries are marked _derived_ when their behavior was reconstructed from
the webCenREE reference emulator rather than period documentation.
