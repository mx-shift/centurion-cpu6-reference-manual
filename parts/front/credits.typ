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

- *The Nakazoto CenturionComputer wiki* and its contributors
  (https://github.com/Nakazoto/CenturionComputer/wiki) — instruction
  documentation, register and memory models, and worked examples.

- *webCenREE / CenRE*, Copyright © 2023 Meisaka Yukara
  (https://github.com/Meisaka/webCenREE) — the reference emulator whose
  opcode tables and instruction semantics inform this manual, used under
  the CenRE license. The above copyright notice is reproduced as that
  license requires. This manual is an independent work and is not
  endorsed by the author of webCenREE.

- *David Lovett (Usagi Electric)* and the wider Centurion community for
  hardware preservation and the reverse-engineering effort.

Instruction descriptions marked _derived_ were reconstructed from
emulator semantics rather than period documentation and may contain
errors; see the status appendix.
