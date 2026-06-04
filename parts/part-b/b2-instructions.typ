= Instruction Descriptions

The descriptions are grouped by function. Within each entry, every
encoding variant appears with its applicability, byte layout, and
decode rule; semantics marked _microcode-verified_ were established by
lockstep comparison against the reference microcode simulator and the
community's on-machine opcode test suite (248 tests, all matching).

#include "instructions/control.typ"
#include "instructions/branches.typ"
#include "instructions/regops-byte.typ"
#include "instructions/regops-word.typ"
#include "instructions/alu.typ"
#include "instructions/loads-stores.typ"
#include "instructions/jumps.typ"
#include "instructions/muldiv.typ"
#include "instructions/system.typ"
#include "instructions/extended.typ"
#include "instructions/illegal.typ"
