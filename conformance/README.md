# CPU6 ISA conformance suite

A hardware-runnable test suite derived **solely from the ISA manual**
in this repository. It exists because the emulator work keeps turning
up behaviors that no existing test suite covers (DRM's
remainder-to-`[A]`, CFB's marker rules, SVC's map switch, …) — so no
existing suite is trusted as evidence that an emulator matches the
real machine. This one tests the *manual's claims*, on whatever is on
the other end of the wire.

## How it works

```
  run.py ──serial/telnet──► TOS (DIAG monitor) ──M/G──► test kernel
    │                                                       │
    ├── gen.py: vectors from data/opcodes.yaml + §A5         │
    ├── model.py: expectations transcribed from the manual ◄─┘
    └── report.jsonl: per-vector pass/fail/skip with full state
```

- **kernel.py / asm.py** — a 650-byte CPU6 program, assembled with
  opcodes checked against `../data/opcodes.yaml` at build time. It is
  loaded through TOS's `M` command, started with `G`, and then speaks
  a checksummed hex frame protocol on the console MUX port: the host
  sends initial registers + a memory window + a code snippet; the
  kernel runs the snippet and reports the four flags (sampled with a
  conditional-branch tree — the only architecturally clean way to
  read live flags), all six registers, and the memory window.
- **model.py** — an interpreter for the tested subset written from
  the manual's Operation pseudocode, sharing no code with any
  emulator. Ambiguous readings are marked `# READING:`.
- **gen.py** — vector tiers: 0 harness-trust smoke, 1 loads/stores/
  branches, 2 ALU/inc/dec/shift/rotate, 3 MUL/DIV, 4 BIG core
  (including divide-with-remainder), 5 stack ops, 6 MEM block
  operations and MVL, 7 BIG completion (CTB/CFB, all operand specs),
  8 SVC/RSV round trips with frame capture, 9 seeded random soup
  (straight-line compositions — this is what catches
  flag-interaction rules single-op vectors cannot), 11/12 addressing
  and ALU completion sweeps. `--tiers all` runs everything.
- **shrink.py** — given a report with failing soup vectors, replays
  each against the microcode simulator (needs the emulator repo's
  harness) and bisects to the first instruction where the model and
  the microcode disagree.

## Running

Against the emulator (spawns `cen diag 0a --telnet`):

```
./run.py --emulator ~/Projects/centurion-emu --tiers 0,1,2,3,4,5
```

Against real hardware, with the DIAG board DIP set to 0x0A (TOS) and
a serial adapter on the console port (needs pyserial):

```
./run.py --serial /dev/ttyUSB0:9600 --tiers 0 --verbose   # smoke first
./run.py --serial /dev/ttyUSB0:9600 --tiers 0,1,2,3,4,5
```

Run tier 0 first on a new target: it exercises only the instructions
the kernel itself depends on. If tier 0 fails, nothing else is
meaningful.

A disagreement is evidence about *two* artifacts: the target and the
manual. On the emulator it usually means an emulator bug; on real
hardware it may mean the manual (and everything derived from it) is
wrong — those are the most valuable results this suite can produce.
Compare `report.jsonl` files from an emulator run and a hardware run
to separate the two.

## TOS interface notes (empirically mapped)

- Sign-on `846F`, prompt `\`.
- `M<addr16><space>` then `XX ` per byte deposits memory (TOS echoes
  the next location's current value after each space); any non-hex
  character aborts to the prompt.
- `G<addr16><space>` jumps. `Q` restarts TOS.
- The kernel loads at 0x4000, its stack at 0x5F00, test code slot at
  0x4D00, test memory window at 0x6000 — chosen clear of TOS's
  low-RAM workspace and the DIAG ROMs at 0x8000.

## Results (2026-06-06, against the emulator)

Full suite: 1729 vectors, 1729 pass. Bringing the suite up found ten
errors in the manual — indexed-mode-byte bit positions, INX/DCX step
size, DIV's dividend width and result placement, IVRB's
carry/overflow flags (and the n = 0 pure-complement case that
preserves them), rotate-left's fault flag, right shifts/rotates
preserving F, MUL clearing L, DIV clearing F on success — all
arbitrated against the microcode simulator and corrected — plus one
real emulator bug (SLR by the full register width must set FAULT when
the sign drains out). Most of the flag-policy rules fell out of the
random-soup tier, which composes instructions so the *incoming* flag
state varies — single-op vectors all enter with clean flags and
cannot distinguish "cleared" from "preserved". A manual-only suite
catching both kinds of error is the point of building it this way.

Coverage: every non-system opcode (loads/stores in all modes
including the one-byte register-pointer rows, branches, byte/word
ALU with all CPU6 sub-modes, register-constant rows with memory
forms, all one-byte aliases, MUL/DIV in all forms, BIG sub-ops 0-9
with all operand specs, MEM block ops, MVL, STR, LST/SST, SAR/LAR,
flag ops, PCX, SVC/RSV). Excluded as untestable under a monitor:
HLT, EI/DI, RI, PAGE, DMA, LIO/SIO, the parity and clock controls,
sense-switch branches (panel-state dependent), and the MEM record
loader (planned).
