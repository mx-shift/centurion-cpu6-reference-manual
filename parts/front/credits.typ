#import "../../lib/template.typ": front-chapter

#front-chapter[Preface and Acknowledgments]

This manual documents the instruction set architecture of the Centurion
CPU6 minicomputer processor (Warrex Computer Corporation, circa 1980),
as reconstructed by the retrocomputing community. It is written in the
style of ARM's Architecture Reference Manuals.

This document is licensed under the Creative Commons Attribution 4.0
International license (CC-BY-4.0).

== Sources and acknowledgments

The architecture described here was reverse-engineered by the Centurion
community. This manual builds directly on:

- *David Lovett (Usagi Electric)*, who recovered and restored a working
  Centurion system and documented the effort publicly, catalysing the
  reverse-engineering project. He maintains the *CenturionComputer wiki*
  under the GitHub handle _Nakazoto_
  (https://github.com/Nakazoto/CenturionComputer/wiki) — instruction
  documentation, register and memory models, board-level analysis, and
  worked examples — to which the wider community has contributed.

- *webCenREE / CenRE*, Copyright © 2023 Meisaka Yukara
  (https://github.com/Meisaka/webCenREE) — the reference emulator whose
  opcode tables and instruction semantics inform this manual, used under
  the CenRE license. The above copyright notice is reproduced as that
  license requires. This manual is an independent work and is not
  endorsed by the author of webCenREE.

- The wider *Centurion community* for hardware preservation, microcode
  and disk-format analysis, and the collective reverse-engineering
  effort that this manual records.

Instruction descriptions marked _derived_ were reconstructed from
emulator semantics rather than period documentation and may contain
errors; see the status appendix.
