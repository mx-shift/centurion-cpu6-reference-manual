#import "../../../lib/instruction.typ": *

// Row 0x30-0x3F: single-operand word operations, their extended
// memory forms, and the A/X one-byte aliases.

#instruction(
  "INR / DCR / CLR / IVR / SRR / SLR / RRR / RLR",
  qualifier: "(word register-constant operations)",
  summary: [
    The word counterparts of the byte register-constant row: add or
    subtract 1–16, load a constant, complement-and-add, and shift or
    rotate by 1–16 positions, on a full 16-bit register. The CPU6
    assembler also accepts `INC DEC CAD IAD/NOT SHR SHL RTR RTL`.
  ],
  encodings: (
    encoding(
      "Register-constant",
      applicability: "CPU4/5/6 (counts > 1 and memory forms: CPU6)",
      asm: "INR <reg>, <n>",
      diagram: bitbox(
        ((bits: 5, value: "00110"), (name: "op", bits: 3)),
        ((name: "reg (even)", bits: 4), (name: "n−1", bits: 4)),
      ),
      decode: [
        ```cpu6
        op: 000 INR  001 DCR  010 CLR  011 IVR
            100 SRR  101 SLR  110 RRR  111 RLR
        ```
      ],
    ),
    encoding(
      "Memory direct",
      applicability: "CPU6",
      asm: "INC/ <addr>[, <n>]",
      diagram: bitbox(
        ((bits: 5, value: "00110"), (name: "op", bits: 3)),
        ((bits: 4, value: "0001"), (name: "n−1", bits: 4)),
        ((name: "addr", bits: 16),),
      ),
      decode: [
        ```cpu6
        // odd register nibble 1: operate on MemW[addr]
        ```
      ],
    ),
    encoding(
      "Memory indexed",
      applicability: "CPU6",
      asm: "INC- <ireg>, <disp>[, <n>]",
      diagram: bitbox(
        ((bits: 5, value: "00110"), (name: "op", bits: 3)),
        ((name: "2·ireg+1", bits: 4), (name: "n−1", bits: 4)),
        ((name: "disp", bits: 16),),
      ),
      decode: [
        ```cpu6
        // odd register nibbles 3,5,7,…: operate on
        // MemW[R[ireg] + disp]; nibble 3 = B, 5 = X, 7 = Y, …
        // The A register cannot be the index (nibble 1 selects
        // the direct form). The 16-bit displacement always
        // follows, 0 when omitted.
        ```
      ],
    ),
  ),
  operation: [
    ```cpu6
    operand = R[reg]  or  MemW[ea]
    result  = Op(operand, n)
    writeback result
    // flags as for the byte row, computed at word width
    ```
  ],
  flags: flags-affected(fault: [op-dependent], link: [shifts: last bit out],
    minus: "*", value: "*"),
  notes: [
    The memory forms were verified instruction-by-instruction against
    the microcode simulator (optest suite, tests 30–37): an odd
    register nibble means a 16-bit address word always follows, used
    directly for nibble 1 and added to the selected index register
    for higher odd nibbles.

    `INA DCA CLA IVA SRA SLA` (0x38–0x3D) are one-byte A-register
    aliases, and `INX`/`DCX` (0x3E/0x3F) step X by 1
    (microcode-verified — not by the word size, despite the name).
  ],
)
