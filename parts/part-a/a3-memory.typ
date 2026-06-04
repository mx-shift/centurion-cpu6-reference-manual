= Memory Model

== Address spaces

Programs use 16-bit virtual addresses. The MMU translates them to an
18-bit physical space (256 KiB) in 2 KiB pages: the virtual page
number (high five bits) indexes the active map, and the selected
entry's low seven bits replace it.

```cpu6
entry = PageRam[PTA*32 + va<15:11>]
pa    = entry<6:0> : va<10:0>      // 18-bit physical address
```

== Page maps

The page RAM holds eight maps of 32 entries. The *PTA* register names
the active map. PTA is its own piece of processor state — saved into
and restored from the C register's low bits at every level switch,
loaded from an SVC/RSV frame on dispatch, but never altered merely by
reading or writing C as data. The reset state is map 0 with an
identity mapping of low memory.

== Entry bit 7: write tracking

Bit 7 of a page entry marks the page _write-tracked_: reads and
writes both pass through to the underlying page, but a write
additionally traps to level 15 after completing, with cause 2 in `AL`
and the written virtual address in Z. The operating system uses this
to notice mutation of pages it shares or caches.

== Parity

Main memory stores a parity bit per byte, written according to the
SOP/SEP mode and checked on every read; §B's EPE/DPE entry describes
the trap machinery. ROM and I/O regions carry no parity and never
disturb the latch.

== Physical layout

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt,
  inset: 5pt,
  table.header([*Physical*], [*Contents*]),
  [0x00000–0x000FF], [register file (sixteen 16-byte banks)],
  [0x00100–0x3EFFF], [RAM (machine-dependent ceiling)],
  [0x3F000–0x3FBFF], [I/O cards (virtual 0xF000–0xFBFF through the
    standard map: MUX at F200, Hawk disk at F140, printer at F0E0,
    FFC floppy at F800)],
  [0x3FC00–0x3FDFF], [bootstrap ROM (reset enters at 0xFD00)],
)
