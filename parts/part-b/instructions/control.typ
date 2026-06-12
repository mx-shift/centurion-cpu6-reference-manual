#import "../../../lib/instruction.typ": *

// Row 0x00-0x0F: implicit control instructions. Semantics verified
// against the microcode simulator during the emulator's optest
// campaign (see the emulator repo's FIDELITY.md).

#instruction(
  "HLT",
  qualifier: "(halt)",
  summary: [
    Halt stops instruction execution. At interrupt level 15 the
    processor genuinely halts until an interrupt arrives. At any lower
    level, HLT instead traps to level 15 with cause code 1, so a
    supervisor can treat stray halts as faults; the operating system
    uses the trap as its idle/wait primitive — the level-15 handler
    resumes the halted context when work arrives.
  ],
  encodings: (
    encoding(
      "Implicit",
      applicability: "CPU4/5/6",
      asm: "HLT",
      diagram: bitbox((( bits: 8, value: "00000000"),)),
    ),
  ),
  syntax: [
    `HLT` — the alias `HALT` is accepted.
  ],
  operation: [
    ```cpu6
    if IPL == 15 then
        halt until interrupt
    else
        TrapToLevel15(cause = 1)   // saved PC points past HLT
    ```
  ],
  flags: none,
  exceptions: [Level-15 trap when executed below level 15 (cause 1 in
    the service bank's `AL`).],
)

#instruction(
  "NOP",
  summary: [No operation. One byte, no architectural effect.],
  encodings: (
    encoding(
      "Implicit",
      applicability: "CPU4/5/6",
      asm: "NOP",
      diagram: bitbox((( bits: 8, value: "00000001"),)),
    ),
  ),
  flags: none,
)

#instruction(
  "SF",
  qualifier: "(set fault)",
  summary: [
    Set the fault flag F directly. All other flags are preserved. `RF`
    is the reset counterpart.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU4/5/6", asm: "SF",
      diagram: bitbox((( bits: 8, value: "00000010"),))),
  ),
  operation: [
    ```cpu6
    FAULT = 1
    ```
  ],
  flags: flags-affected(fault: [set]),
)

#instruction(
  "RF",
  qualifier: "(reset fault)",
  summary: [
    Clear the fault flag F directly. All other flags are preserved.
    `SF` is the set counterpart.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU4/5/6", asm: "RF",
      diagram: bitbox((( bits: 8, value: "00000011"),))),
  ),
  operation: [
    ```cpu6
    FAULT = 0
    ```
  ],
  flags: flags-affected(fault: [cleared]),
)

#instruction(
  "EI",
  qualifier: "(enable interrupts)",
  summary: [
    Enable the interrupt system. The enable state is global (not
    per-level) and is left untouched by interrupt entry, trap entry,
    and RI — only EI, DI, and processor reset change it. The `BI`
    branch tests it; `DI` is the disable counterpart.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU4/5/6", asm: "EI",
      diagram: bitbox((( bits: 8, value: "00000100"),))),
  ),
  flags: none,
)

#instruction(
  "DI",
  qualifier: "(disable interrupts)",
  summary: [
    Disable the interrupt system. The enable state is global (not
    per-level) and is left untouched by interrupt entry, trap entry,
    and RI — only EI, DI, and processor reset change it. The `BI`
    branch tests it; `EI` re-enables.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU4/5/6", asm: "DI",
      diagram: bitbox((( bits: 8, value: "00000101"),))),
  ),
  flags: none,
)

#instruction(
  "SL",
  qualifier: "(set link)",
  summary: [
    Set the link (carry) flag L. All other flags are preserved. `RL`
    clears it; `CL` complements it.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU4/5/6", asm: "SL",
      diagram: bitbox((( bits: 8, value: "00000110"),))),
  ),
  flags: flags-affected(link: [set]),
)

#instruction(
  "RL",
  qualifier: "(reset link)",
  summary: [
    Clear the link (carry) flag L. All other flags are preserved. See
    `SL`.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU4/5/6", asm: "RL",
      diagram: bitbox((( bits: 8, value: "00000111"),))),
  ),
  flags: flags-affected(link: [cleared]),
)

