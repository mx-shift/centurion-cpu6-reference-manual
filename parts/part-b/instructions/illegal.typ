#import "../../../lib/instruction.typ": *

#instruction(
  "Illegal opcodes",
  summary: [
    Opcodes 0x0B, 0x70, 0x87, 0x97, 0xA7, 0xB7, 0xC7, and 0xE7 are
    not implemented (0xF7 is additionally illegal on CPU5, where MVL
    does not exist). Executing one traps to level 15 exactly like an
    interrupt entry: nothing else is stamped except the cause code 0
    in the service bank's `AL`, and the saved PC points past the
    opcode byte, so a handler that simply returns resumes after the
    offender.
  ],
  encodings: (),
  operation: [
    ```cpu6
    TrapToLevel15(cause = 0)
    // Bank[15].AL = 0, Bank[15].AU preserved, Z preserved;
    // Bank[old].P = PC (past the illegal byte)
    ```
  ],
  flags: none,
  exceptions: [Always: level-15 illegal-instruction trap.],
  notes: [
    System software exploits the resume semantics: the community's
    opcode test suite sets all four flags atomically by planting the
    desired flag byte where the level-15 handler will find it,
    executing a deliberate 0xE7, and letting the handler rewrite the
    interrupted level's saved C before returning.
  ],
)
