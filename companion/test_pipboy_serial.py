#!/usr/bin/env python3
"""Offline test of pipboy_serial against a fake Espruino console.

Emulates the device console at the level of the specific commands the module
sends, in BOTH echo-on and echo-off modes, so we can prove the read/parse
protocol survives console echo. Also checks verify-mismatch, device-error, and
no-response failure paths. No hardware and no pyserial required.
"""
import base64
import re
import sys
import types
import time

# ---- install a fake `serial` package so pipboy_serial._pyserial() succeeds ---
fake_serial = types.ModuleType("serial")
fake_listports = types.ModuleType("serial.tools.list_ports")
tools = types.ModuleType("serial.tools")


class FakeEspruino:
    """A minimal stand-in for the Pip-Boy's Espruino USB console."""

    def __init__(self, port="COM_TEST", baud=9600, timeout=0, write_timeout=0,
                 echo=True, board="PIPBOY", broken=None):
        self.echo = echo
        self.board = board
        self.broken = broken or set()   # command kinds that should throw
        self.fs = {}                    # fake FAT filesystem: path -> bytes
        self._out = bytearray()         # bytes waiting to be read by the host
        self._in = bytearray()          # bytes written by the host, unparsed
        self.wrong_len = False          # force a verify mismatch

    # pyserial-ish surface -------------------------------------------------
    @property
    def in_waiting(self):
        return len(self._out)

    def read(self, n=1):
        n = min(n, len(self._out))
        chunk = bytes(self._out[:n])
        del self._out[:n]
        return chunk

    def write(self, data):
        self._in += data
        while b"\n" in self._in:
            line, _, rest = self._in.partition(b"\n")
            self._in = bytearray(rest)
            self._exec(line.decode("utf-8", "replace"))
        return len(data)

    def close(self):
        pass

    # console emulation ----------------------------------------------------
    def _emit(self, s):
        self._out += s.encode("utf-8")

    def _exec(self, line):
        line = line.lstrip("\x03").strip()      # Ctrl-C just clears the line
        if not line:
            return
        if line in ("echo(0)", "echo(1)"):
            if self.echo:                       # echoed before the setting applies
                self._emit(line + "\r\n")
            self.echo = (line == "echo(1)")
            self._emit("=undefined\r\n>")
            return

        if self.echo:                           # device echoes typed input
            self._emit(line + "\r\n")

        executed = self._evaluate(line)         # what print() would emit
        if executed:
            self._emit(executed + "\r\n")
        self._emit("=undefined\r\n>")           # result + prompt

    def _evaluate(self, line):
        # process.env.BOARD probe
        if "process.env.BOARD" in line:
            if "board" in self.broken:
                return MARK + "ERR ReferenceError"
            return MARK + "B=" + self.board

        # writeFileSync(path,"") -> truncate/create
        m = re.search(r'writeFileSync\("([^"]+)",""\)', line)
        if m:
            if "write" in self.broken:
                return MARK + 'ERR Error: Unable to open file'
            self.fs[m.group(1)] = b""
            return MARK + "OK"

        # appendFileSync(path, atob("b64"))
        m = re.search(r'appendFileSync\("([^"]+)",atob\("([^"]*)"\)\)', line)
        if m:
            if "append" in self.broken:
                return MARK + 'ERR Error: disk full'
            self.fs[m.group(1)] = self.fs.get(m.group(1), b"") + base64.b64decode(m.group(2))
            return MARK + "OK"

        # readFileSync(path).length -> verify
        m = re.search(r'readFileSync\("([^"]+)"\)\.length', line)
        if m:
            n = len(self.fs.get(m.group(1), b""))
            if self.wrong_len:
                n += 7
            return MARK + "L=" + str(n)

        # mkdir(...) -> no print; device just returns undefined
        if "mkdir(" in line:
            return ""
        return MARK + "OK"


# knobs the tests tweak before each construction
_ECHO = [True]
_BOARD = ["PIPBOY"]
_BROKEN = [set()]
_WRONGLEN = [False]
_LAST = [None]


def _Serial(port, baud=9600, timeout=0, write_timeout=0):
    dev = FakeEspruino(port, baud, echo=_ECHO[0], board=_BOARD[0],
                       broken=set(_BROKEN[0]))
    dev.wrong_len = _WRONGLEN[0]
    _LAST[0] = dev
    return dev


class _PortInfo:
    def __init__(self, device, description="USB Serial Device", manufacturer="",
                 vid=0x0483, pid=0x5740, product="", name=""):
        self.device = device
        self.description = description
        self.manufacturer = manufacturer
        self.vid = vid
        self.pid = pid
        self.product = product
        self.name = name


def _comports():
    return [_PortInfo("COM3", "USB Serial Device"),
            _PortInfo("COM_TEST", "Pip-Boy (Espruino)", "Espruino")]


