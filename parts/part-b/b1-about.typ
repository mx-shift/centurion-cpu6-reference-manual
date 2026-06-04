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

== Conventions

Part A is the reference for the programmers' model; these descriptions
assume it. The notes here cover only what is specific to reading an
instruction entry.

*Register operand fields.* A register field in an encoding diagram holds
the 4-bit register-file byte index of its operand (the registers and
their byte halves are §A2.2): word operands use even indexes (`A`=0,
`B`=2, …, `P`=14); byte operands address any of the 16 register bytes
directly.

*The Flags affected box.* The box names the four condition flags in the
`C` register's low byte — *F* (fault), *L* (link), *M* (minus), *V*
(value); their meanings are §A2.5. Within an entry, "—" marks a flag the
instruction leaves unchanged and "\*" one set from the result; any other
text states the specific rule. Recall that *V* has inverted sense — it
is set when the result is _zero_.

== Documentation status

Entries are marked _derived_ when their behavior was reconstructed from
the webCenREE reference emulator rather than period documentation.
