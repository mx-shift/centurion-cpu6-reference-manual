#import "lib/template.typ": manual, part, front-chapter
#import "lib/pseudocode.typ": pseudocode-show

#show: pseudocode-show
#show: manual.with(
  title: "Centurion Computer",
  subtitle: "CPU6 Instruction Set Reference Manual",
  version: "Draft 0.2",
)

#include "parts/front/credits.typ"
#include "parts/front/conventions.typ"

// Parts are structural level-1 headings; inside each part the heading
// offset is raised by one so a chapter file's `=` becomes level 2 and
// bookmarks as a child of its part. depth: 3 keeps chapters and their
// sections in the printed Contents (now levels 2 and 3 inside a part).
#pagebreak(weak: true)
#outline(depth: 3, indent: 0pt)

#part("A", "Architecture")
#[
  #set heading(offset: 1)
  #include "parts/part-a/a1-introduction.typ"
  #include "parts/part-a/a2-model.typ"
  #include "parts/part-a/a3-memory.typ"
  #include "parts/part-a/a4-exceptions.typ"
  #include "parts/part-a/a5-addressing.typ"
]

#part("B", "Instruction Set")
#[
  #set heading(offset: 1)
  #include "parts/part-b/b1-about.typ"
  #include "parts/part-b/b2-instructions.typ"
  #include "parts/part-b/b3-illegal.typ"
]

#part("C", "Appendices", appendix: true)
#[
  #set heading(offset: 1)
  #include "parts/part-c/c-opcode-map.typ"
  #include "parts/part-c/c-pseudocode.typ"
]
