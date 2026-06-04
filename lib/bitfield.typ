// Boxed bit-field encoding diagrams in the style of the ARM ARM, adapted
// to the CPU6's byte-oriented encodings: an 8-bit opcode optionally
// followed by operand bytes.
//
// Each byte is described by an array of fields, most-significant first:
//   (bits: 8, value: "01101001")          fixed bits, one digit per cell
//   (name: "Sreg", bits: 4)               variable field, name spans cells
//   (name: "disp", bits: 8)               full-byte operand field
// A whole byte may also be given as a plain string of 8 bits.

#import "theme.typ": *

#let _cell(body, leftmost) = box(
  width: 100%,
  inset: (y: 4pt),
  stroke: (
    left: if leftmost { 1pt } else { 0.5pt },
    right: 1pt,
    top: 1pt,
    bottom: 1pt,
  ),
  align(center, body),
)

#let bitbox(..bytes) = {
  let bytes = bytes.pos().map(b => if type(b) == str { ((bits: 8, value: b),) } else { b })
  let total-bits = bytes.map(b => b.map(f => f.bits).sum()).sum()
  set text(font: mono-font, size: 8pt)
  block(breakable: false, width: 100%)[
    // Bit-number ruler, 7..0 repeated per byte.
    #grid(
      columns: (1fr,) * total-bits,
      ..bytes
        .map(b => {
          let w = b.map(f => f.bits).sum()
          range(w).map(i => align(center, text(size: 6.5pt)[#calc.rem(w - 1 - i, 8)]))
        })
        .flatten()
    )
    // Field boxes.
    #grid(
      columns: (1fr,) * total-bits,
      ..{
        let cells = ()
        for (bi, byte) in bytes.enumerate() {
          let used = 0
          for field in byte {
            let leftmost = used == 0
            if "value" in field {
              // Fixed bits: one digit per cell.
              for (i, d) in field.value.clusters().enumerate() {
                cells.push(grid.cell(_cell(raw(d), leftmost and i == 0)))
              }
            } else {
              cells.push(grid.cell(
                colspan: field.bits,
                _cell(text(style: "italic", font: body-font, size: 8pt)[#field.name], leftmost),
              ))
            }
            used += field.bits
          }
          assert(calc.rem(used, 8) == 0, message: "byte " + str(bi) + " has " + str(used) + " bits")
        }
        cells
      }
    )
    // Byte labels underneath.
    #grid(
      columns: (1fr,) * total-bits,
      ..{
        let labels = ()
        let bi = 0
        for byte in bytes {
          let w = byte.map(f => f.bits).sum()
          let label = if w == 8 [byte #bi] else [bytes #bi–#(bi + calc.quo(w, 8) - 1)]
          labels.push(grid.cell(
            colspan: w,
            align(center, text(size: 6.5pt, font: heading-font, fill: rule-gray)[#label]),
          ))
          bi += calc.quo(w, 8)
        }
        labels
      }
    )
  ]
}

// Convenience: render an opcode value as its fixed 8-bit pattern.
#let opbits(op) = {
  let s = ""
  let i = 7
  while i >= 0 {
    s += str(op.bit-and(1.bit-lshift(i)).bit-rshift(i))
    i -= 1
  }
  s
}
