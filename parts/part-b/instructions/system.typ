#import "../../../lib/instruction.typ": *

// The one-byte system-control column (x6 opcodes) plus SVC and the
// cross-level register-file accessors.

#instruction(
  "EAO / DAO",
  qualifier: "(abort on overflow)",
  summary: [
    Enable or disable the abort-on-overflow condition. The enable
    lives in bit 3 of the C register's low byte — between the flag
    nibble and the page-map select bits — and is saved and restored
    across interrupt levels with the rest of C. CPU6 only.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU6", asm: "EAO",
      diagram: bitbox((( bits: 8, value: "01010110"),))),
    encoding("Implicit", applicability: "CPU6", asm: "DAO",
      diagram: bitbox((( bits: 8, value: "01010111"),))),
  ),
  operation: [
    ```cpu6
    AOO = 1    // EAO (0x56);  C.lo<3> when next saved
    AOO = 0    // DAO (0x57)
    ```
  ],
  flags: none,
  notes: [
    The abort behavior itself (presumably a level-15 trap when an
    arithmetic overflow occurs while enabled) has not yet been
    characterized on reference hardware; the bit's storage and
    save/restore path are microcode-verified.
  ],
)

#instruction(
  "EPE / DPE / SOP / SEP",
  qualifier: "(memory parity controls)",
  summary: [
    The CPU6 memory system stores a parity bit per byte. SOP and SEP
    select the parity sense for *writes*: SOP (set odd parity) is the
    normal mode; SEP (set even parity) deliberately stores wrong
    parity, "poisoning" the bytes written. Every read of main memory
    latches whether the byte's stored parity was bad. EPE (enable
    parity error) arms the fault: while armed, an instruction whose
    last memory read had bad parity traps to level 15 at the next
    instruction boundary, with cause 4 in `AL` and the failing
    address in Z. DPE disarms. CPU6 only.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU6", asm: "EPE",
      diagram: bitbox((( bits: 8, value: "01110110"),))),
    encoding("Implicit", applicability: "CPU6", asm: "DPE",
      diagram: bitbox((( bits: 8, value: "10000110"),))),
    encoding("Implicit", applicability: "CPU6", asm: "SOP",
      diagram: bitbox((( bits: 8, value: "10010110"),))),
    encoding("Implicit", applicability: "CPU6", asm: "SEP",
      diagram: bitbox((( bits: 8, value: "10100110"),))),
  ),
  operation: [
    ```cpu6
    // write path:  ParityRam[pa] = Parity(value) XOR mode
    // read path:   memfault = (stored parity wrong), latched per read
    // boundary:    if EPE armed and memfault then
    //                  TrapToLevel15(cause = 4, Z = failing VA)
    ```
  ],
  flags: none,
  exceptions: [Level-15 parity trap (cause 4) while EPE is armed.],
  notes: [
    The operating system sizes memory with this machinery: it
    SEP-writes a marker through a sliding page mapping, reads it
    back, and counts which banks fault — present RAM faults, open bus
    does not. Reads of ROM and I/O space never touch the latch.
  ],
)

#instruction(
  "ECK / DCK",
  qualifier: "(clock enable)",
  summary: [
    Start or stop the 60 Hz real-time clock. While running (and the
    system-control interrupt enable permits), the clock requests
    interrupt level 10 at instruction boundaries; service stamps the
    complement of the cause byte (0xFE for the clock) into the
    handler's Z. `BCK` branches while the clock runs. CPU6 only.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU6", asm: "ECK",
      diagram: bitbox((( bits: 8, value: "10110110"),))),
    encoding("Implicit", applicability: "CPU6", asm: "DCK",
      diagram: bitbox((( bits: 8, value: "11000110"),))),
  ),
  flags: none,
)

#instruction(
  "SVC",
  qualifier: "(service call)",
  summary: [
    Operating-system service call. SVC pushes a 5-byte frame, saves
    the return address in X, clears the flag nibble, and enters the
    fixed supervisor entry point 0x0100. The immediate byte is the
    request number, passed in the frame — it is *not* a vector index.
    CPU6 only.
  ],
  encodings: (
    encoding(
      "Immediate",
      applicability: "CPU6",
      asm: "SVC <number>",
      diagram: bitbox(
        ((bits: 8, value: "01100110"),),
        ((name: "number", bits: 8),),
      ),
    ),
  ),
  operation: [
    ```cpu6
    push (descending): cc-byte, 0x05, X<7:0>, X<15:8>, number
    // cc-byte = [V M F L][AOO][PTA]: the same composition the
    // level-switch hardware saves into C.lo
    X  = PC            // return address
    cc = 0             // flag nibble cleared
    PC = 0x0100
    ```
  ],
  flags: flags-affected(fault: [cleared], link: [cleared],
    minus: [cleared], value: [cleared]),
  notes: [
    RSV unwinds the frame and, through the saved cc byte's low bits,
    restores the caller's page map — the dispatcher primitive for the
    operating system's task switching.
  ],
)

