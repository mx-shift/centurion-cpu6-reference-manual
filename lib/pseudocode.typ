// Rendering for the manual's pseudocode language (defined in Appendix C).
// Use fenced raw blocks tagged `cpu6`:
//
//   ```cpu6
//   (result, carry, overflow) = AddWithCarry(A, operand, 0)
//   ```

#import "theme.typ": *

#let pseudocode-show(body) = {
  show raw.where(lang: "cpu6"): it => block(
    width: 100%,
    inset: (x: 10pt, y: 7pt),
    fill: luma(247),
    stroke: (left: 1.5pt + accent),
    text(font: mono-font, size: mono-size, it),
  )
  body
}
