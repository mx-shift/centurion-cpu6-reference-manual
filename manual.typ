#import "lib/template.typ": manual, part, front-chapter
#import "lib/pseudocode.typ": pseudocode-show

#show: pseudocode-show
#show: manual.with(
  title: "Centurion Computer",
  subtitle: "CPU6 Instruction Set Reference Manual",
  version: "Draft — work in progress",
)

#include "parts/front/credits.typ"
#include "parts/front/conventions.typ"

#outline(depth: 2)

#part("A", "Architecture")
#include "parts/part-a/a1-introduction.typ"

#part("B", "Instruction Set")
#include "parts/part-b/b1-about.typ"
#include "parts/part-b/b2-instructions.typ"

#part("C", "Appendices")
#include "parts/part-c/c-pseudocode.typ"
