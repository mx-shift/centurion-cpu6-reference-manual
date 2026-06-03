// Shared style tokens, approximating the ARM ARM look with free fonts.

// Liberation Serif/Sans are static fonts (Fedora's Noto is variable-only,
// which Typst does not support) and Liberation Serif's Times metrics are
// close to the ARM ARM's body face anyway.
#let body-font = "Liberation Serif"
#let heading-font = "Liberation Sans"
#let mono-font = "Source Code Pro"

#let body-size = 9.5pt
#let mono-size = 8.5pt

// ARM uses a muted blue for some rules/links; keep it subtle.
#let accent = rgb("#27509b")
#let rule-gray = luma(120)
