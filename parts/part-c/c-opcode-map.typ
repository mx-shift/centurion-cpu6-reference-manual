= Appendix A: Opcode Map

Generated from `data/opcodes.yaml` — the machine-readable index shared
with the emulator (whose decode table is CI-checked against it, and
which passes the community's 248-test opcode suite in lockstep with
the reference microcode simulator).

#let ops = yaml("../../data/opcodes.yaml")

#let hex2(i) = {
  let h = upper(str(i, base: 16))
  if i < 16 { "0" + h } else { h }
}

#let cell(i) = {
  let e = ops.at("0x" + hex2(i), default: none)
  if e == none { [—] }
  else if e.at("illegal", default: false) {
    text(fill: gray, size: 6pt)[ill]
  } else {
    text(size: 6pt, font: "Source Code Pro")[#e.mnemonic]
  }
}

#table(
  columns: (auto,) + (1fr,) * 16,
  stroke: 0.4pt,
  inset: 2.5pt,
  align: center,
  table.header(
    [], ..range(16).map(c => text(size: 6.5pt, weight: "bold")[\_#upper(str(c, base: 16))]),
  ),
  ..range(16).map(r => (
    (text(size: 6.5pt, weight: "bold")[#upper(str(r, base: 16))\_],)
      + range(16).map(c => cell(r * 16 + c))
  )).flatten(),
)
