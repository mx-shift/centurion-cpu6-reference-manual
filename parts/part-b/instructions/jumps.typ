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
      asm: "JMP/ <addr>  JMP$ <addr>  JMP <label>  JMP* <label>  JMP± <idx>",
      diagram: bitbox(
        ((bits: 5, value: "01110"), (name: "mode", bits: 3)),
        ((name: "operand bytes per mode", bits: 16),),
      ),
      decode: [
        ```cpu6
        mode: 001 /  direct          010 $  indirect
              011    PC-relative     100 *  relative indirect
              101 ±  indexed (mode byte follows, §A5)
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
      asm: "JSR/ <addr>  JSR$ <addr>  JSR <label>  JSR* <label>  JSR± <idx>",
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
  "STK / POP",
  qualifier: "(multi-register push / pop)",
  summary: [
    Push or pop a run of register-file bytes. The operand names the
    first register byte and a count of bytes minus one; STK pushes the
    run ending at that register descending, POP restores it. The pair
    brackets interrupt-handler bodies and deep call chains. CPU6
    only.
  ],
  encodings: (
    encoding(
      "Register-count",
      applicability: "CPU6",
      asm: "STK <reg>, <count>",
      diagram: bitbox(
        ((bits: 8, value: "0111111d"),),
        ((name: "reg", bits: 4), (name: "count−1", bits: 4)),
      ),
      decode: [
        ```cpu6
        d = opcode<0>   // 0 = STK (0x7E), 1 = POP (0x7F)
        ```
      ],
    ),
  ),
  operation: [
    ```cpu6
    STK: for i = count-1 downto 0:
             S = S - 1; Mem[S] = RFile[reg + i]
    POP: for i = 0 to count-1:
             RFile[reg + i] = Mem[S]; S = S + 1
    ```
  ],
  flags: none,
  notes: [
    `STK A,2` pushes `AU` and `AL` (one word); `POP Y,4` restores
    Y and Z. Register-file byte indexing is described in §A2.
  ],
)
