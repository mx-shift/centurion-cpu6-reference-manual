#import "lib/template.typ": manual, part, front-chapter
#import "lib/pseudocode.typ": pseudocode-show

#show: pseudocode-show
#show: manual.with(
  title: "Centurion Computer",
  subtitle: "CPU6 Instruction Set Reference Manual",
  version: "Draft 0.2 — instruction semantics microcode-verified (optest 248/248)",
)

#include "parts/front/credits.typ"
#include "parts/front/conventions.typ"

#outline(depth: 2)

#part("A", "Architecture")
#include "parts/part-a/a1-introduction.typ"
#include "parts/part-a/a2-model.typ"
#include "parts/part-a/a3-memory.typ"
#include "parts/part-a/a4-exceptions.typ"
#include "parts/part-a/a5-addressing.typ"

#part("B", "Instruction Set")
#include "parts/part-b/b1-about.typ"
#include "parts/part-b/b2-instructions.typ"

#part("C", "Appendices")
#include "parts/part-c/c-opcode-map.typ"
#include "parts/part-c/c-pseudocode.typ"
