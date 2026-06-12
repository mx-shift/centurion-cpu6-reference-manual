// Document template: page geometry, heading numbering in the ARM style
// ("A1", "B2.7.1"), part divider pages, running headers.
//
// Heading-level scheme (so the PDF bookmark tree nests chapters under
// their part):
//   * A part is a structural level-1 heading — bookmarked into the PDF
//     outline but kept out of the printed Contents (outlined: false), and
//     rendered as a full divider page by the show rule.
//   * Inside a part, manual.typ raises the heading offset by one, so a
//     chapter file's `=` is structural level 2, `==` is level 3, and so on.
//     The chapter therefore bookmarks as a child of its part.
//   * Front-matter chapters stay at structural level 1 (no part parent).
// The visible numbering and the running header use the *logical* level
// (chapter = 1, section = 2, …), recovered by dropping the part's level
// inside a part, so neither the "A1.2" numbers nor the printed Contents
// change.

#import "theme.typ": *

// The current part letter ("A", "B", "C"), consumed by heading numbering,
// the running footer, and the logical-level computation.
#let part-letter = state("part-letter", "")

// True while inside the appendix part: its divider reads simply
// "Appendices" (no "Part C"), and its chapters are labelled in their own
// titles ("Appendix A: …") rather than auto-numbered.
#let appendix-mode = state("appendix-mode", false)

// A heading is a part divider iff it is bookmarked into the PDF outline
// yet excluded from the printed Contents — the signature part() sets, and
// nothing else (front-matter chapters are outlined; the outline's own
// "Contents" title heading is neither bookmarked nor outlined).
#let _is-part(h) = h.outlined == false and h.bookmarked == true

// Logical level of a normal (non-part) heading: chapters are 1, sections
// 2, …. Inside a part the structural level is one deeper than logical.
#let _logical(level, letter) = if letter == "" { level } else { level - 1 }

// Begin a new part. Emits the bookmark anchor / divider heading; the show
// rule paints the actual divider page. Resets chapter numbering. Set
// appendix: true for the appendices (see appendix-mode above).
#let part(letter, title, appendix: false) = {
  part-letter.update(letter)
  appendix-mode.update(appendix)
  counter(heading).update(0)
  heading(level: 1, numbering: none, outlined: false, bookmarked: true)[#title]
}

// Front-matter sections (unnumbered chapter-level headings, no part parent).
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
      // The running header shows the current chapter: a front-matter
      // chapter (level-1, outlined) or, inside a part, a part chapter
      // (level-2). Part dividers and section headings are skipped.
      let chapters = query(selector(heading).before(here())).filter(h => {
        // front-matter chapter (level-1, outlined — excludes part dividers
        // and the outline's own non-outlined "Contents" title) …
        if h.level == 1 and h.outlined == true { return true }
        // … or a part chapter (level-2 inside a part).
        if h.level == 2 and part-letter.at(h.location()) != "" { return true }
        return false
      })
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
      // Part pages are located as "A-7"; front matter and the appendices
      // (which are not a lettered part) use a plain page number.
      grid(
        columns: (1fr, auto),
        [#footer-title],
        if letter == "" or appendix-mode.get() [#pageno] else [#letter‑#pageno],
      )
    },
  )
  set text(font: body-font, size: body-size)
  set par(justify: true, leading: 0.62em)

  // ARM-style heading numbers: "A1", "A1.2", …. The leading counter
  // component inside a part is the part's own level-1 count; drop it and
  // prefix the part letter instead. Front matter (no part letter) is
  // unnumbered.
  set heading(numbering: (..nums) => context {
    let letter = part-letter.get()
    if letter == "" { return none }
    if appendix-mode.get() { return none }  // appendices label themselves
    let n = nums.pos()
    if n.len() < 2 { return none }
    letter + n.slice(1).map(str).join(".")
  })
  show heading: it => context {
    let letter = part-letter.get()
    if _is-part(it) {
      // Part divider page. The appendices are titled simply "Appendices"
      // (their own title), without a "Part C" super-label.
      pagebreak(weak: true)
      v(30%)
      align(center)[
        #if not appendix-mode.get() {
          text(font: heading-font, size: 14pt, weight: "bold")[Part #letter]
          v(1em)
        }
        #text(font: heading-font, size: 24pt, weight: "bold")[#it.body]
      ]
      // No trailing page break: the part's first chapter does its own
      // (weak) break onto the next page, so the divider stands alone
      // without an intervening blank page.
    } else {
      let logical = _logical(it.level, letter)
      // The page break must come BEFORE any spacing: emitting vertical
      // space ahead of it leaves the heading's introspected location on the
      // pre-break page, which throws the Contents page numbers off by one.
      // A chapter (logical level 1) inside any part starts a new page —
      // including unnumbered appendix chapters; front-matter chapters
      // (letter == "") break themselves in front-chapter(). Each
      // instruction entry (marked supplement: [instruction]) likewise
      // starts a fresh page, so its heading sits at the top.
      if (logical == 1 and letter != "") or it.supplement == [instruction] {
        pagebreak(weak: true)
      } else {
        v(if logical == 1 { 1.4em } else { 1.0em })
      }
      set text(font: heading-font, weight: "bold")
      let sizes = ("1": 16pt, "2": 12pt, "3": 10.5pt)
      set text(size: sizes.at(str(logical), default: 10pt))
      block(it)
      v(0.5em)
    }
  }
  show raw: set text(font: mono-font, size: mono-size)

  // Printed Contents: indent by logical level so a part's chapters line up
  // with the front-matter chapters (both logical level 1), even though a
  // part chapter is structurally one level deeper than a front chapter.
  // (The outline's own per-level indent is disabled via indent: 0pt at the
  // #outline call.)
  show outline.entry: it => context {
    let logical = _logical(it.level, part-letter.at(it.element.location()))
    pad(left: (logical - 1) * 1.2em, it.indented(it.prefix(), it.inner()))
  }

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
