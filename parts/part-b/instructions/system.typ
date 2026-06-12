#import "../../../lib/instruction.typ": *

// The one-byte system-control column (x6 opcodes) plus SVC and the
// cross-level register-file accessors.

#instruction(
  "EAO",
  qualifier: "(enable abort on overflow)",
  summary: [
    Enable the abort-on-overflow condition. The enable lives in bit 3
    of the C register's low byte — between the flag nibble and the
    page-map select bits — and is saved and restored across interrupt
    levels with the rest of C. `DAO` disables it. CPU6 only.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU6", asm: "EAO",
      diagram: bitbox((( bits: 8, value: "01010110"),))),
  ),
  operation: [
    ```cpu6
    AOO = 1    // C.lo<3> when next saved
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
  "DAO",
  qualifier: "(disable abort on overflow)",
  summary: [
    Disable the abort-on-overflow condition: clear `AOO`, bit 3 of the
    C register's low byte (between the flag nibble and the page-map
    select bits), so overflows no longer abort. The bit is saved and
    restored across interrupt levels with the rest of C. `EAO` enables.
    CPU6 only.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU6", asm: "DAO",
      diagram: bitbox((( bits: 8, value: "01010111"),))),
  ),
  operation: [
    ```cpu6
    AOO = 0
    ```
  ],
  flags: none,
)

#instruction(
  "EPE",
  qualifier: "(enable parity error)",
  summary: [
    Arm the memory parity fault. The CPU6 memory system stores a parity
    bit per byte, and every read of main memory latches whether the
    byte's stored parity was bad. While EPE is armed, an instruction
    whose last memory read had bad parity traps to level 15 at the next
    instruction boundary, with cause 4 in `AL` and the failing address
    in Z. `DPE` disarms; `SOP`/`SEP` choose the write-parity sense.
    CPU6 only.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU6", asm: "EPE",
      diagram: bitbox((( bits: 8, value: "01110110"),))),
  ),
  operation: [
    ```cpu6
    // read path:   memfault = (stored parity wrong), latched per read
    // boundary:    if EPE armed and memfault then
    //                  TrapToLevel15(cause = 4, Z = failing VA)
    ```
  ],
  flags: none,
  exceptions: [Level-15 parity trap (cause 4) while EPE is armed.],
  notes: [
    The operating system sizes memory with this machinery: it
    `SEP`-writes a marker through a sliding page mapping, reads it
    back, and counts which banks fault — present RAM faults, open bus
    does not. Reads of ROM and I/O space never touch the latch.
  ],
)

#instruction(
  "DPE",
  qualifier: "(disable parity error)",
  summary: [
    Disarm the memory parity fault: after DPE, a memory read with bad
    stored parity no longer traps. (Reads still latch the bad-parity
    condition; it simply has no effect until re-armed.) `EPE` arms it.
    CPU6 only.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU6", asm: "DPE",
      diagram: bitbox((( bits: 8, value: "10000110"),))),
  ),
  flags: none,
)

#instruction(
  "SOP",
  qualifier: "(set odd parity)",
  summary: [
    Select odd parity for memory *writes* — the normal mode, storing
    correct parity so reads do not fault. (`SEP` stores wrong parity to
    poison bytes; `EPE` arms the fault that bad parity triggers.) CPU6
    only.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU6", asm: "SOP",
      diagram: bitbox((( bits: 8, value: "10010110"),))),
  ),
  flags: none,
)

#instruction(
  "SEP",
  qualifier: "(set even parity)",
  summary: [
    Select even parity for memory *writes* — deliberately stores wrong
    parity, "poisoning" the bytes written so a later read faults while
    `EPE` is armed. Used to size memory. CPU6 only.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU6", asm: "SEP",
      diagram: bitbox((( bits: 8, value: "10100110"),))),
  ),
  flags: none,
)

#instruction(
  "ECK",
  qualifier: "(enable clock)",
  summary: [
    Start the 60 Hz real-time clock. While running (and the
    system-control interrupt enable permits), the clock requests
    interrupt level 10 at instruction boundaries; service stamps the
    complement of the cause byte (0xFE for the clock) into the
    handler's Z. `BCK` branches while the clock runs; `DCK` stops it.
    CPU6 only.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU6", asm: "ECK",
      diagram: bitbox((( bits: 8, value: "10110110"),))),
  ),
  flags: none,
)

#instruction(
  "DCK",
  qualifier: "(disable clock)",
  summary: [
    Stop the 60 Hz real-time clock, so it no longer requests interrupt
    level 10 at instruction boundaries. `BCK` branches while the clock
    runs; `ECK` starts it. CPU6 only.
  ],
  encodings: (
    encoding("Implicit", applicability: "CPU6", asm: "DCK",
      diagram: bitbox((( bits: 8, value: "11000110"),))),
  ),
  flags: none,
)

#instruction(
  "SVC",
  qualifier: "(service call)",
  summary: [
    Operating-system service call. SVC pushes a 5-byte frame (under
    the caller's page map), saves the return address in X, clears the
    flag nibble, switches to page map 0, and enters the fixed
    supervisor entry point 0x0100. The immediate byte is the request
    number, passed in the frame — it is *not* a vector index. CPU6
    only.
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
    // level-switch hardware saves into C.lo; the pushes translate
    // through the CALLER's map
    X   = PC           // return address
    cc  = 0            // flag nibble cleared
    PTA = 0            // supervisor address space
    PC  = 0x0100
    ```
  ],
  flags: flags-affected(fault: [cleared], link: [cleared],
    minus: [cleared], value: [cleared]),
  notes: [
    RSV unwinds the frame and, through the saved cc byte's low bits,
    restores the caller's page map — the dispatcher primitive for the
    operating system's task switching. The entry-time switch to map 0
    is what lets user tasks (whose own maps need not expose page 0)
    reach the supervisor at all; it was pinned by lockstep against
    the microcode during the CENTOS boot, where the first dispatched
    task's map leaves page 0 unmapped.
  ],
)

