#!/usr/bin/env python3
# ============================================================================
#  PIP-BOY 3000 USB TRANSFER  (companion helper)
#
#  Pushes files straight to a USB-connected Pip-Boy 3000 - no need to pop the
#  microSD card out. The weather app reads the freshly-written cache the next
#  time you open it.
#
#  HOW IT WORKS / WHY SERIAL (not a USB drive)
#  -------------------------------------------
#  The Pip-Boy 3000 does NOT present its SD card as a USB mass-storage drive
#  when you plug it in. Like the Mk V, it runs Espruino on an STM32 and exposes
#  a JavaScript console over a USB-C serial (CDC) link - the same link The Wand
#  Company's web updater and the Espruino Web IDE use. Files on the card live on
#  a FAT32 filesystem reachable from that console through Espruino's `fs` module.
#
#  So instead of copying a file onto a mounted drive, we open the serial port
#  and ask the device to write the file itself:
#      require("fs").writeFileSync("USER/WEATHER.JSON", <chunk>)   // truncate
#      require("fs").appendFileSync("USER/WEATHER.JSON", <chunk>)  // ...repeat
#  which is the very path (USER/WEATHER.JSON) the on-device app reads.
#
#  SAFETY
#  ------
#  * We only ever write files under the card's normal app/data folders via the
#    `fs` module. We NEVER touch the Espruino firmware/flash and NEVER call the
#    global save() - so this can't brick the device the way the IDE's "flash"
#    button can.
#  * Every device call is wrapped in try/catch on-device, so a missing
#    capability surfaces as a clear error instead of a hang.
#
#  REQUIREMENTS
#  ------------
#  pyserial  ->  pip install pyserial
#  (imported lazily; the rest of the companion stays dependency-free.)
#
#  STANDALONE USAGE
#  ----------------
#    List likely ports:   python pipboy_serial.py --list-ports
#    Push a file:         python pipboy_serial.py WEATHER.JSON:USER/WEATHER.JSON
#    Force a port:        python pipboy_serial.py --port COM5 WEATHER.JSON:USER/WEATHER.JSON
#
#  Normally you won't run this directly - pipboy_weather.py (--usb) and the GUI
#  ("TRANSFER OVER USB") import it.
# ============================================================================

import base64
import re
import sys
import time

DEFAULT_BAUD = 9600         # USB-CDC ignores baud, but pyserial needs a value
CMD_TIMEOUT = 4.0           # seconds to wait for a device reply per command
PROBE_TIMEOUT = 1.5         # shorter wait while scanning ports for the device
IDLE_GAP = 0.08             # a reply is "done" after this long with no new bytes
B64_CHUNK = 120             # base64 chars per append line (keeps each line < 256)
MARK = "__PBW__"            # printable marker; control bytes may be stripped

# Soft hints only - detection ALWAYS confirms by probing the console.
HINT_VIDS = {0x0483, 0x1209}          # STMicroelectronics, Espruino/community
HINT_WORDS = ("espruino", "pip-boy", "pipboy", "pip boy",
              "stmicro", "stm32", "usb serial", "cdc")

_ERR_RE = re.compile(r"Uncaught|ERROR:|Error:|not defined|not a function")


class SerialUnavailable(RuntimeError):
    """pyserial isn't installed."""


class PipBoyNotFound(RuntimeError):
    """No Pip-Boy / Espruino console found on any serial port."""


class TransferError(RuntimeError):
    """The device reported an error (or didn't respond) during transfer."""


def _pyserial():
    try:
        import serial
        import serial.tools.list_ports as list_ports
        return serial, list_ports
    except ImportError:
        raise SerialUnavailable(
            "pyserial is required for USB transfer. Install it with:\n"
            "    pip install pyserial")


# --------------------------------------------------------------- port scan ---
def _score_port(p):
    text = " ".join(str(x or "") for x in
                    (p.description, p.manufacturer, getattr(p, "product", ""),
                     p.name, p.device)).lower()
    score = sum(2 for w in HINT_WORDS if w in text)
    if getattr(p, "vid", None) in HINT_VIDS:
        score += 1
    return score


