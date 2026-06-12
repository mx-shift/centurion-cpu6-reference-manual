#import "../../../lib/instruction.typ": *

// The load/store half of the opcode space: rows 0x60-0x6D (X), and
// 0x80-0xFF (A and B, byte and word), all sharing one mode pattern.
// Every load/store is its own complete entry; the shared mode-family
// encoding is produced by the helpers below so each entry repeats the
// full details rather than referring elsewhere.

#let _mode-family-decode = [
  ```cpu6
  mode: 000 =   immediate (byte or word literal)
        001 /   direct: EA = addr16
        010 $   indirect: EA = MemW[addr16]
        011     relative: EA = PC + disp8 (signed)
        100 *   relative indirect: EA = MemW[PC + disp8]
        101 +/− indexed: a mode byte follows (§A5)
  ```
]

#let _mode-family(name) = encoding(
  "Mode family",
  applicability: "CPU4/5/6",
  asm: name + "= / " + name + "/ / " + name + "$ / " + name + " (rel) / " + name + "* / " + name + "+idx / " + name + "−idx",
  diagram: bitbox(
    ((name: "row", bits: 5), (name: "mode", bits: 3)),
    ((name: "operand bytes per mode", bits: 16),),
  ),
  decode: _mode-family-decode,
)

#let _implicit-ptr(name) = encoding(
  "Implicit register pointer",
  applicability: "CPU4/5/6",
  asm: name + "+ <reg>  (one byte)",
  diagram: bitbox(
    ((name: "row", bits: 5), (bits: 3, value: "1rr"),),
  ),
  decode: [
    ```cpu6
    // opcodes row+8 … row+15: EA = R[A B X Y Z S C P],
    // a one-byte encoding of the plain indexed mode
    ```
  ],
)

#let _access(reg, width) = if width == "word" { reg + " = MemW[EA]" } else { reg + " = Mem[EA]" }

#let _load(name, reg, width, rows, note: none) = instruction(
  name,
  qualifier: "(load " + width + " into " + reg + ")",
  summary: [
    Load #raw(reg) from an immediate, from memory, or through a pointer,
    using the six addressing modes selected by the opcode's low three
    bits (rows #rows).#if width == "word" [ Word values are big-endian in
    memory.] The loaded value sets M and V.
  ],
  encodings: (_mode-family(name), _implicit-ptr(name)),
  operation: raw(
    "value = " + (if width == "word" { "MemW[EA]" } else { "Mem[EA]" }) + "\n"
      + reg + " = value\n"
      + "MINUS = sign(value); VALUE = IsZero(value)",
    lang: "cpu6", block: true),
  flags: flags-affected(minus: "*", value: "*"),
  notes: note,
)

#let _store(name, reg, width, rows, note: none) = instruction(
  name,
  qualifier: "(store " + width + " from " + reg + ")",
  summary: [
    Store #raw(reg) to memory through the six addressing modes (rows
    #rows). The immediate mode stores over the inline literal — legal,
    and used by self-modifying idioms. M and V are set from the stored
    value.
  ],
  encodings: (_mode-family(name), _implicit-ptr(name)),
  operation: raw(
    "Mem[EA] = " + reg + (if width == "word" { "      // word, big-endian" } else { "       // byte" }) + "\n"
      + "MINUS = sign(" + reg + "); VALUE = IsZero(" + reg + ")",
    lang: "cpu6", block: true),
  flags: flags-affected(minus: "*", value: "*"),
  notes: note,
)

#_load("LDA", "A", "word", "0x90–0x9F",
  note: [`LST` (0x6E) is the companion "load status": it loads the flag
    nibble from the high nibble of a memory byte, leaving the low
    nibble of C untouched.])
#_load("LDAB", "AL", "byte", "0x80–0x8F")
#_load("LDB", "B", "word", "0xD0–0xDF")
#_load("LDBB", "BL", "byte", "0xC0–0xCF")
#_load("LDX", "X", "word", "0x60–0x65")

#_store("STA", "A", "word", "0xB0–0xBF",
  note: [`SST` (0x6F) stores the flag nibble into the high nibble of a
    memory byte.])
#_store("STAB", "AL", "byte", "0xA0–0xAF")
#_store("STB", "B", "word", "0xF0–0xFF")
#_store("STBB", "BL", "byte", "0xE0–0xEF")
#_store("STX", "X", "word", "0x68–0x6D")
