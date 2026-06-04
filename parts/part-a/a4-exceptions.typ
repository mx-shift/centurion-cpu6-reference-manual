= Interrupts, Traps, and Context Switching

== Interrupt levels

Sixteen priority levels, each with its own register bank (§A2). The
processor runs at one level (IPL); a device asserting a higher level
preempts at the next instruction boundary. Level assignments on a
typical system: Hawk disk completion at 2, console MUX at 6, the
60 Hz clock at 10, and all traps at 15.

== Entry

Entering level _t_ (interrupt or trap) performs:

```cpu6
Bank[old].P   = PC
Bank[old].Clo = [V M F L] : AOO : PTA     // live status composed
Bank[t].CU    = old<<4 | 5                // entry stamp
cc            = 0                          // flags cleared
AOO           = Bank[t].Clo<3>             // stale: kept per level
PTA           = Bank[t].Clo<2:0>           // each level keeps its map
PC            = Bank[t].P
```

The interrupt-enable state (EI/DI) is unchanged. Because the flag
helpers never touch the low nibble, a service routine that returns
with RI re-saves its own map bits — each level's address space is
sticky across entries. _Microcode-verified._

== Trap causes

All traps enter level 15. The cause code is written to the service
bank's `AL` only — `AU` survives — and the saved PC points past the
faulting instruction, so RI resumes after it:

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt,
  inset: 5pt,
  table.header([*Cause (`AL`)*], [*Z*], [*Source*]),
  [0], [—], [illegal opcode or encoding],
  [1], [—], [HLT below level 15],
  [2], [written VA], [store through a write-tracked page (after the
    write completes)],
  [4], [failing VA], [memory parity error while EPE is armed],
)

The clock service (level 10) is not a trap but stamps Z with the
complemented cause byte (0xFE).

== Service calls and dispatch

SVC enters the supervisor at 0x0100 with a 5-byte stack frame; RSV
unwinds it and reloads the caller's page map from the frame's status
byte. An operating system represents a task as a stack image ending
in such a frame: dispatch is "point S, RSV". Returning the favor,
SAR/LAR let the supervisor edit any bank directly, and the register
file's memory mapping exposes everything to ordinary instructions.

== Reset

Reset enters level 0 at 0xFD00 (bootstrap ROM) with interrupts
disabled, the clock stopped, map 0 active, and write parity odd.