#instruction(
  "SAR / LAR",
  qualifier: "(store / load A cross-level)",
  summary: [
    Direct register-file access across interrupt levels: the operand
    byte is the register-file *byte address* (level × 16 + offset).
    SAR stores A there; LAR loads A from there. Neither touches the
    flags. CPU6 only.
  ],
  encodings: (
    encoding("Register-file direct", applicability: "CPU6",
      asm: "SAR <rfile-addr>",
      diagram: bitbox(
        ((bits: 8, value: "11010111"),),
        ((name: "rfile byte address", bits: 8),),
      )),
    encoding("Register-file direct", applicability: "CPU6",
      asm: "LAR <rfile-addr>",
      diagram: bitbox(
        ((bits: 8, value: "11100110"),),
        ((name: "rfile byte address", bits: 8),),
      )),
  ),
  operation: [
    ```cpu6
    SAR: RFile[n] = A<15:8>; RFile[n+1] = A<7:0>
    LAR: A = RFile[n] : RFile[n+1]
    ```
  ],
  flags: none,
  notes: [
    This is how supervisors plant another level's P (e.g. to direct
    where a forced trap will execute) or harvest a faulted context's
    registers. The register file also appears at physical addresses
    0x0000–0x00FF, so ordinary loads and stores reach it when the
    active map exposes page 0.
  ],
)

#instruction(
  "STR",
  qualifier: "(store register)",
  summary: [
    Store any word register: to another register, over the
    instruction's own inline literal, to a direct address, or
    indexed. The register-register form is written
    `STR <dst>, <src>` — reversed operand order relative to XFR.
    CPU6 only.
  ],
  encodings: (
    encoding(
      "Register-register",
      applicability: "CPU6",
      asm: "STR <dst>, <src>",
      diagram: bitbox(
        ((bits: 8, value: "11010110"),),
        ((name: "dst (even)", bits: 4), (name: "src (even)", bits: 4)),
      ),
    ),
    encoding(
      "Immediate (self-modifying) / direct / indexed",
      applicability: "CPU6",
      asm: "STR= 0, <src>   STR/ <addr>, <src>   STR- <ireg>, <disp>, <src>",
      diagram: bitbox(
        ((bits: 8, value: "11010110"),),
        ((name: "n1|s", bits: 4), (name: "n2|d", bits: 4)),
        ((name: "literal / addr / disp", bits: 16),),
      ),
      decode: [
        ```cpu6
        // (s,d) low bits select the form:
        //  s=1,d=0  store low nibble's register over the inline word
        //  s=0,d=1  store high nibble's register to MemW[addr]
        //  s=1,d=1  store low nibble's register to
        //           MemW[R[high nibble] + disp]
        ```
      ],
    ),
  ),
  flags: flags-affected(minus: "*", value: "*"),
)

#instruction(
  "MVL",
  qualifier: "(move long)",
  summary: [
    Block copy: move A + 1 bytes from the address in B to the address
    in Y. A, B, and Y are architecturally unchanged; P is left
    pointing at the next instruction. Flags untouched. CPU6 only
    (the opcode is one of the CPU5's illegal codes).
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU6", asm: "MVL",
      diagram: bitbox((( bits: 8, value: "11110111"),))),
  ),
  operation: [
    ```cpu6
    for i = 0 to A:
        Mem[Y + i] = Mem[B + i]
    P = PC
    ```
  ],
  flags: none,
)

#instruction(
  "LIO / SIO",
  qualifier: "(direct I/O access)",
  summary: [
    Load from or store to the physical I/O region, bypassing the MMU:
    the effective address is `(R[k] + disp8) OR 0xF000` in physical
    space. The J nibble selects the data register and byte/word
    width; the K nibble's low bit selects the direction. Both
    directions set M and V from the transferred value. CPU6 only.
  ],
  encodings: (
    encoding(
      "Register + displacement",
      applicability: "CPU6",
      asm: "LIO <j>, <k>, <disp>",
      diagram: bitbox(
        ((bits: 8, value: "11110110"),),
        ((name: "j", bits: 4), (name: "k", bits: 4)),
        ((name: "disp (signed)", bits: 8),),
      ),
      decode: [
        ```cpu6
        byte  = j<0>          // odd j: byte register
        write = k<0>          // SIO when set
        EA    = (R[k AND 14] + SignExtend(disp)) OR IO_BASE
        ```
      ],
    ),
  ),
  flags: flags-affected(minus: "*", value: "*"),
)
