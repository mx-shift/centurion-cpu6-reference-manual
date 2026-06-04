= Introduction

The Centurion CPU6 is the processor of the last and most capable
generation of the Centurion family of small-business minicomputers. It
is an 8/16-bit, microcoded, bit-slice design that hosts up to sixteen
concurrent execution contexts in hardware. This manual describes its
instruction set architecture: the programmers' model, the memory and
mapping model, the interrupt and context-switching model, the addressing
modes, and every instruction.

== The Centurion family

The Centurion line was built by Warrex Computer Corporation of
Richardson, Texas. The company began in 1971 as Warrex Computer
Services, a consulting and programming firm founded by John Warren, and
incorporated as Warrex Corporation in 1972. By August 1974 it had
designed, built, and shipped its first minicomputer — the start of the
Centurion family of small-business systems, sold and supported through
Warrex Computer Corporation. Warren died in 1976; the company was
renamed Centurion Computer Corporation in March 1980 and acquired by
Electronic Data Systems for \$7 million in March 1981.

Across roughly a decade of production the company delivered on the order
of a thousand systems, predominantly to customers in Texas and Oklahoma.
A Centurion system paired the CPU with core or semiconductor memory
(32–256 KiB), Winchester and CDC Hawk disk storage (8–96 MiB), and as
many as 32 serial CRT terminals — a multi-user business machine running
the proprietary CENTOS operating system. Successive product series (the
MicroPlus, Series 200, 6200, III, 6300, 6400, and 6500) were built
around the CPU5 and CPU6 processors.

== Architectural lineage

The Centurion instruction set descends from the El Dorado Electrodata
Corporation EE200, a processor that the community believes to be the
direct predecessor of the first Centurion CPU. Three processor
generations are documented:

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt,
  inset: 5pt,
  table.header([*Generation*], [*Implementation*]),
  [CPU4], [Hardwired discrete TTL logic across several boards.],
  [CPU5], [The same architecture compressed onto two cards.],
  [CPU6], [A single multiwire board, reimplemented as a *microcoded*
           bit-slice machine.],
)

The generations are upward-compatible at the instruction-set level: CPU6
runs the earlier software and extends it. This manual documents the
CPU6; behaviours known to differ in CPU4 or CPU5 are annotated where
they are understood (see the differences appendix).

== The CPU6 processor

Unlike its hardwired predecessors, the CPU6 is *microcoded*. Its data
path is built from Am2901 four-bit ALU slices; a microprogram sequencer
(two Am2909 plus one Am2911, forming an 11-bit microcode address) steps
through seven 2 KiB EPROMs that supply a 56-bit microword each cycle,
with a separate decode ROM mapping opcodes to microcode entry points.
Every architecturally visible instruction in this manual is therefore a
short microprogram, and the richer behaviours that distinguish the
CPU6 — the banked register file, the page-mapping MMU, the extended
arithmetic and block-move families, and the sixteen-level priority
interrupt system — are properties of that microcode rather than of fixed
logic.

This microcode is the ultimate authority on the architecture. Where
period documentation is silent — which is to say, across much of the
instruction map — the behaviour stated here was recovered from the
microcode and from emulators that reproduce it, and is so marked.

== Rediscovery

No manufacturer's programming manual for the CPU6 is known to survive.
The architecture documented here was reconstructed by the retrocomputing
community after David Lovett (Usagi Electric) recovered and restored a
working Centurion system and documented the effort publicly. The
community has since reverse-engineered the microcode, the instruction
set, the memory and interrupt models, and the disk and peripheral
formats. This manual is a synthesis of that work; its sources and the
people behind them are credited in the Preface.
