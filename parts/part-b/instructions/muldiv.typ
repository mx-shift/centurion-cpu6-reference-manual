#import "../../../lib/instruction.typ": *

#instruction(
  "MUL",
  qualifier: "(multiply)",
  summary: [
    Unsigned 16×16 multiply. The destination register names a pair:
    when it is the pair *leader* (A, X, Z, …) the full 32-bit product
    lands in the pair (leader = high word, follower = low); when it is
    the *follower* (B, Y, S, …) only the low 16 bits are written.
    CPU6 only.
  ],
  encodings: (
    encoding(
      "Register-register",
      applicability: "CPU6",
      asm: "MUL <src>, <dst>",
      diagram: bitbox(
        ((bits: 8, value: "01110111"),),
        ((name: "src (even)", bits: 4), (name: "dst (even)", bits: 4)),
      ),
      decode: [
        ```cpu6
        product = R[src] * R[dst]
        ```
      ],
    ),
    encoding(
      "Immediate / direct / indexed",
      applicability: "CPU6",
      asm: "MUL= <imm>, <dst>[, <follower>]   MUL/ <addr>, …   MUL- <ireg>, <disp>, …",
      diagram: bitbox(
        ((bits: 8, value: "01110111"),),
        ((name: "src|s", bits: 4), (name: "dst|d", bits: 4)),
        ((name: "imm / addr / disp", bits: 16),),
      ),
      decode: [
        ```cpu6
        // sub-mode from the nibble low bits (s,d):
        //  s=1,d=0  immediate            multiplicand = R[src AND 14]
        //  s=0,d=1  direct MemW[addr]    multiplicand = R[src AND 14]
        //  s=1,d=1  indexed MemW[R+disp] multiplicand = dst itself
        //           (the src nibble selects the index register)
        ```
      ],
    ),
  ),
  operation: [
    ```cpu6
    product = operand * multiplicand        // 32-bit
    if dst is pair leader then
        R[leader] = product<31:16>; R[follower] = product<15:0>
    else
        R[dst] = product<15:0>
    VALUE = IsZero(product)
    FAULT = product > 0xFFFF
    MINUS = product<31> if FAULT else product<15>
    LINK  = 0                               // microcode-verified
    ```
  ],
  flags: flags-affected(fault: [product > 16 bits], minus: "*", value: "*"),
  notes: [
    In the immediate and direct sub-modes the src nibble names the
    multiplicand register explicitly — the assembler's
    `MUL= imm,<reg>,<dst>` encodes `<reg>` there (`77 12` multiplies
    A, `77 32` B, `77 52` X; all microcode-verified), with the
    destination selecting only the result pair. The indexed sub-mode
    instead multiplies the destination itself, the src nibble naming
    the index register (`MUL- A,7,B` multiplies *B* with A + 7 as the
    operand address).
  ],
)

#instruction(
  "DIV",
  qualifier: "(divide)",
  summary: [
    Unsigned 16÷16 divide. The dividend follows the same operand rule
    as MUL's multiplicand (src-nibble register for the immediate and
    direct sub-modes, the destination itself otherwise); the quotient
    goes to the pair follower and the remainder to the leader (the
    remainder is only written when the destination names the leader).
    Divide-by-zero sets F and leaves the registers unchanged — there
    is no trap. CPU6 only.
  ],
  encodings: (
    encoding(
      "Register-register",
      applicability: "CPU6",
      asm: "DIV <src>, <dst>",
      diagram: bitbox(
        ((bits: 8, value: "01111000"),),
        ((name: "src (even)", bits: 4), (name: "dst (even)", bits: 4)),
      ),
    ),
    encoding(
      "Immediate / direct / indexed",
      applicability: "CPU6",
      asm: "DIV= <imm>, <dst>[, <follower>]   DIV/ <addr>, …   DIV- <ireg>, <disp>, …",
      diagram: bitbox(
        ((bits: 8, value: "01111000"),),
        ((name: "src|s", bits: 4), (name: "dst|d", bits: 4)),
        ((name: "imm / addr / disp", bits: 16),),
      ),
    ),
  ),
  operation: [
    ```cpu6
    if divisor == 0 then FAULT = 1; return   // regs unchanged
    FAULT = 0                                // success clears F
    dividend = R[dst]                        // 16 bits, NOT a pair
    q = dividend / divisor; r = dividend mod divisor
    if dst is pair leader then
        R[leader] = r; R[follower] = q
    else
        R[dst] = q                           // remainder discarded
    VALUE = IsZero(q); MINUS = q<15>; LINK = r != 0
    ```
  ],
  flags: flags-affected(fault: [divide by zero], link: [remainder ≠ 0],
    minus: "*", value: "*"),
)