#instruction(
  "CL",
  qualifier: "(complement link)",
  summary: [
    Complement the link (carry) flag L. All other flags are preserved.
    See `SL`.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU4/5/6", asm: "CL",
      diagram: bitbox((( bits: 8, value: "00001000"),))),
  ),
  flags: flags-affected(link: [complemented]),
)

#instruction(
  "RSR",
  qualifier: "(return from subroutine)",
  summary: [
    Return from a subroutine entered with JSR: pop the 16-bit return
    address from the stack (S pre-increment by 2) and continue there.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU4/5/6", asm: "RSR",
      diagram: bitbox((( bits: 8, value: "00001001"),))),
  ),
  operation: [
    ```cpu6
    PC = MemW[S]
    S  = S + 2
    ```
  ],
  flags: none,
)

#instruction(
  "RI",
  qualifier: "(return from interrupt)",
  summary: [
    Return from an interrupt or trap by switching back to the level
    recorded in the current bank's C register high nibble. The target
    bank's saved C low byte is split back into live state: the high
    nibble restores the flags, bit 3 restores the abort-on-overflow
    enable, and the low three bits restore the active page map (PTA).
    Execution resumes at the target bank's saved P.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU4/5/6", asm: "RI",
      diagram: bitbox((( bits: 8, value: "00001010"),))),
  ),
  operation: [
    ```cpu6
    target  = Bank[IPL].C<7:4>          // level stamped at entry
    IPL     = target
    cc      = Bank[target].Clo<7:4>     // V M F L
    AOO     = Bank[target].Clo<3>
    PTA     = Bank[target].Clo<2:0>     // active page map
    PC      = Bank[target].P
    ```
  ],
  flags: flags-affected(fault: "*", link: "*", minus: "*", value: "*"),
  notes: [
    The interrupt-enable state (EI/DI) is *not* modified. The current
    bank's own C and P are saved on the way out, so a later entry to
    this level resumes correctly.
  ],
)

#instruction(
  "SYN",
  summary: [
    Flash the front-panel abort indicator. No architectural effect on
    program state. CPU6 only.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU6", asm: "SYN",
      diagram: bitbox((( bits: 8, value: "00001100"),))),
  ),
  flags: none,
)

#instruction(
  "PCX",
  qualifier: "(PC to X)",
  summary: [
    Copy the address of the next instruction into X. Used to establish
    position-independent addressing.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU4/5/6", asm: "PCX",
      diagram: bitbox((( bits: 8, value: "00001101"),))),
  ),
  operation: [
    ```cpu6
    X = PC   // address of the instruction after PCX
    ```
  ],
  flags: none,
)

#instruction(
  "DLY",
  summary: [
    Delay for approximately 4.55 ms. The processor idles; interrupts
    are taken normally during the delay.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU4/5/6", asm: "DLY",
      diagram: bitbox((( bits: 8, value: "00001110"),))),
  ),
  flags: none,
)

#instruction(
  "RSV",
  qualifier: "(return from service call)",
  summary: [
    Return-from-SVC and task dispatch. RSV pops the 5-byte SVC frame:
    PC continues at the address currently in X, X is restored from the
    frame, S is adjusted by 5, and P receives the address after the
    RSV. The flags are *not* restored — but the frame's saved cc byte
    reloads the active page map (PTA, low three bits), which is how
    the operating system's dispatcher switches a task's address space
    on resume. CPU6 only.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU6", asm: "RSV",
      diagram: bitbox((( bits: 8, value: "00001111"),))),
  ),
  operation: [
    ```cpu6
    frame_x  = MemW[S + 1]
    frame_cc = Mem[S + 4]
    S   = S + 5
    P   = PC          // address after RSV
    PC  = X
    X   = frame_x
    PTA = frame_cc<2:0>   // flags V M F L unchanged
    ```
  ],
  flags: none,
  notes: [
    Microcode-verified: the live flags survive RSV even when the frame
    byte differs; only the map-select bits take effect. See SVC for
    the frame layout.
  ],
)
