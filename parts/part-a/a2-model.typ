= Programmers' Model

== Overview

The CPU6 is organized, from the programmer's point of view, around
*multitasking*. It is not a single-context processor onto which an
operating system bolts time-sharing; the hardware itself maintains
sixteen independent execution contexts and switches between them by
priority. Understanding that structure first makes the rest of the
model — the registers, the flags, the memory map, the interrupt
mechanism — fall into place.

=== Functional units

The architecturally visible machine comprises four cooperating units:

- *The data path* — an 8/16-bit ALU that performs the arithmetic,
  logical, shift, and move operations. It does not contain the working
  registers; it operates on them in memory (below).
- *The register file* — sixteen complete sets of eight 16-bit
  registers, one set per context, held in the lowest 256 bytes of
  physical memory. The file *is* memory addresses `0x0000`–`0x00FF`
  (§A2.3); there is no separate register hardware to save or restore.
- *The memory mapper (MMU)* — translates the 16-bit addresses a program
  issues into the larger physical address space through one of several
  page maps, so different contexts can run in different address spaces
  (§A3).
- *The priority interrupt system* — sixteen levels, each bound to a
  register set and a saved program counter, that arbitrate which context
  the data path is currently executing (§A4).

Input and output are memory-mapped: device registers appear in the high
end of the address space (the `0xF000`–`0xFFFF` region) and are read and
written by ordinary load and store instructions.

=== How data moves

Because the working registers live in memory, the central data motion of
the machine is between the register file and the rest of memory. A
register-to-register instruction names two registers by their position
in the *current* context's slice of the file; a load or store moves a
byte or word between a register and a mapped memory address; the
extended families move blocks and wide integers. The mapper sits on
every memory access a program makes, so the same 16-bit address in two
different contexts can reach two different physical locations.

=== Process contexts

A *context* (the hardware calls it an interrupt *level*) is a complete,
independent thread of execution: its own eight registers, its own
condition flags, its own saved program counter, and its own address map.
The sixteen levels are ranked by priority. At any instant the data path
is executing the highest-priority level that is ready to run; when a
higher-priority level becomes ready — a device interrupt, a trap, or an
explicit request — the machine switches to it.

The switch is not a stack-based save and restore. Because each level's
entire context already resides in its own slice of the register file and
is reached through its own map, switching levels is simply a matter of
changing which slice and which map are current. A suspended level's
state is left exactly where it lives; resuming it continues from its
saved program counter as though it had never stopped. This is what makes
the CPU6 a natural multitasking host: a supervisor running at one level
manufactures and dispatches tasks by writing their register slices and
pointing the interrupt mechanism at them, and the cost of a context
switch is bounded by the architecture rather than by how much state
software chooses to spill.

The remainder of this chapter describes the pieces of a context in
detail — the registers (§A2.2), the register file that holds all sixteen
of them (§A2.3), the way levels behave as resumable coroutines (§A2.4),
and the condition flags (§A2.5). The memory map and the interrupt
mechanism that bind a context to an address space and a priority are the
subjects of §A3 and §A4.

== Registers

The CPU6 provides eight 16-bit registers per interrupt level:

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt,
  inset: 5pt,
  table.header([*Register*], [*Byte halves*], [*Conventional role*]),
  [A], [`AU`, `AL`], [accumulator; trap cause codes arrive in `AL`],
  [B], [`BU`, `BL`], [accumulator / pair follower of A],
  [X], [`XU`, `XL`], [index; SVC return address],
  [Y], [`YU`, `YL`], [index; MVL destination],
  [Z], [`ZU`, `ZL`], [index; fault addresses arrive here],
  [S], [`SU`, `SL`], [stack pointer (descending, byte-granular)],
  [C], [`CU`, `CL`], [status: flags, abort enable, page map, entry stamp],
  [P], [`PU`, `PL`], [saved program counter],
)

Registers pair as (A,B), (X,Y), (Z,S): a _leader_ and a _follower_.
MUL and DIV use the pair to hold 32-bit products and
quotient/remainder sets.

== The register file

All sixteen levels' registers live in a 256-byte register file that is
also physical memory 0x0000–0x00FF: level _n_'s bank occupies bytes
16·_n_…16·_n_+15, registers stored big-endian in the order A B X Y Z S
C P. Ordinary loads and stores reach any bank when the active page map
exposes physical page 0, and SAR/LAR address the file directly. The
*live* program counter is processor state, distinct from the P slot,
which holds the value saved at the last level switch.

== The C register and the flags

The live condition flags are the high nibble of an internal status
byte; the rest of the byte materializes whenever C is saved:

#table(
  columns: (auto, auto, auto, auto, auto, auto),
  stroke: 0.5pt,
  inset: 5pt,
  align: center,
  table.header([*7*], [*6*], [*5*], [*4*], [*3*], [*2:0*]),
  [V], [M], [F], [L], [AOO], [PTA],
)

- *V (value)* — set when a result is zero. Note the inverted sense
  relative to most architectures' Z flag: `BZ` branches when V = 1.
- *M (minus)* — the result's sign bit.
- *F (fault)* — arithmetic overflow, shift sign-change, divide by
  zero; also directly settable (SF/RF).
- *L (link)* — carry / borrow-free / rotate-through bit.
- *AOO* — the EAO/DAO abort-on-overflow enable.
- *PTA* — the active page map number (§A3).

`CU` receives an entry stamp at every interrupt or trap: the
interrupted level in the high nibble and 5 in the low nibble.

== Data types

Byte and word (16-bit, big-endian in memory) throughout; the BIG
family (0x46) adds big-endian two's-complement integers of 1–16
bytes.

== The stack

S points at the last pushed byte and grows downward. JSR pushes a
2-byte return address; STK/POP move register-file byte runs; SVC
pushes its 5-byte frame. Nothing is implicitly aligned.
