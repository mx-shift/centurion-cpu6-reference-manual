#import "../../../lib/instruction.typ": *

// The four sub-dispatched families: PAGE (0x2E), DMA (0x2F),
// BIGNUM (0x46), MEMBLOCK (0x47/0x67).

#instruction(
  "PAGE",
  qualifier: "(page-table access, 0x2E)",
  summary: [
    Read and write the MMU page tables (eight maps of 32 entries; see
    §A3). A selector byte picks the operation and addressing form, a
    count byte packs an entry count or start index with the map
    number, and an address locates the in-memory table. The block
    forms translate their start address once and then step
    *physically*, which lets the active map rewrite its own entries.
    CPU6 only.
  ],
  encodings: (
    encoding(
      "Direct",
      applicability: "CPU6",
      asm: "PAGE <sub>, <n|map>, <addr>",
      diagram: bitbox(
        ((bits: 8, value: "00101110"),),
        ((name: "sub", bits: 4), (bits: 4, value: "1100"),),
        ((name: "n", bits: 5), (name: "map", bits: 3)),
        ((name: "addr", bits: 16),),
      ),
      decode: [
        ```cpu6
        sub: 0 load entries 0…n      1 store entries 0…n
             2 load single entry n   3 store single entry n
             4 rotated full-map load: entry (n+i) mod 32 = src[i]
             5 store entries 0…n (write-tracking variant)
        ```
      ],
    ),
    encoding(
      "Register-indexed",
      applicability: "CPU6",
      asm: "PAGE <sub>, <n|map>, <reg>, <disp8>",
      diagram: bitbox(
        ((bits: 8, value: "00101110"),),
        ((name: "sub", bits: 4), (bits: 4, value: "1101"),),
        ((name: "n", bits: 5), (name: "map", bits: 3)),
        ((name: "reg", bits: 4), (bits: 4, value: "0000"),),
        ((name: "disp (signed)", bits: 8),),
      ),
      decode: [
        ```cpu6
        // EA = R[reg] + SignExtend(disp8); the selector byte's
        // high nibble names a word register (0 = A, 2 = B, …)
        ```
      ],
    ),
  ),
  operation: [
    ```cpu6
    base = PhysicalAddress(EA)    // translated once
    load:  PageRam[map*32 + i] = PhysMem[base + i]
    store: PhysMem[base + i] = PageRam[map*32 + i]
    ```
  ],
  flags: none,
  exceptions: [Store sub-ops through a write-tracked page raise the
    write-track trap after completing (§A4).],
  notes: [
    The operating system keeps each task's map image in its task
    block and uses the indexed forms to save and reload whole maps on
    every dispatch. All forms microcode-verified, including the
    rotated sub-op 4.
  ],
)

#instruction(
  "DMA",
  qualifier: "(DMA controller, 0x2F)",
  summary: [
    Program the processor-board DMA channel. The selector byte's low
    nibble picks the operation and its high nibble a word register
    operand. Transfers proceed a byte per instruction boundary while
    enabled, walking the address register through the MMU; the
    transfer ends when the count register wraps to 0xFFFF. CPU6 only
    (the CPU4 used an external DMA card instead).
  ],
  encodings: (
    encoding(
      "Selector",
      applicability: "CPU6",
      asm: "DMA <op>, <reg>",
      diagram: bitbox(
        ((bits: 8, value: "00101111"),),
        ((name: "reg", bits: 4), (name: "op", bits: 4)),
      ),
      decode: [
        ```cpu6
        op: 0 set address     1 read address
            2 set count       3 read count
            4/5 set device    6 enable   7 disable
            8 set int level   9 read status
        ```
      ],
    ),
  ),
  flags: none,
)

#instruction(
  "BIG",
  qualifier: "(multi-byte integers, 0x46)",
  summary: [
    Arithmetic on big-endian two's-complement integers of 1–16 bytes.
    A length byte carries source and destination lengths (each nibble
    + 1), a selector byte the sub-operation and operand specs
    (inline address, register pointer, or — for sources — an inline
    literal). Sub-operations include load/store, add, subtract,
    compare, negate, and shifts. CPU6 only.
  ],
  encodings: (
    encoding(
      "Length + selector",
      applicability: "CPU6",
      asm: "ZAD= <lit>, /<dst>(<len>)   (and family)",
      diagram: bitbox(
        ((bits: 8, value: "01000110"),),
        ((name: "srclen−1", bits: 4), (name: "dstlen−1", bits: 4)),
        ((name: "subop", bits: 4), (name: "sspec", bits: 2), (name: "dspec", bits: 2)),
        ((name: "operand bytes per spec", bits: 16),),
      ),
    ),
  ),
  flags: flags-affected(fault: [arith: overflow], link: [arith: carry],
    minus: "*", value: "*"),
  notes: [
    The assembler surfaces this family as `ZAD ZSU ZCM ZNG …` with
    parenthesised byte lengths. Operand specs allow degenerate but
    legal combinations (literal-to-literal); see the optest sources
    for exhaustive examples.
  ],
)

#instruction(
  "MEM",
  qualifier: "(memory block operations, 0x47 / 0x67)",
  summary: [
    The block family: fill, move, compare, scan, and the boot
    loader's record interpreter. A selector byte picks the
    sub-operation; operands follow as base/index register
    specifications. The 0x67 row is the reversed-direction variant
    set. CPU6 only.
  ],
  encodings: (
    encoding(
      "Selector",
      applicability: "CPU6",
      asm: "FIL(<n>)=<v>, /<dst>   (and family)",
      diagram: bitbox(
        ((bits: 8, value: "01000111"),),
        ((name: "sub", bits: 4), (name: "spec", bits: 4)),
        ((name: "operand bytes per spec", bits: 16),),
      ),
    ),
  ),
  flags: flags-affected(value: "*", minus: "*"),
  notes: [
    Sub-operation 0 is the *record loader* used by the bootstrap and
    by executable files: it interprets a stream of
    `[type][len][offset₁₆][payload…][checksum]` records (byte sum ≡ 0
    mod 256). Type 0 copies the payload to base + offset; type 1
    treats the payload as a list of fixup locations, adding the load
    delta to each word; a record of length 0 ends a section; a bare
    0x80 byte ends the stream with A preserved. On success Z advances
    past the record and A holds base + offset. Microcode-verified
    against 992 boot-time invocations.
  ],
)