def list_candidates():
    """Return serial ports, best-guess-first, as a list of dicts."""
    _, list_ports = _pyserial()
    out = []
    for p in list_ports.comports():
        out.append({
            "device": p.device,
            "description": p.description or "",
            "manufacturer": p.manufacturer or "",
            "vid": getattr(p, "vid", None),
            "pid": getattr(p, "pid", None),
            "score": _score_port(p),
        })
    out.sort(key=lambda d: d["score"], reverse=True)
    return out


# --------------------------------------------------------------- utilities ---
def _q(s):
    """Quote a string for embedding inside a one-line JS command."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


# ------------------------------------------------------------ device link ----
class PipBoyLink:
    """A serial connection to the Espruino console on a Pip-Boy.

    Use as a context manager:
        with PipBoyLink(port) as link:
            link.identify()
            link.write_file("USER/WEATHER.JSON", data_bytes)

    Console echo is handled robustly: every command is wrapped so it prints a
    single MARK-tagged status line, and we always parse the LAST marker in the
    reply (the executed output arrives after any echoed copy of the command),
    so the code works whether or not the console echoes input.
    """

    def __init__(self, port, baud=DEFAULT_BAUD, timeout=CMD_TIMEOUT):
        serial, _ = _pyserial()
        self.port = port
        self.timeout = timeout
        try:
            self.ser = serial.Serial(port, baud, timeout=0, write_timeout=timeout)
        except Exception as e:
            raise TransferError("could not open %s: %s" % (port, e))
        time.sleep(0.25)
        self._prime()

    # -- lifecycle ----------------------------------------------------------
    def _prime(self):
        # Abort any half-typed line, quiet the echo (best effort), clear buffers.
        try:
            self.ser.write(b"\x03")            # Ctrl-C: clear the input line
            time.sleep(0.15)
            self.ser.write(b"echo(0)\n")       # best effort; parsing works either way
            time.sleep(0.20)
            self._drain()
        except Exception:
            pass

    def _drain(self, t=0.15):
        end = time.time() + t
        while time.time() < end:
            n = self.ser.in_waiting
            if n:
                self.ser.read(n)
                end = time.time() + t
            else:
                time.sleep(0.01)

    def close(self):
        try:
            self.ser.write(b"echo(1)\n")       # restore the normal console
            time.sleep(0.05)
        except Exception:
            pass
        try:
            self.ser.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    # -- raw conversation ---------------------------------------------------
    def _converse(self, js, timeout=None):
        """Send one line of JS; return everything the device prints back.

        Idle-based: stops a short moment after the device goes quiet, or at
        `timeout` if it never answers.
        """
        timeout = timeout or self.timeout
        try:
            self.ser.write((js + "\n").encode("utf-8"))
        except Exception as e:
            raise TransferError("write failed on %s: %s" % (self.port, e))
        buf = bytearray()
        last = time.time()
        deadline = time.time() + timeout
        while time.time() < deadline:
            n = self.ser.in_waiting
            if n:
                buf += self.ser.read(n)
                last = time.time()
            elif buf and (time.time() - last) > IDLE_GAP:
                break
            else:
                time.sleep(0.004)
        return buf.decode("utf-8", "replace")

    def _status(self, js, timeout=None):
        """Run JS (which must print '<MARK>...') wrapped in try/catch.

        Returns the text after the LAST marker: the payload we printed on
        success, or 'ERR <message>' if the device threw.
        """
        wrapped = 'try{%s}catch(e){print("%sERR "+e)}' % (js, MARK)
        resp = self._converse(wrapped, timeout=timeout)
        if MARK not in resp:
            raise TransferError("no response from device (timed out).")
        tail = resp.rsplit(MARK, 1)[-1]
        return tail.splitlines()[0].strip() if tail.strip() else ""

    def _run(self, js, timeout=None):
        """Run a statement that returns nothing useful; raise on device error."""
        st = self._status('%s;print("%sOK")' % (js, MARK), timeout=timeout)
        if st.startswith("ERR"):
            raise TransferError(st[3:].strip() or "device error")
        if not st.startswith("OK"):
            raise TransferError("unexpected device reply: %r" % st)

    # -- high level ---------------------------------------------------------
    def identify(self, timeout=PROBE_TIMEOUT):
        """Return the device's Espruino BOARD name, or raise PipBoyNotFound."""
        st = self._status('print("%sB="+process.env.BOARD)' % MARK, timeout=timeout)
        board = ""
        if st.startswith("B="):
            board = re.sub(r"[^A-Za-z0-9_]", "", st[2:])
        if not board:
            raise PipBoyNotFound(
                "%s did not answer like an Espruino device (is the Pip-Boy "
                "plugged in with a DATA cable, and not open in another program "
                "like the Espruino IDE or the web updater?)" % self.port)
        return board

    def write_file(self, sd_rel, data, verify=True, progress=None):
        """Write `data` (bytes/str) to `sd_rel` on the card via the fs module.

        The payload is sent base64-encoded and rebuilt on-device with atob(),
        so binary files (e.g. the .IMG icon) and every JSON byte survive intact.
        Returns {'path','bytes','verified'}.
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        path = sd_rel.replace("\\", "/")
        total = len(data)

        # Make sure the target folder exists (harmless if it already does or if
        # the firmware's fs has no mkdir - the try/catch swallows both).
        if "/" in path:
            folder = path.rsplit("/", 1)[0]
            self._converse('try{require("fs").mkdir("%s")}catch(e){}' % folder)

        # Truncate / create, then stream the base64 chunks in.
        self._run('require("fs").writeFileSync(%s,"")' % _q(path))
        b64 = base64.b64encode(data).decode("ascii")
        done = 0
        for i in range(0, len(b64), B64_CHUNK):
            chunk = b64[i:i + B64_CHUNK]
            self._run('require("fs").appendFileSync(%s,atob("%s"))' % (_q(path), chunk))
            done = min(total, done + (len(chunk) * 3) // 4)
            if progress:
                progress(sd_rel, done, total)
        if progress:
            progress(sd_rel, total, total)

        if not verify:
            return {"path": sd_rel, "bytes": total, "verified": None}

        st = self._status(
            'print("%sL="+require("fs").readFileSync(%s).length)' % (MARK, _q(path)))
        m = re.match(r"L=(\d+)", st)
        if not m:
            return {"path": sd_rel, "bytes": total, "verified": False}
        got = int(m.group(1))
        if got != total:
            raise TransferError(
                "verify failed for %s: sent %d bytes, device has %d"
                % (sd_rel, total, got))
        return {"path": sd_rel, "bytes": total, "verified": True}

    def file_size(self, sd_rel):
        """Return the size of `sd_rel` on the card, or None if it is missing."""
        path = sd_rel.replace("\\", "/")
        st = self._status(
            'print("%sL="+require("fs").readFileSync(%s).length)' % (MARK, _q(path)))
        if st.startswith("ERR"):
            return None
        m = re.match(r"L=(\d+)", st)
        return int(m.group(1)) if m else None

    def file_exists(self, sd_rel, min_bytes=1):
        """Return True when `sd_rel` exists and is at least `min_bytes` long."""
        n = self.file_size(sd_rel)
        return n is not None and n >= min_bytes


# --------------------------------------------------------------- detection ---
def find_pipboy(port=None, prefer="PIP"):
    """Return the serial device path of a Pip-Boy, probing to confirm.

    If `port` is given it is verified. Otherwise every serial port is probed
    best-guess-first and the first Espruino-looking device is returned
    (preferring one whose BOARD name contains `prefer`, e.g. "PIPBOY").
    """
    if port:
        with PipBoyLink(port) as link:
            link.identify()
        return port

    cands = list_candidates()
    if not cands:
        raise PipBoyNotFound("no serial ports found - plug the Pip-Boy in with a "
                             "data-capable USB-C cable.")
    fallback = None
    tried = []
    for c in cands:
        dev = c["device"]
        tried.append(dev)
        try:
            with PipBoyLink(dev) as link:
                board = link.identify()
        except (PipBoyNotFound, TransferError):
            continue
        if prefer and prefer in board.upper():
            return dev
        fallback = fallback or dev
    if fallback:
        return fallback
    raise PipBoyNotFound(
        "no Pip-Boy found. Ports checked: %s. Make sure the cable carries data "
        "(not charge-only) and that the device isn't open in the Espruino IDE "
        "or the web updater." % ", ".join(tried))


# ------------------------------------------------------------- high level ----
def transfer_files(pairs, port=None, progress=None):
    """Push files to a USB-connected Pip-Boy.

    `pairs` is a list of (local_path, sd_rel_path). Returns
    {'port','board','files':[...]} and raises SerialUnavailable /
    PipBoyNotFound / TransferError on failure.
    """
    _pyserial()                       # fail early with a clear message
    resolved = find_pipboy(port)
    results = []
    with PipBoyLink(resolved) as link:
        board = link.identify()
        for local, sd_rel in pairs:
            with open(local, "rb") as f:
                data = f.read()
            results.append(link.write_file(sd_rel, data, progress=progress))
    return {"port": resolved, "board": board, "files": results}


def scan_files(paths, port=None):
    """Check whether SD-relative files exist on a USB-connected Pip-Boy.

    Returns {'port','board','files':[{'path','exists','bytes'}], 'missing':[...]}.
    A zero-byte file is treated as missing because app/data files should never
    be empty in a working install.
    """
    _pyserial()                       # fail early with a clear message
    resolved = find_pipboy(port)
    files = []
    with PipBoyLink(resolved) as link:
        board = link.identify()
        for sd_rel in paths:
            path = sd_rel.replace("\\", "/")
            size = link.file_size(path)
            exists = size is not None and size > 0
            files.append({"path": path, "exists": exists, "bytes": size or 0})
    missing = [f["path"] for f in files if not f["exists"]]
    return {"port": resolved, "board": board, "files": files, "missing": missing}


# ---------------------------------------------------------------- CLI test ---
def _cli(argv):
    port = None
    do_list = False
    pairs = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--port" and i + 1 < len(argv):
            i += 1
            port = argv[i]
        elif a in ("--list-ports", "-l"):
            do_list = True
        elif ":" in a:
            local, sd_rel = a.split(":", 1)
            pairs.append((local, sd_rel))
        else:
            print("skipping unrecognised arg: %s" % a)
        i += 1

    if do_list or not pairs:
        try:
            cands = list_candidates()
        except SerialUnavailable as e:
            print(e)
            return 2
        print("Serial ports (best guess first):")
        for c in cands or []:
            vid = ("[%04X:%04X]" % (c["vid"], c["pid"])) if c["vid"] else ""
            print("  %-16s score=%d  %s %s"
                  % (c["device"], c["score"], c["description"], vid))
        if not cands:
            print("  (none)")
        if not pairs:
            return 0

    def prog(name, done, total):
        pct = 100 * done // total if total else 100
        sys.stdout.write("\r  %-22s %3d%%" % (name, pct))
        sys.stdout.flush()
        if done >= total:
            sys.stdout.write("\n")

    try:
        res = transfer_files(pairs, port=port, progress=prog)
    except (SerialUnavailable, PipBoyNotFound, TransferError) as e:
        print("\nUSB transfer failed: %s" % e)
        return 1
    print("  device: %s on %s" % (res["board"], res["port"]))
    for r in res["files"]:
        note = "verified" if r["verified"] else (
            "written (unverified)" if r["verified"] is False else "written")
        print("  wrote %-22s %6d bytes  %s" % (r["path"], r["bytes"], note))
    print("Open the Weather app on the Pip-Boy to load the new data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