#instruction(
  "SAR",
  qualifier: "(store A cross-level)",
  summary: [
    Store A directly into the register file across interrupt levels:
    the operand byte is the register-file *byte address*
    (level × 16 + offset). `LAR` is the load counterpart. The flags are
    untouched. CPU6 only.
  ],
  encodings: (
    encoding("Register-file direct", applicability: "CPU6",
      asm: "SAR <rfile-addr>",
      diagram: bitbox(
        ((bits: 8, value: "11010111"),),
        ((name: "rfile byte address", bits: 8),),
      )),
  ),
  operation: [
    ```cpu6
    RFile[n] = A<15:8>; RFile[n+1] = A<7:0>
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
  "LAR",
  qualifier: "(load A cross-level)",
  summary: [
    Load A directly from the register file across interrupt levels: the
    operand byte is the register-file *byte address* (level × 16 +
    offset). Supervisors use it to harvest another level's registers (a
    faulted context, say); the register file also appears at physical
    `0x0000`–`0x00FF`, so ordinary loads reach it when the active map
    exposes page 0. `SAR` is the store counterpart. The flags are
    untouched. CPU6 only.
  ],
  encodings: (
    encoding("Register-file direct", applicability: "CPU6",
      asm: "LAR <rfile-addr>",
      diagram: bitbox(
        ((bits: 8, value: "11100110"),),
        ((name: "rfile byte address", bits: 8),),
      )),
  ),
  operation: [
    ```cpu6
    A = RFile[n] : RFile[n+1]
    ```
  ],
  flags: none,
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
  "LIO",
  qualifier: "(load from I/O)",
  summary: [
    Load from the physical I/O region, bypassing the MMU: the effective
    address is `(R[k] + disp8) OR 0xF000` in physical space. The J
    nibble selects the data register and byte/word width. `SIO` is the
    store counterpart — the same opcode with `k<0>` = 1. The
    transferred value sets M and V. CPU6 only.
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
        write = k<0>          // 0 = LIO (load)
        EA    = (R[k AND 14] + SignExtend(disp)) OR IO_BASE
        ```
      ],
    ),
  ),
  flags: flags-affected(minus: "*", value: "*"),
)

#instruction(
  "SIO",
  qualifier: "(store to I/O)",
  summary: [
    Store to the physical I/O region, bypassing the MMU: the effective
    address is `(R[k] + disp8) OR 0xF000` in physical space. The J
    nibble selects the data register and byte/word width. This is the
    store direction of the I/O accessor — the same opcode as `LIO`,
    distinguished by `k<0>` = 1. The transferred value sets M and V.
    CPU6 only.
  ],
  encodings: (
    encoding(
      "Register + displacement",
      applicability: "CPU6",
      asm: "SIO <j>, <k>, <disp>",
      diagram: bitbox(
        ((bits: 8, value: "11110110"),),
        ((name: "j", bits: 4), (name: "k", bits: 4)),
        ((name: "disp (signed)", bits: 8),),
      ),
      decode: [
        ```cpu6
        byte  = j<0>          // odd j: byte register
        write = k<0>          // 1 = SIO (store)
        EA    = (R[k AND 14] + SignExtend(disp)) OR IO_BASE
        ```
      ],
    ),
  ),
  flags: flags-affected(minus: "*", value: "*"),
)
