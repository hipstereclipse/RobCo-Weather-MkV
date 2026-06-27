#!/usr/bin/env python3
# ============================================================================
#  PIP-BOY 3000 WEATHER COMPANION - graphical interface
#  A modern, Pip-Boy-themed desktop UI over the same engine as the CLI.
#  Pure standard library (Tkinter) - no packages to install.
#
#  Run:  python pipboy_weather_gui.py
#  (The CLI still works: python pipboy_weather.py)
# ============================================================================

import os
import sys
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog

import pipboy_weather as core

# --- Pip-Boy palette --------------------------------------------------------
BG     = "#06120a"   # screen black-green
PANEL  = "#0b2014"   # panel fill
EDGE   = "#1d5c33"   # borders
GREEN  = "#46ff78"   # primary phosphor green
DIM    = "#2f9d54"   # dimmed green
AMBER  = "#ffb642"   # accent / warnings
SEL    = "#103b22"   # selection fill

FT   = ("Consolas", 11)
FTB  = ("Consolas", 11, "bold")
FTSM = ("Consolas", 9)
FTBIG = ("Consolas", 22, "bold")

FETCH_LABEL = ">  FETCH & SYNC DATA"
INSTALL_LABEL = "INSTALL APP FILES"


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = core.load_config()
        self.search_results = []
        self.q = queue.Queue()
        self.fetching = False
        self.installing = False

        root.title("PIP-OS // WEATHER COMPANION")
        root.configure(bg=BG)
        root.geometry("860x620")
        root.minsize(760, 560)

        self._build()
        self.refresh_locations()
        self.update_output_label()
        self.log("PIP-OS WEATHER COMPANION ONLINE.")
        self.log("Data: Open-Meteo (weather) + NOAA SWPC (space weather).")
        self.root.after(80, self._poll)

    # ---------------------------------------------------------------- styling
    def _btn(self, parent, text, cmd, accent=False):
        c = AMBER if accent else GREEN
        b = tk.Button(parent, text=text, command=cmd, font=FTB,
                      bg=PANEL, fg=c, activebackground=SEL, activeforeground=c,
                      bd=1, relief="solid", highlightbackground=EDGE,
                      cursor="hand2", padx=10, pady=4)
        return b

    def _frame(self, parent, title):
        outer = tk.LabelFrame(parent, text=" " + title + " ", font=FTSM,
                              bg=BG, fg=DIM, bd=1, relief="solid",
                              labelanchor="nw", padx=8, pady=8,
                              highlightbackground=EDGE)
        return outer

    def _build(self):
        # header ------------------------------------------------------------
        head = tk.Frame(self.root, bg=BG)
        head.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(head, text="▒ WEATHER COMPANION", font=FTBIG,
                 bg=BG, fg=GREEN).pack(side="left")
        tk.Label(head, text="ROBCO INDUSTRIES (TM)  TERMINLINK",
                 font=FTSM, bg=BG, fg=DIM).pack(side="right", pady=(10, 0))
        tk.Frame(self.root, bg=EDGE, height=2).pack(fill="x", padx=14)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=14, pady=10)
        body.columnconfigure(0, weight=1, uniform="col")
        body.columnconfigure(1, weight=1, uniform="col")
        body.rowconfigure(0, weight=1)

        # left: saved locations --------------------------------------------
        left = self._frame(body, "SAVED LOCATIONS")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.loc_list = tk.Listbox(left, font=FT, bg=BG, fg=GREEN,
                                   selectbackground=SEL, selectforeground=AMBER,
                                   bd=0, highlightthickness=0, activestyle="none")
        self.loc_list.pack(fill="both", expand=True)
        lb = tk.Frame(left, bg=BG)
        lb.pack(fill="x", pady=(8, 0))
        self._btn(lb, "▲", lambda: self.move(-1)).pack(side="left")
        self._btn(lb, "▼", lambda: self.move(1)).pack(side="left", padx=4)
        self._btn(lb, "REMOVE", self.remove_location, accent=True).pack(side="right")

        # right: add location ----------------------------------------------
        right = self._frame(body, "ADD LOCATION  (search anywhere on Earth)")
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        sr = tk.Frame(right, bg=BG)
        sr.pack(fill="x")
        self.search_var = tk.StringVar()
        e = tk.Entry(sr, textvariable=self.search_var, font=FT, bg=BG, fg=GREEN,
                     insertbackground=GREEN, bd=1, relief="solid",
                     highlightbackground=EDGE)
        e.pack(side="left", fill="x", expand=True, ipady=3)
        e.bind("<Return>", lambda ev: self.search())
        self._btn(sr, "SEARCH", self.search).pack(side="left", padx=(6, 0))
        self.result_list = tk.Listbox(right, font=FTSM, bg=BG, fg=DIM,
                                      selectbackground=SEL, selectforeground=GREEN,
                                      bd=0, highlightthickness=0, activestyle="none")
        self.result_list.pack(fill="both", expand=True, pady=(8, 0))
        self.result_list.bind("<Double-Button-1>", lambda ev: self.add_location())
        self._btn(right, "ADD SELECTED  ←", self.add_location).pack(
            anchor="e", pady=(8, 0))

        # settings ----------------------------------------------------------
        setf = self._frame(self.root, "SETTINGS")
        setf.pack(fill="x", padx=14)
        row = tk.Frame(setf, bg=BG)
        row.pack(fill="x")
        tk.Label(row, text="UNITS", font=FTSM, bg=BG, fg=DIM).pack(side="left")
        self.units_var = tk.StringVar(value=self.cfg.get("units", "F"))
        for u, lbl in (("F", "°F"), ("C", "°C")):
            tk.Radiobutton(row, text=lbl, value=u, variable=self.units_var,
                           command=self.on_units, font=FT, bg=BG, fg=GREEN,
                           selectcolor=BG, activebackground=BG,
                           activeforeground=AMBER).pack(side="left", padx=2)
        tk.Label(row, text="   SD CARD ROOT", font=FTSM, bg=BG,
                 fg=DIM).pack(side="left")
        self.sd_var = tk.StringVar(value=self.cfg.get("sd_path", ""))
        tk.Entry(row, textvariable=self.sd_var, font=FT, bg=BG, fg=GREEN,
                 insertbackground=GREEN, bd=1, relief="solid",
                 highlightbackground=EDGE, width=24).pack(
            side="left", padx=6, ipady=2)
        self._btn(row, "BROWSE…", self.browse_sd).pack(side="left")
        self.out_lbl = tk.Label(setf, text="", font=FTSM, bg=BG, fg=DIM,
                                anchor="w")
        self.out_lbl.pack(fill="x", pady=(6, 0))

        # sync + log --------------------------------------------------------
        act = tk.Frame(self.root, bg=BG)
        act.pack(fill="x", padx=14, pady=(8, 4))
        self.fetch_btn = self._btn(act, "▶  FETCH & SYNC TO SD", self.fetch,
                                   accent=True)
        self.fetch_btn.configure(font=FTBIG, padx=16, pady=8)
        self.fetch_btn.pack(fill="x")
        self.fetch_btn.configure(text=FETCH_LABEL)
        self.install_btn = self._btn(act, INSTALL_LABEL, self.install_app)
        self.install_btn.configure(font=FTBIG, padx=16, pady=8)
        self.install_btn.pack(fill="x", pady=(6, 0))

        logf = self._frame(self.root, "TERMINAL")
        logf.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        self.log_txt = tk.Text(logf, font=FTSM, bg=BG, fg=GREEN, bd=0,
                               highlightthickness=0, height=7, wrap="word")
        self.log_txt.pack(fill="both", expand=True)
        self.log_txt.configure(state="disabled")

    # ----------------------------------------------------------------- data
    def refresh_locations(self):
        self.loc_list.delete(0, "end")
        for l in self.cfg["locations"]:
            self.loc_list.insert("end", " %-22s %s"
                                 % (l.get("name", "?"), l.get("region", "")))

    def update_output_label(self):
        self.out_lbl.configure(text="OUTPUT  ->  " + core.resolve_output(self.cfg))

    def _sel(self, listbox):
        s = listbox.curselection()
        return s[0] if s else None

    def move(self, delta):
        i = self._sel(self.loc_list)
        if i is None:
            return
        j = i + delta
        locs = self.cfg["locations"]
        if 0 <= j < len(locs):
            locs[i], locs[j] = locs[j], locs[i]
            core.save_config(self.cfg)
            self.refresh_locations()
            self.loc_list.selection_set(j)

    def remove_location(self):
        i = self._sel(self.loc_list)
        if i is None:
            return
        removed = self.cfg["locations"].pop(i)
        core.save_config(self.cfg)
        self.refresh_locations()
        self.log("Removed %s." % removed.get("name"))

    def search(self):
        q = self.search_var.get().strip()
        if not q:
            return
        self.result_list.delete(0, "end")
        self.result_list.insert("end", "  searching ...")
        threading.Thread(target=self._search_worker, args=(q,), daemon=True).start()

    def _search_worker(self, q):
        try:
            res = core.geocode_search(q)
        except Exception as e:
            self.q.put(("__search__", []))
            self.q.put(("log", "Search failed: %s" % e))
            return
        self.q.put(("__search__", res))

    def add_location(self):
        i = self._sel(self.result_list)
        if i is None or i >= len(self.search_results):
            return
        r = self.search_results[i]
        self.cfg["locations"].append({"name": r["name"], "region": r["region"],
                                      "lat": r["lat"], "lon": r["lon"]})
        core.save_config(self.cfg)
        self.refresh_locations()
        self.log("Added %s." % r["label"])

    def on_units(self):
        self.cfg["units"] = self.units_var.get()
        core.save_config(self.cfg)
        self.update_output_label()

    def browse_sd(self):
        d = filedialog.askdirectory(title="Select Pip-Boy SD card root")
        if d:
            self.sd_var.set(d)
            self.cfg["sd_path"] = d
            core.save_config(self.cfg)
            self.update_output_label()

    # --------------------------------------------------------------- install
    def install_app(self):
        if self.fetching or self.installing:
            return
        sd = self.sd_var.get().strip()
        if not sd:
            self.log("Set the SD card root before installing app files.")
            return
        self.cfg["sd_path"] = sd
        core.save_config(self.cfg)
        self.update_output_label()
        self.installing = True
        self.install_btn.configure(state="disabled", text="INSTALLING ...")
        self.fetch_btn.configure(state="disabled")
        threading.Thread(target=self._install_worker, args=(sd,), daemon=True).start()

    def _install_worker(self, sd):
        try:
            copied = core.install_app_files(sd)
            for path in copied:
                self.q.put(("log", "  > installed %s" % path))
            self.q.put(("log", "APP INSTALL COMPLETE - %d file(s) copied."
                        % len(copied)))
            self.q.put(("log", "Reboot the Pip-Boy after installing or updating."))
        except Exception as e:
            self.q.put(("log", "INSTALL ERROR: %s" % e))
        finally:
            self.q.put(("__install_done__", None))

    # ---------------------------------------------------------------- fetch
    def fetch(self):
        if self.fetching or self.installing:
            return
        if not self.cfg["locations"]:
            self.log("No locations configured - add some first.")
            return
        self.cfg["sd_path"] = self.sd_var.get().strip()
        core.save_config(self.cfg)
        self.update_output_label()
        self.fetching = True
        self.install_btn.configure(state="disabled")
        self.fetch_btn.configure(state="disabled", text="… SYNCING …")
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        old = sys.stdout
        sys.stdout = _QWriter(self.q)
        try:
            payload = core.build_payload(self.cfg)
            if payload["locations"]:
                core.write_payload(self.cfg, payload)
                print("SYNC COMPLETE - %d location(s) cached."
                      % len(payload["locations"]))
            else:
                print("Nothing fetched - check your connection.")
        except Exception as e:
            print("ERROR: %s" % e)
        finally:
            sys.stdout = old
            self.q.put(("__done__", None))

    # ------------------------------------------------------------ ui pump
    def log(self, msg):
        self.log_txt.configure(state="normal")
        self.log_txt.insert("end", msg.rstrip() + "\n")
        self.log_txt.see("end")
        self.log_txt.configure(state="disabled")

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "__done__":
                    self.fetching = False
                    self.fetch_btn.configure(state="normal",
                                             text="▶  FETCH & SYNC TO SD")
                    self.install_btn.configure(state="normal",
                                               text=INSTALL_LABEL)
                    self.fetch_btn.configure(text=FETCH_LABEL)
                elif kind == "__install_done__":
                    self.installing = False
                    self.install_btn.configure(state="normal",
                                               text=INSTALL_LABEL)
                    self.fetch_btn.configure(state="normal",
                                             text=FETCH_LABEL)
                elif kind == "__search__":
                    self.search_results = payload
                    self.result_list.delete(0, "end")
                    if not payload:
                        self.result_list.insert("end", "  no matches")
                    for r in payload:
                        self.result_list.insert("end", "  " + r["label"])
                elif kind == "log":
                    self.log(payload)
                else:
                    self.log(str(payload))
        except queue.Empty:
            pass
        self.root.after(80, self._poll)


class _QWriter:
    """Redirects core's print() output into the UI log queue."""
    def __init__(self, q):
        self.q = q
        self.buf = ""

    def write(self, s):
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if line.strip():
                self.q.put(("log", line))

    def flush(self):
        pass


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
