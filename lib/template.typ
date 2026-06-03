// Document template: page geometry, heading numbering in the ARM style
// ("A1", "B2.7.1"), part divider pages, running headers.

#import "theme.typ": *

// The current part letter ("A", "B", "C"), consumed by heading numbering
// and the running footer.
#let part-letter = state("part-letter", "")

// Begin a new part: full divider page, reset chapter numbering.
#let part(letter, title) = {
  pagebreak(weak: true)
  part-letter.update(letter)
  counter(heading).update(0)
  v(30%)
  align(center)[
    #text(font: heading-font, size: 14pt, weight: "bold")[Part #letter]
    #v(1em)
    #text(font: heading-font, size: 24pt, weight: "bold")[#title]
  ]
  pagebreak()
}

// Front-matter sections (unnumbered chapter-level headings).
#let front-chapter(title) = {
  pagebreak(weak: true)
  heading(level: 1, numbering: none, title)
}

#let manual(
  title: "",
  subtitle: "",
  version: "",
  footer-title: "Centurion CPU6 Instruction Set Reference Manual",
  body,
) = {
  set document(title: title)
  set page(
    paper: "us-letter",
    margin: (top: 2.2cm, bottom: 2.4cm, inside: 2.6cm, outside: 2.0cm),
    header: context {
      let chapters = query(selector(heading.where(level: 1)).before(here()))
      if chapters.len() > 0 {
        let c = chapters.last()
        set text(font: heading-font, size: 8pt)
        emph(c.body)
        line(length: 100%, stroke: 0.5pt + rule-gray)
      }
    },
    footer: context {
      set text(font: heading-font, size: 8pt)
      line(length: 100%, stroke: 0.5pt + rule-gray)
      let letter = part-letter.get()
      let pageno = counter(page).display()
      grid(
        columns: (1fr, auto),
        [#footer-title],
        if letter == "" [#pageno] else [#letter‑#pageno],
      )
    },
  )
  set text(font: body-font, size: body-size)
  set par(justify: true, leading: 0.62em)

  // ARM-style heading numbers: level 1 -> "A1", level 2 -> "A1.2", ...
  set heading(numbering: (..nums) => context {
    part-letter.get() + nums.pos().map(str).join(".")
  })
  show heading: it => {
    set text(font: heading-font, weight: "bold")
    let sizes = ("1": 16pt, "2": 12pt, "3": 10.5pt)
    set text(size: sizes.at(str(it.level), default: 10pt))
    v(if it.level == 1 { 1.4em } else { 1.0em })
    if it.level == 1 and it.numbering != none {
      pagebreak(weak: true)
    }
    block(it)
    v(0.5em)
  }
  show raw: set text(font: mono-font, size: mono-size)

  // Title page.
  v(25%)
  align(center)[
    #text(font: heading-font, size: 26pt, weight: "bold")[#title]
    #v(0.6em)
    #text(font: heading-font, size: 14pt)[#subtitle]
    #v(2em)
    #text(font: heading-font, size: 10pt)[#version]
  ]
  pagebreak()

  body
}
