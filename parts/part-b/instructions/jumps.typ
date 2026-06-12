#import "../../../lib/instruction.typ": *

// Rows 0x71-0x75 (JMP), 0x79-0x7D (JSR), 0x7E/0x7F (STK/POP).

#instruction(
  "JMP",
  qualifier: "(jump)",
  summary: [
    Unconditional transfer using the standard mode family: direct,
    indirect, PC-relative, relative-indirect, or indexed. The
    immediate mode does not exist for JMP (opcode 0x70 is illegal).
  ],
  encodings: (
    encoding(
      "Mode family",
      applicability: "CPU4/5/6",
      asm: "JMP/ <addr>  JMP$ <addr>  JMP <label>  JMP* <label>  JMP+ <idx>  JMP− <idx>",
      diagram: bitbox(
        ((bits: 5, value: "01110"), (name: "mode", bits: 3)),
        ((name: "operand bytes per mode", bits: 16),),
      ),
      decode: [
        ```cpu6
        mode: 001 /  direct          010 $  indirect
              011    PC-relative     100 *  relative indirect
              101 +/− indexed (mode byte follows, §A5)
        PC = EA
        ```
      ],
    ),
  ),
  flags: none,
)

#instruction(
  "JSR",
  qualifier: "(jump to subroutine)",
  summary: [
    Call: push the address of the next instruction on the stack
    (S decrements by 2) and continue at the effective address,
    computed exactly as for JMP. RSR returns.
  ],
  encodings: (
    encoding(
      "Mode family",
      applicability: "CPU4/5/6",
      asm: "JSR/ <addr>  JSR$ <addr>  JSR <label>  JSR* <label>  JSR+ <idx>  JSR− <idx>",
      diagram: bitbox(
        ((bits: 5, value: "01111"), (name: "mode", bits: 3)),
        ((name: "operand bytes per mode", bits: 16),),
      ),
    ),
  ),
  operation: [
    ```cpu6
    S = S - 2
    MemW[S] = PC      // return address
    PC = EA
    ```
  ],
  flags: none,
)

#instruction(
  "STK",
  qualifier: "(multi-register push)",
  summary: [
    Push a run of register-file bytes onto the stack. The operand names
    the first register byte and a count of bytes minus one; the run
    ending at that register is pushed descending. `POP` is the
    restoring counterpart; the pair brackets interrupt-handler bodies
    and deep call chains. CPU6 only.
  ],
  encodings: (
    encoding(
      "Register-count",
      applicability: "CPU6",
      asm: "STK <reg>, <count>",
      diagram: bitbox(
        ((bits: 8, value: "01111110"),),
        ((name: "reg", bits: 4), (name: "count−1", bits: 4)),
      ),
    ),
  ),
  operation: [
    ```cpu6
    for i = count-1 downto 0:
        S = S - 1; Mem[S] = RFile[reg + i]
    ```
  ],
  flags: none,
  notes: [
    `STK A,2` pushes `AU` and `AL` (one word). Register-file byte
    indexing is described in §A2.
  ],
)

#instruction(
  "POP",
  qualifier: "(multi-register pop)",
  summary: [
    Restore a run of register-file bytes from the stack — the inverse
    of `STK`, with the same register-count operand. CPU6 only.
  ],
  encodings: (
    encoding(
      "Register-count",
      applicability: "CPU6",
      asm: "POP <reg>, <count>",
      diagram: bitbox(
        ((bits: 8, value: "01111111"),),
        ((name: "reg", bits: 4), (name: "count−1", bits: 4)),
      ),
    ),
  ),
  operation: [
    ```cpu6
    for i = 0 to count-1:
        RFile[reg + i] = Mem[S]; S = S + 1
    ```
  ],
  flags: none,
  notes: [`POP Y,4` restores `Y` and `Z`. See `STK`.],
)
