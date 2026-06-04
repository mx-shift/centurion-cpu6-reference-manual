#import "../../../lib/instruction.typ": *

// The load/store half of the opcode space: rows 0x60-0x6D (X), and
// 0x80-0xFF (A and B, byte and word), all sharing one mode pattern.

#instruction(
  "LDA / LDB / LDX / LDAB / LDBB",
  qualifier: "(loads)",
  summary: [
    Load a register from an immediate, from memory, or through a
    pointer. Each load row provides the same six addressing modes,
    selected by the opcode's low three bits; rows exist for A and B at
    byte and word width and for X at word width. Word values are
    big-endian in memory. The loaded value sets M and V.
  ],
  encodings: (
    encoding(
      "Mode family",
      applicability: "CPU4/5/6",
      asm: "LDr= / LDr/ / LDr$ / LDr (rel) / LDr* / LDr±idx",
      diagram: bitbox(
        ((name: "row", bits: 5), (name: "mode", bits: 3)),
        ((name: "operand bytes per mode", bits: 16),),
      ),
      decode: [
        ```cpu6
        mode: 000 =   immediate (byte or word literal)
              001 /   direct: EA = addr16
              010 $   indirect: EA = MemW[addr16]
              011     relative: EA = PC + disp8 (signed)
              100 *   relative indirect: EA = MemW[PC + disp8]
              101 ±   indexed: a mode byte follows (§A5)
        ```
      ],
    ),
    encoding(
      "Implicit register pointer",
      applicability: "CPU4/5/6",
      asm: "LDr+ <reg>  (one byte)",
      diagram: bitbox(
        ((name: "row", bits: 5), (bits: 3, value: "1rr"),),
      ),
      decode: [
        ```cpu6
        // opcodes row+8 … row+15: EA = R[A B X Y Z S C P],
        // a one-byte encoding of the plain indexed mode
        ```
      ],
    ),
  ),
  syntax: [
    #table(
      columns: (auto, auto, auto, auto),
      stroke: 0.5pt,
      inset: 4pt,
      table.header([*Rows*], [*Mnemonic*], [*Width*], [*Register*]),
      [80–8F], [`LDAB`], [byte], [`AL`],
      [90–9F], [`LDA`],  [word], [`A`],
      [C0–CF], [`LDBB`], [byte], [`BL`],
      [D0–DF], [`LDB`],  [word], [`B`],
      [60–65], [`LDX`],  [word], [`X`],
    )
  ],
  operation: [
    ```cpu6
    value  = Mem[EA]  (byte)  or  MemW[EA]  (word)
    R[dst] = value
    MINUS  = sign(value); VALUE = IsZero(value)
    ```
  ],
  flags: flags-affected(minus: "*", value: "*"),
  notes: [
    `LST` (0x6E) is the companion "load status": it loads the flag
    nibble from the high nibble of a memory byte, leaving the low
    nibble of C untouched.
  ],
)

#instruction(
  "STA / STB / STX / STAB / STBB",
  qualifier: "(stores)",
  summary: [
    Store a register to memory through the same mode family as the
    loads (the immediate mode stores over the inline literal — legal,
    and used by self-modifying idioms). M and V are set from the
    stored value.
  ],
  encodings: (
    encoding(
      "Mode family",
      applicability: "CPU4/5/6",
      asm: "STr= / STr/ / STr$ / STr (rel) / STr* / STr±idx",
      diagram: bitbox(
        ((name: "row", bits: 5), (name: "mode", bits: 3)),
        ((name: "operand bytes per mode", bits: 16),),
      ),
    ),
  ),
  syntax: [
    #table(
      columns: (auto, auto, auto, auto),
      stroke: 0.5pt,
      inset: 4pt,
      table.header([*Rows*], [*Mnemonic*], [*Width*], [*Register*]),
      [A0–AF], [`STAB`], [byte], [`AL`],
      [B0–BF], [`STA`],  [word], [`A`],
      [E0–EF], [`STBB`], [byte], [`BL`],
      [F0–FF], [`STB`],  [word], [`B`],
      [68–6D], [`STX`],  [word], [`X`],
    )
  ],
  operation: [
    ```cpu6
    Mem[EA] = R[src]      // byte or word, big-endian
    MINUS = sign(value); VALUE = IsZero(value)
    ```
  ],
  flags: flags-affected(minus: "*", value: "*"),
  notes: [
    `SST` (0x6F) stores the flag nibble into the high nibble of a
    memory byte. Rows +8…+15 are the one-byte implicit register
    pointer forms, as for the loads.
  ],
)