fake_serial.Serial = _Serial
fake_listports.comports = _comports
tools.list_ports = fake_listports
fake_serial.tools = tools
sys.modules["serial"] = fake_serial
sys.modules["serial.tools"] = tools
sys.modules["serial.tools.list_ports"] = fake_listports

import pipboy_serial as pbs
from pipboy_serial import MARK  # noqa: E402  (import after fake install)
# make the mock's marker match the module's
FakeEspruino.__init__.__defaults__  # touch, no-op

# inject MARK into the test module namespace for FakeEspruino
globals()["MARK"] = pbs.MARK


def _make_payload(nbytes):
    # realistic-ish JSON bytes, includes quotes/backslashes/unicode to stress atob
    s = '{"v":1,"note":"quote \\" backslash \\\\ unicode \u2600","pad":"'
    s += "A" * max(0, nbytes - len(s) - 2)
    s += '"}'
    return s.encode("utf-8")


def run_transfer(echo, board="PIPBOY", size=3000, wrong_len=False):
    _ECHO[0] = echo
    _BOARD[0] = board
    _BROKEN[0] = set()
    _WRONGLEN[0] = wrong_len
    data = _make_payload(size)
    # write a temp local file and push it
    import tempfile
    import os
    p = tempfile.mktemp(suffix=".json")
    with open(p, "wb") as f:
        f.write(data)
    res = pbs.transfer_files([(p, "USER/WEATHER.JSON")], port="COM_TEST")
    os.remove(p)
    got = _LAST[0].fs.get("USER/WEATHER.JSON")
    assert got == data, "echo=%s: file mismatch (%d vs %d bytes)" % (
        echo, len(got or b""), len(data))
    assert res["files"][0]["verified"] is True, "echo=%s: not verified" % echo
    assert res["board"] == board
    return res


def main():
    print("1) transfer with console ECHO ON ...")
    r = run_transfer(echo=True, size=3200)
    print("   ok - wrote %d bytes, verified, board=%s"
          % (r["files"][0]["bytes"], r["board"]))

    print("2) transfer with console ECHO OFF ...")
    r = run_transfer(echo=False, size=1500)
    print("   ok - wrote %d bytes, verified" % r["files"][0]["bytes"])

    print("3) binary-safe payload (all 256 byte values) ...")
    _ECHO[0] = True
    _BOARD[0] = "PIPBOY"
    _BROKEN[0] = set()
    _WRONGLEN[0] = False
    import tempfile
    import os
    raw = bytes(range(256)) * 3
    p = tempfile.mktemp()
    with open(p, "wb") as f:
        f.write(raw)
    pbs.transfer_files([(p, "APPINFO/WEATHER.IMG")], port="COM_TEST")
    os.remove(p)
    assert _LAST[0].fs["APPINFO/WEATHER.IMG"] == raw, "binary mismatch"
    print("   ok - 768 binary bytes round-tripped exactly")

    print("4) auto-detect picks the PIPBOY port by probing ...")
    _ECHO[0] = True
    dev = pbs.find_pipboy()          # no port -> scan + probe
    assert dev == "COM_TEST", dev
    print("   ok - find_pipboy() -> %s" % dev)

    print("5) verify mismatch is caught ...")
    try:
        run_transfer(echo=True, size=800, wrong_len=True)
        print("   FAIL - mismatch not detected"); return 1
    except pbs.TransferError as e:
        print("   ok - raised TransferError: %s" % e)
    _WRONGLEN[0] = False

    print("6) device error during append is surfaced ...")
    _ECHO[0] = True
    _BROKEN[0] = {"append"}
    import tempfile as tf
    q = tf.mktemp()
    open(q, "wb").write(_make_payload(500))
    try:
        pbs.transfer_files([(q, "USER/WEATHER.JSON")], port="COM_TEST")
        print("   FAIL - error not surfaced"); return 1
    except pbs.TransferError as e:
        print("   ok - raised TransferError: %s" % e)
    finally:
        os.remove(q)
    _BROKEN[0] = set()

    print("7) non-Espruino / silent port raises PipBoyNotFound ...")
    _BROKEN[0] = {"board"}
    try:
        with pbs.PipBoyLink("COM_TEST") as link:
            link.identify()
        print("   FAIL - should not identify"); return 1
    except pbs.PipBoyNotFound as e:
        print("   ok - raised PipBoyNotFound")
    _BROKEN[0] = set()

    print("8) list_candidates() ranks the hinted port first ...")
    cands = pbs.list_candidates()
    assert cands[0]["device"] == "COM_TEST", cands
    print("   ok - top candidate: %s (score=%d)"
          % (cands[0]["device"], cands[0]["score"]))

    print("\nALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
