#!/usr/bin/env python3
"""CPU6 conformance suite runner.

Loads the test kernel onto a Centurion through TOS, streams generated
test vectors to it, and compares every captured machine state against
the manual-derived model. The same runner drives real hardware over a
serial port and the emulator over TCP — run it against both and diff
the reports to find where the emulator and the hardware disagree.

  # emulator (spawns cen itself):
  ./run.py --emulator ~/Projects/centurion-emu --tiers 0,1,2

  # emulator already listening (cen diag 0a ... --telnet=6500):
  ./run.py --tcp localhost:6500 --tiers 0,1,2,3,4,5

  # real machine via a serial adapter:
  ./run.py --serial /dev/ttyUSB0:9600 --tiers 0,1,2,3,4,5

Reports land in report.jsonl (one record per vector: name, target
observations, model expectations, verdict). PASS means target ==
model; a FAIL on real hardware is a *manual* finding as much as an
emulator one — that is the point.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time

import gen
import kernel
import model
import tos


# -- transports ----------------------------------------------------------
class TcpIo:
    def __init__(self, host, port, retry=10.0):
        deadline = time.time() + retry
        while True:
            try:
                self.s = socket.create_connection((host, port), timeout=30)
                break
            except OSError:
                if time.time() > deadline:
                    raise
                time.sleep(0.3)
        self.s.setblocking(False)

    def read_available(self):
        try:
            data = self.s.recv(4096)
            # strip telnet IAC negotiation (FF xx xx)
            out = bytearray()
            i = 0
            while i < len(data):
                if data[i] == 0xFF and i + 2 < len(data) + 1:
                    i += 3 if i + 2 < len(data) else len(data)
                else:
                    out.append(data[i])
                    i += 1
            return bytes(out)
        except BlockingIOError:
            return b""

    def write(self, data):
        self.s.sendall(data)


class SerialIo:
    def __init__(self, dev, baud):
        import serial  # pyserial; only needed for hardware runs

        self.s = serial.Serial(dev, baud, timeout=0)

    def read_available(self):
        return self.s.read(4096)

    def write(self, data):
        self.s.write(data)
        self.s.flush()


# -- kernel protocol -------------------------------------------------------
class Kernel:
    def __init__(self, io, log):
        self.io = io
        self.log = log

    def _read_until(self, token, timeout=20.0):
        buf = bytearray()
        deadline = time.time() + timeout
        while time.time() < deadline:
            chunk = self.io.read_available()
            if chunk:
                buf.extend(chunk)
                if token in buf:
                    return bytes(buf)
            else:
                time.sleep(0.005)
        raise TimeoutError(f"kernel: waiting for {token!r}, got {bytes(buf)!r}")

    def wait_signon(self):
        self._read_until(b"CK1")
        self.log("kernel: signed on")

    def ping(self):
        self.io.write(b"P")
        self._read_until(b"+", timeout=5.0)

    def run_vector(self, vec):
        payload = bytearray()
        for r in ("A", "B", "X", "Y", "Z", "S"):
            payload += vec.regs[r].to_bytes(2, "big")
        payload += vec.mem_addr.to_bytes(2, "big")
        payload += len(vec.mem).to_bytes(2, "big")
        payload += len(vec.code).to_bytes(2, "big")
        payload += vec.mem
        payload += vec.code
        cksum = sum(payload) & 0xFF
        frame = b":" + payload.hex().upper().encode() + b"%02X\r" % cksum
        self.io.write(frame)
        reply = self._read_until(b"\n")
        eq = reply.rfind(b"=")
        if eq < 0:
            raise IOError(f"kernel: bad reply {reply!r}")
        body = reply[eq + 1 :].strip().decode()
        need = 2 + 24 + 2 * len(vec.mem) + 2
        if len(body) != need:
            raise IOError(f"kernel: reply length {len(body)} != {need}: {body}")
        raw = bytes.fromhex(body)
        flags = raw[0]
        regs = {
            r: int.from_bytes(raw[1 + 2 * i : 3 + 2 * i], "big")
            for i, r in enumerate(("A", "B", "X", "Y", "Z", "S"))
        }
        mem = raw[13 : 13 + len(vec.mem)]
        cks = raw[-1]
        if sum(raw[:-1]) & 0xFF != cks:
            raise IOError("kernel: reply checksum mismatch")
        return flags, regs, mem


# -- main ------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tcp", help="host:port of a listening console")
    ap.add_argument("--serial", help="device:baud of a serial console")
    ap.add_argument("--emulator", help="path to centurion-emu (spawns cen diag 0a)")
    ap.add_argument("--tiers", default="0,1", help="comma list, see gen.py")
    ap.add_argument("--report", default="report.jsonl")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    log = print if args.verbose else (lambda *a: None)
    proc = None
    if args.emulator:
        import random

        port = random.randrange(6510, 6900)
        errlog = open(os.path.join(os.path.dirname(args.report) or ".", "emulator.log"), "wb")
        proc = subprocess.Popen(
            [
                os.path.expanduser(f"{args.emulator}/target/release/cen"),
                "diag",
                "0a",
                "100000000000",
                "--quiet",
                f"--telnet={port}",
                "--pace=0",
            ],
            stdout=subprocess.DEVNULL,
            stderr=errlog,
            cwd=os.path.expanduser(args.emulator),
        )
        log(f"emulator on port {port} (pid {proc.pid})")
        time.sleep(1.0)
        io = TcpIo("localhost", port)
    elif args.tcp:
        host, port = args.tcp.rsplit(":", 1)
        io = TcpIo(host, int(port))
    elif args.serial:
        dev, baud = args.serial.rsplit(":", 1)
        io = SerialIo(dev, int(baud))
    else:
        ap.error("need --tcp, --serial, or --emulator")

    try:
        return run_suite(io, args, log)
    finally:
        if proc:
            proc.kill()


def run_suite(io, args, log):
    image, labels = kernel.build()
    capture = labels["CAPTURE"]
    gen.CAPTURE = capture

    t = tos.Tos(io, log=log)
    t.attention()
    log(f"loading kernel: {len(image)} bytes at {kernel.ORG:04X}")
    t.load(kernel.ORG, image)
    t.go(kernel.ORG)

    k = Kernel(io, log)
    k.wait_signon()
    k.ping()

    if args.tiers == "all":
        tiers = gen.ALL_TIERS
    else:
        tiers = [int(x) for x in args.tiers.split(",")]
    vectors = gen.generate(tiers, capture)
    print(f"{len(vectors)} vectors (tiers {args.tiers})")

    results = {"pass": 0, "fail": 0, "skip": 0, "err": 0}
    with open(args.report, "w") as rep:
        for vec in vectors:
            rec = {"name": vec.name, "code": vec.code.hex()}
            # model expectation
            try:
                ef, er, em = model.run_vector(
                    vec.regs, vec.mem_addr, vec.mem, vec.code, capture
                )
                rec["model"] = {"flags": ef, "regs": er, "mem": em.hex()}
            except model.Trap as e:
                rec["verdict"] = "skip"
                rec["why"] = f"model: {e}"
                results["skip"] += 1
                rep.write(json.dumps(rec) + "\n")
                continue
            # target observation
            try:
                tf, tr, tm = k.run_vector(vec)
                rec["target"] = {"flags": tf, "regs": tr, "mem": tm.hex()}
            except (TimeoutError, IOError) as e:
                rec["verdict"] = "err"
                rec["why"] = str(e)
                results["err"] += 1
                rep.write(json.dumps(rec) + "\n")
                print(f"ERR  {vec.name}: {e}")
                # try to recover the kernel
                try:
                    k.ping()
                except Exception:
                    print("kernel unresponsive; reloading via TOS")
                    t.attention()
                    t.load(kernel.ORG, image)
                    t.go(kernel.ORG)
                    k.wait_signon()
                continue
            ok = tf == ef and tm == em and all(tr[r] == er[r] for r in er)
            rec["verdict"] = "pass" if ok else "fail"
            if not ok:
                diffs = []
                if tf != ef:
                    diffs.append(f"flags {tf:02x}!={ef:02x}")
                for r in er:
                    if tr[r] != er[r]:
                        diffs.append(f"{r} {tr[r]:04x}!={er[r]:04x}")
                if tm != em:
                    diffs.append(f"mem {tm.hex()}!={em.hex()}")
                rec["diff"] = diffs
                print(f"FAIL {vec.name}: {'; '.join(diffs)}")
            elif args.verbose:
                print(f"pass {vec.name}")
            results["pass" if ok else "fail"] += 1
            rep.write(json.dumps(rec) + "\n")

    print(
        f"\n{results['pass']} pass, {results['fail']} fail, "
        f"{results['skip']} model-skip, {results['err']} comm-error "
        f"-> {args.report}"
    )
    return 1 if results["fail"] or results["err"] else 0


if __name__ == "__main__":
    sys.exit(main())
