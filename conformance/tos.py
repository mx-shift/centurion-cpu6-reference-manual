"""TOS (DIAG test 0x0A) console driver: loading code on a Centurion.

TOS is the monitor in the DIAG board ROMs, selected with DIP setting
0x0A. It signs on with a ROM checksum and prompts with a backslash.
Empirically mapped command set (verified against the DIAG ROM running
in emulation):

  M<addr16>      modify memory: type two hex digits to store a byte,
                 space commits and advances (TOS echoes the *next*
                 location's current value), any non-hex character
                 returns to the prompt.
  G<addr16>      jump to address.
  Q              restart TOS (fresh sign-on).

The same dialogue works over a real serial connection at the DIAG
board's console rate.
"""

import time

PROMPT = b"\\"


class Tos:
    def __init__(self, io, log=None):
        self.io = io  # transport with read_available()/write()/drain()
        self.log = log or (lambda s: None)

    def _read_until(self, token, timeout=10.0):
        buf = bytearray()
        deadline = time.time() + timeout
        while time.time() < deadline:
            chunk = self.io.read_available()
            if chunk:
                buf.extend(chunk)
                if token in buf:
                    return bytes(buf)
            else:
                time.sleep(0.01)
        raise TimeoutError(f"TOS: waiting for {token!r}, got {bytes(buf)!r}")

    def attention(self):
        """Get to a fresh prompt from an unknown state: a junk byte
        aborts any half-entered command, then CR elicits a prompt."""
        self.io.write(b".")
        time.sleep(0.1)
        self.io.read_available()
        self.io.write(b"\r")
        self._read_until(PROMPT)
        self.log("TOS: prompt")

    def load(self, addr, data, chunk=64):
        """Deposit `data` at `addr` with the M command."""
        n = 0
        while n < len(data):
            run = data[n : n + chunk]
            self.io.write(b"M%04X " % (addr + n))
            for b in run:
                self.io.write(b"%02X " % b)
            self.io.write(b".")  # abort M -> prompt
            self._read_until(PROMPT, timeout=30.0)
            n += len(run)
            self.log(f"TOS: loaded {n}/{len(data)}")

    def verify(self, addr, data):
        """Read back one byte per M view to spot-check the load: enter
        M at the address, commit the same byte, and confirm TOS echoes
        the following location's current value."""
        # Cheap spot check: rewrite the first byte and compare the
        # echoed next-location value against what we loaded there.
        if len(data) < 2:
            return True
        self.io.write(b"M%04X" % addr)
        self.io.write(b"%02X " % data[0])
        out = self._read_until(b" ")
        self.io.write(b".")
        self._read_until(PROMPT)
        want = b"%02X" % data[1]
        return want in out

    def go(self, addr):
        # G takes four hex digits; a trailing space triggers the jump
        # (same terminator discipline as the M dialog).
        self.io.write(b"G%04X " % addr)
        self.log(f"TOS: G{addr:04X}")
