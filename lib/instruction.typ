// The per-instruction description template (ARM ARM chapter A7 style).
// Every instruction entry in Part B is produced by #instruction so the
// manual stays uniform.

#import "theme.typ": *
#import "bitfield.typ": bitbox, opbits

// Instruction entries register themselves here as (sort-key, content)
// pairs instead of rendering in place, so the chapter can emit them in
// alphabetical order (matching the bookmark/Contents order a reader scans
// to look an instruction up). emit-instructions() places them, sorted.
#let _instr-list = state("cen-instrs", ())
#let emit-instructions() = context {
  for e in _instr-list.final().sorted(key: e => lower(e.first())) {
    e.last()
  }
}

// One encoding variant of an instruction (≙ ARM's "Encoding T1" block).
//
//   label:         short variant name shown in bold ("Register-register")
//   applicability: which CPUs have it ("CPU4/5/6", "CPU6")
//   asm:           assembler form for this encoding ("ADD <Sreg>, <Dreg>")
//   diagram:       a #bitbox(..) for this encoding
//   decode:        optional decode pseudocode (raw block)
#let encoding(label, applicability: "CPU6", asm: none, diagram: none, decode: none) = (
  label: label,
  applicability: applicability,
  asm: asm,
  diagram: diagram,
  decode: decode,
)

// The flags-affected box. Each of fault/link/minus/value takes a short
// marker: "—" untouched, "*" set from result, or descriptive content.
#let flags-affected(fault: "—", link: "—", minus: "—", value: "—") = {
  set text(size: 8.5pt)
  table(
    columns: (auto, auto, auto, auto),
    align: center,
    stroke: 0.5pt,
    inset: 4pt,
    table.header([*F* (fault)], [*L* (link)], [*M* (minus)], [*V* (value)]),
    fault, link, minus, value,
  )
}

#let _section(title) = {
  v(0.8em)
  text(font: heading-font, weight: "bold", size: 9.5pt)[#title]
  v(0.3em)
}

// The instruction entry. Renders, in fixed order: heading, summary,
// encodings, assembler syntax, operation, flags, exceptions, notes,
// example.
//
//   name:       canonical mnemonic ("ADD")
//   qualifier:  disambiguator shown in the heading ("(register)")
//   summary:    one-paragraph prose description
//   encodings:  array of #encoding(..) values
//   syntax:     content: canonical syntax line(s) + "where:" field list
//   operation:  content: pseudocode raw block
//   flags:      a #flags-affected(..) value (none = flags untouched)
//   exceptions: content (default "None.")
//   notes:      optional content: caveats, CPU-generation differences
//   example:    optional content: worked example (often from the wiki)
#let instruction(
  name,
  qualifier: none,
  summary: [],
  encodings: (),
  syntax: none,
  operation: none,
  flags: none,
  exceptions: [None.],
  notes: none,
  example: none,
) = {
  let content = {
  // Structural level 3: an instruction entry is a section under the
  // level-2 "Instruction Descriptions" chapter (Part B is offset by one,
  // but an explicit heading level — unlike markup `==` — ignores the
  // offset, so it is set directly). Logical level 2 → numbered "B2.n".
  // supplement: [instruction] marks it so the template's heading show
  // rule starts each instruction entry on a fresh page (architecture
  // sections sit at the same level but must not break).
  heading(level: 3, supplement: [instruction])[#name#if qualifier != none [ #qualifier]]
  summary

  for enc in encodings {
    v(0.8em)
    grid(
      columns: (1fr, auto),
      text(font: heading-font, weight: "bold", size: 9.5pt)[Encoding: #enc.label],
      text(font: heading-font, size: 8.5pt, fill: rule-gray)[#enc.applicability],
    )
    if enc.asm != none {
      v(0.3em)
      raw(enc.asm)
    }
    if enc.diagram != none {
      v(0.4em)
      enc.diagram
    }
    if enc.decode != none {
      v(0.3em)
      enc.decode
    }
  }

  if syntax != none {
    _section[Assembler syntax]
    syntax
  }
  if operation != none {
    _section[Operation]
    operation
  }
  _section[Flags affected]
  if flags == none [None.] else { flags }
  _section[Exceptions]
  exceptions
  if notes != none {
    _section[Notes]
    notes
  }
  if example != none {
    _section[Example]
    example
  }
  v(1.2em)
  line(length: 100%, stroke: 0.5pt + rule-gray)
  }
  // Register rather than render; emit-instructions() places it in
  // alphabetical order. `name` is the sort key (first mnemonic).
  _instr-list.update(l => l + ((name, content),))
}

// "where:" operand glossary entry, used inside the syntax block.
#let syntax-field(placeholder, description) = {
  grid(
    columns: (7em, 1fr),
    column-gutter: 1em,
    raw(placeholder),
    description,
  )
  v(0.2em)
}
