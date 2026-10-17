#!/usr/bin/env python3
"""A6-EC servo tuning over EtherCAT SDO (ethercat upload/download), usable while LinuxCNC runs.

Parameter Cgg.xx = object 0x20gg:(xx+1), see the A6-EC manual ch. 7 / p. 201-203. Gains and speed FF
only take effect with C00.04 auto-tuning mode = 0 (manual); otherwise the drive sets them itself.
Values are shown in engineering units. Peak following error comes from the drives' 60F4
PDO (lcec.0.<drive>.following-error, mm) via halcmd when LinuxCNC is running.
"""
import subprocess
import tkinter as tk
import os
from tkinter import filedialog, messagebox

DRIVES = [(0, "x-left"), (1, "x-right"), (2, "y"), (3, "z")]
GANTRY = (0, 1)

# (name, param, address 0xIIIISS, scale, unit, raw min, raw max, at stop only)
PARAMS = [
    ("Auto-tuning (0=manual)",  "C00.04", 0x200005, 1,    "0/1/2", 0, 2,     False),
    ("Stiffness level",     "C00.05", 0x200006, 1,    "-",     1, 31,    False),
    ("Load inertia ratio",  "C00.06", 0x200007, 1,    "%",     0, 12000, False),
    ("Gain switchover (0=off)", "C01.38", 0x200139, 1, "0-8",  0, 8,     False),
    ("Switchover time",     "C01.39", 0x20013A, 0.1,  "ms",    10, 10000, False),
    ("Switchover threshold", "C01.3A", 0x20013B, 1,   "mode unit", 0, 65535, False),
    ("Switchover loop width", "C01.3B", 0x20013C, 1,  "mode unit", 0, 65535, False),
    ("1st position loop gain",  "C01.00", 0x200101, 0.1,  "rad/s", 0, 20000, False),
    ("1st speed loop gain",     "C01.01", 0x200102, 0.1,  "Hz",    1, 20000, False),
    ("1st speed integral time", "C01.02", 0x200103, 0.01, "ms",    1, 51200, False),
    ("1st torque ref. filter",  "C01.03", 0x200104, 1,    "Hz",    5, 16000, False),
    ("2nd position loop gain",  "C01.08", 0x200109, 0.1,  "rad/s", 0, 20000, False),
    ("2nd speed loop gain",     "C01.09", 0x20010A, 0.1,  "Hz",    1, 20000, False),
    ("2nd speed integral time", "C01.0A", 0x20010B, 0.01, "ms",    1, 51200, False),
    ("2nd torque ref. filter",  "C01.0B", 0x20010C, 1,    "Hz",    5, 16000, False),
    ("Speed FF source",     "C01.13", 0x200114, 1,    "0/1/2/5", 0, 5,   True),
    ("Speed FF",            "C01.14", 0x200115, 0.1,  "%",     0, 2000,  False),
    ("Speed FF filter",     "C01.15", 0x200116, 1,    "Hz",    5, 16000, False),
    ("Torque FF source",    "C01.16", 0x200117, 1,    "0/1/2/5", 0, 5,   True),
    ("Torque FF",           "C01.17", 0x200118, 0.1,  "%",     0, 2000,  False),
    ("Torque FF filter",    "C01.18", 0x200119, 1,    "Hz",    5, 16000, False),
    ("PDFF coefficient",    "C01.1B", 0x20011C, 0.1,  "%",     0, 1000,  False),
    ("Adaptive notch mode", "C01.30", 0x200131, 1,    "0-4",   0, 4,     False),
    ("1st notch frequency", "C01.40", 0x200141, 1,    "Hz",    10, 8000, False),
    ("1st notch width",     "C01.41", 0x200142, 0.1,  "%",     0, 4000,  False),
    ("1st notch depth",     "C01.42", 0x200143, 0.1,  "%",     10, 1000, False),
    ("2nd notch frequency", "C01.43", 0x200144, 1,    "Hz",    10, 8000, False),
    ("2nd notch width",     "C01.44", 0x200145, 0.1,  "%",     0, 4000,  False),
    ("2nd notch depth",     "C01.45", 0x200146, 0.1,  "%",     10, 1000, False),
    ("3rd notch frequency", "C01.46", 0x200147, 1,    "Hz",    10, 8000, False),
    ("3rd notch width",     "C01.47", 0x200148, 0.1,  "%",     0, 4000,  False),
    ("3rd notch depth",     "C01.48", 0x200149, 0.1,  "%",     10, 1000, False),
    ("4th notch frequency", "C01.49", 0x20014A, 1,    "Hz",    10, 8000, False),
    ("4th notch width",     "C01.4A", 0x20014B, 0.1,  "%",     0, 4000,  False),
    ("4th notch depth",     "C01.4B", 0x20014C, 0.1,  "%",     10, 1000, False),
    ("Resonance test result", "C01.31", 0x200132, 1,  "-",     0, 65535, False),
]


def sdo_read(pos, addr):
    out = subprocess.run(["ethercat", "upload", "-p", str(pos), "-t", "uint16", hex(addr >> 8), hex(addr & 0xff)],
                         capture_output=True, text=True, timeout=5)
    if out.returncode:
        raise RuntimeError(out.stderr.strip())
    return int(out.stdout.split()[1])


def sdo_write(pos, addr, raw):
    out = subprocess.run(["ethercat", "download", "-p", str(pos), "-t", "uint16", hex(addr >> 8), hex(addr & 0xff), str(raw)],
                         capture_output=True, text=True, timeout=5)
    if out.returncode:
        raise RuntimeError(out.stderr.strip())


def num(txt):
    return float(txt.strip().replace(",", "."))  # decimal comma ok


def fmt(raw, scale):
    return f"{raw * scale:.{ {1: 0, 0.1: 1, 0.01: 2}[scale]}f}"


# Tooltips: what each parameter does and how to tune it (A6-EC manual ch. 7)
TIPS = {
    "C00.04": "0 = manual: required for the gains and speed FF below to take effect.\n1/2 = auto-tuning: the drive sets the gains itself from the stiffness level\n(2 also sets up gain switchover and holds speed FF at 30 %).",
    "C00.05": "Only used with auto-tuning (C00.04 = 1/2). Higher = stiffer and faster,\ntoo high = vibration. Ignored in manual mode.",
    "C00.06": "Load inertia ratio. Torque FF is scaled with it: too low = error during\nacceleration even with torque FF on.",
    "C01.38": "Automatic switch between gain sets 1 and 2. 0 = off (always set 1),\nrecommended for CNC path motion. 7 = switch on position error (auto-tuning default).",
    "C01.39": "Blend time when switching between gain sets. Only used if C01.38 > 0.",
    "C01.3A": "Switching point; unit depends on the C01.38 mode (counts, rpm, 0.1 %).\nOnly used if C01.38 > 0.",
    "C01.3B": "Hysteresis around the threshold so the drive doesn't flip back and forth.\nOnly used if C01.38 > 0.",
    "C01.00": "Position loop stiffness. Raise after the speed loop is tuned; keep below\nspeed loop gain [Hz] x 2pi / 4 (manual: speed loop 3-5x faster).\nToo high = overshoot / ringing when stopping.",
    "C01.01": "Speed loop responsiveness. Raise in ~10 % steps until whining or vibration,\nthen back off 20-30 %. Lower the integral time along with it.",
    "C01.02": "Speed loop integral time. Smaller = stronger integral, holds position\nunder load. Rule of thumb ~ 640 / speed loop gain [Hz] ms. Too small = oscillation.",
    "C01.03": "Torque command low-pass. Higher = less delay, allows higher gains;\nlower = quieter. Lower it if the motor whines.",
    "C01.08": "Gain set 2 position loop gain. Only used if C01.38 > 0.",
    "C01.09": "Gain set 2 speed loop gain. Only used if C01.38 > 0.",
    "C01.0A": "Gain set 2 speed integral time (512 ms = practically no integral).\nOnly used if C01.38 > 0.",
    "C01.0B": "Gain set 2 torque filter. Only used if C01.38 > 0.",
    "C01.13": "Where the speed FF signal comes from. Keep 1 (internal, from LinuxCNC's\ntarget positions). 2 = model tracking, 5 = from LinuxCNC via 60B1h. Servo off to change.",
    "C01.14": "Share of the commanded speed fed straight into the speed loop.\nRemoves the error at constant speed. Raise towards ~100 %; if the constant-speed\nerror flips sign, it's too high.",
    "C01.15": "Smooths the speed FF. Its delay shows as error at constant speed\n(~speed x 1/(2pi f)). Raise (1000-4000 Hz) until it gets noisy.",
    "C01.16": "Torque FF source. 1 = internal (from the speed command). Servo off to change.",
    "C01.17": "Adds torque for acceleration. Removes the error while accelerating/braking.\nRaise in steps; too much = error in the opposite direction or overshoot.",
    "C01.18": "Smooths the torque FF. Lower it to soften the spikes where acceleration\nstarts/stops; higher = faster.",
    "C01.30": "Adaptive notch against resonance (whine/hum). The manual contradicts itself on\nwhich notches it fills (1/2 in ch. 7.14, 3/4 on p. 235): check all of them after Read all.\n1 = one adaptive notch, 2 = two, 3 = reset adaptive notches, 4 = only detect\n(result in C01.31). Only reacts while a resonance is actually excited.\nSet back to 0 once values are found, so they stay fixed.",
    "C01.31": "Mode C01.30 = 4: detected resonance (manual p. 235). 0 = nothing detected.",
    "C01.40": "Notch 1 centre frequency (8000 = off). Set to the resonance frequency.",
    "C01.41": "Notch width. Wider = covers more frequencies, but more delay.",
    "C01.42": "Notch depth. 100 % = no cut, lower = deeper cut at the notch frequency.",
    "C01.43": "Notch 2 centre frequency (8000 = off).",
    "C01.44": "Notch width.",
    "C01.45": "Notch depth. 100 % = no cut, lower = deeper.",
    "C01.46": "Notch 3 centre frequency (8000 = off). Possibly filled by the adaptive notch.",
    "C01.47": "Notch width.",
    "C01.48": "Notch depth. 100 % = no cut, lower = deeper.",
    "C01.49": "Notch 4 centre frequency (8000 = off). Possibly filled by the adaptive notch (C01.30 = 2).",
    "C01.4A": "Notch width.",
    "C01.4B": "Notch depth. 100 % = no cut, lower = deeper.",
    "C01.1B": "100 % = PI speed loop (fast); lower = IP (less overshoot, slower).\nUsually leave at 100 %.",
}


# Only used with gain switchover on (C01.38 > 0): dimmed while it's off
# Results / read-only, not written back at startup
NO_EXPORT = {"C01.31"}

SWITCHOVER = 0x200139
SET2 = {0x20013A, 0x20013B, 0x20013C, 0x200109, 0x20010A, 0x20010B, 0x20010C}
DIM = "gray60"


class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.win = widget, text, None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _e):
        self.win = tk.Toplevel(self.widget)
        self.win.wm_overrideredirect(True)
        self.win.geometry(f"+{self.widget.winfo_rootx() + 20}+{self.widget.winfo_rooty() + 22}")
        tk.Label(self.win, text=self.text, justify="left", bg="#ffffe0", relief="solid", bd=1,
                 padx=6, pady=4).pack()

    def hide(self, _e):
        if self.win:
            self.win.destroy()
            self.win = None


class App:
    def __init__(self, root):
        self.root = root
        root.title("A6 servo tuning")
        self.raw = {}      # (pos, sub) -> raw value last read/written
        self.vars = {}     # (pos, sub) -> StringVar
        self.entries = {}
        self.labels = {}   # addr -> row label
        self.peak = {pos: 0.0 for pos, _ in DRIVES}
        self.link = tk.BooleanVar(value=True)

        g = tk.Frame(root, padx=8, pady=8)
        g.pack(fill="both")
        tk.Label(g, text="Parameter", font="TkDefaultFont 9 bold").grid(row=0, column=0, sticky="w")
        tk.Label(g, text="Unit", font="TkDefaultFont 9 bold").grid(row=0, column=1, sticky="w", padx=4)
        for c, (pos, name) in enumerate(DRIVES):
            tk.Label(g, text=name, font="TkDefaultFont 9 bold").grid(row=0, column=2 + c)
        for r, (label, par, sub, scale, unit, lo, hi, stop) in enumerate(PARAMS, 1):
            lbl = tk.Label(g, text=f"{par}  {label}" + ("  (servo off)" if stop else ""))
            lbl.grid(row=r, column=0, sticky="w")
            self.labels[sub] = lbl
            if par in TIPS:
                Tooltip(lbl, TIPS[par])
            tk.Label(g, text=unit).grid(row=r, column=1, sticky="w", padx=4)
            for c, (pos, _) in enumerate(DRIVES):
                v = tk.StringVar()
                e = tk.Entry(g, textvariable=v, width=9, justify="right")
                e.grid(row=r, column=2 + c, padx=2, pady=1)
                v.trace_add("write", lambda *_, k=(pos, sub): self.edited(k))
                e.bind("<Return>", lambda _e: self.write_changed())
                self.vars[pos, sub], self.entries[pos, sub] = v, e

        r = len(PARAMS) + 1
        tk.Label(g, text="Peak following error", font="TkDefaultFont 9 bold").grid(row=r, column=0, sticky="w", pady=(8, 0))
        tk.Label(g, text="mm").grid(row=r, column=1, sticky="w", padx=4, pady=(8, 0))
        self.fe = {}
        for c, (pos, _) in enumerate(DRIVES):
            self.fe[pos] = tk.Label(g, text="-", width=9, anchor="e")
            self.fe[pos].grid(row=r, column=2 + c, pady=(8, 0))

        b = tk.Frame(root, padx=8, pady=8)
        b.pack(fill="x")
        tk.Button(b, text="Read all", command=self.read_all).pack(side="left")
        tk.Button(b, text="Write changed", command=self.write_changed).pack(side="left", padx=4)
        tk.Button(b, text="Reset peak", command=self.reset_peak).pack(side="left")
        tk.Button(b, text="sdoConfig XML", command=self.show_xml).pack(side="left", padx=4)
        tk.Checkbutton(b, text="Link X gantry drives", variable=self.link).pack(side="left", padx=8)
        self.status = tk.Label(root, anchor="w", padx=8, fg="gray30")
        self.status.pack(fill="x", pady=(0, 6))

        self.read_all()
        self.poll_fe()

    def dim_set2(self):
        # per drive from its C01.38 on the drive; row labels only if it's off on all drives
        off = {pos: self.raw.get((pos, SWITCHOVER)) == 0 for pos, _ in DRIVES}
        for addr in SET2:
            for pos, _ in DRIVES:
                self.entries[pos, addr].config(fg=DIM if off[pos] else "black")
            self.labels[addr].config(fg=DIM if all(off.values()) else "black")

    def say(self, msg, err=False):
        self.status.config(text=msg, fg="red3" if err else "green4")
        if err:
            messagebox.showerror("A6 servo tuning", msg, parent=self.root)

    def edited(self, key):
        sub = key[1]
        p = next(p for p in PARAMS if p[2] == sub)
        txt = self.vars[key].get()
        try:
            raw = round(num(txt) / p[3])
            ok = p[5] <= raw <= p[6]
        except ValueError:
            raw, ok = None, False
        changed = key in self.raw and raw != self.raw[key]
        self.entries[key].config(bg="#ffb0b0" if not ok else "#fff0a0" if changed else "white")
        # Mirror edits between the two gantry drives
        if self.link.get() and key[0] in GANTRY and not getattr(self, "_mirroring", False):
            other = (GANTRY[1] if key[0] == GANTRY[0] else GANTRY[0], sub)
            if self.vars[other].get() != txt:
                self._mirroring = True
                self.vars[other].set(txt)
                self._mirroring = False

    def read_all(self):
        errors = []
        for pos, name in DRIVES:
            for p in PARAMS:
                try:
                    self.raw[pos, p[2]] = sdo_read(pos, p[2])
                    self.vars[pos, p[2]].set(fmt(self.raw[pos, p[2]], p[3]))
                except Exception as e:
                    errors.append(f"{name} {p[1]}: {e}")
        self.dim_set2()
        self.say(errors[0] if errors else "Read all drives.", bool(errors))

    def write_changed(self):
        todo = []
        for (pos, sub), v in self.vars.items():
            p = next(p for p in PARAMS if p[2] == sub)
            try:
                raw = round(num(v.get()) / p[3])
            except ValueError:
                return self.say(f"{dict(DRIVES)[pos]} {p[1]}: not a number: \"{v.get()}\"", True)
            if not p[5] <= raw <= p[6]:
                return self.say(f"{dict(DRIVES)[pos]} {p[1]}: out of range {fmt(p[5], p[3])}..{fmt(p[6], p[3])}", True)
            if raw != self.raw.get((pos, sub)):
                todo.append((pos, p, raw))
        if not todo:
            return self.say("Nothing changed.")
        if any(p[7] for _, p, _ in todo) and not messagebox.askokcancel(
                "Servo off", "Feedforward source changes only take effect with the servo off (machine off). Write anyway?"):
            return
        done = []
        for pos, p, raw in todo:
            try:
                sdo_write(pos, p[2], raw)
                self.raw[pos, p[2]] = sdo_read(pos, p[2])
                self.vars[pos, p[2]].set(fmt(self.raw[pos, p[2]], p[3]))
                done.append(f"{dict(DRIVES)[pos]} {p[1]}={fmt(raw, p[3])}")
            except Exception as e:
                return self.say(f"{dict(DRIVES)[pos]} {p[1]}: {e}", True)
        self.dim_set2()
        self.say("Wrote " + ", ".join(done))

    def poll_fe(self):
        try:
            out = subprocess.run(["halcmd", "-s", "show", "pin", "lcec.0."],
                                 capture_output=True, text=True, timeout=1).stdout
            vals = {f[4]: float(f[3]) for f in map(str.split, out.splitlines())
                    if len(f) >= 5 and f[4].endswith(".following-error")}
        except Exception:
            vals = {}
        for pos, name in DRIVES:
            v = vals.get(f"lcec.0.{name}.following-error")
            if v is None:
                self.fe[pos].config(text="-")
            else:
                self.peak[pos] = max(self.peak[pos], abs(v))
                self.fe[pos].config(text=f"{self.peak[pos]:.3f}")
        self.root.after(100, self.poll_fe)

    def reset_peak(self):
        self.peak = {pos: 0.0 for pos, _ in DRIVES}

    def show_xml(self):
        # lcec <sdoConfig> entries (U16, little endian) to make the values permanent in ethercat-conf.xml
        lines = []
        for pos, name in DRIVES:
            lines.append(f"<!-- {name} (slave idx {pos}) -->")
            for p in PARAMS:
                raw = self.raw.get((pos, p[2]))
                if raw is not None and p[1] not in NO_EXPORT:
                    lines.append(f'<sdoConfig idx="{p[2] >> 8:04X}" subIdx="{p[2] & 0xff:02X}"><sdoDataRaw data="{raw & 0xff:02X} {raw >> 8:02X}"/></sdoConfig>'
                                 f'  <!-- {p[1]} = {fmt(raw, p[3])} {p[4]} -->')
        text = "\n".join(lines) + "\n"
        w = tk.Toplevel(self.root)
        w.title("sdoConfig XML")
        b = tk.Frame(w, padx=6, pady=6)
        b.pack(fill="x")
        t = tk.Text(w, width=110, height=30)
        t.pack(fill="both", expand=True)
        t.insert("1.0", text)

        def copy():
            # X11: the clipboard lives in this app, so paste before closing the tool
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.say("XML copied to clipboard (paste before closing the tool).")

        def save():
            path = filedialog.asksaveasfilename(
                parent=w, title="Save sdoConfig XML", defaultextension=".xml", initialfile="servo-tuning.xml",
                initialdir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "configs", "biber3ax"))
            if path:
                with open(path, "w") as f:
                    f.write(text)
                self.say(f"Saved {path}")

        tk.Button(b, text="Copy", command=copy).pack(side="left")
        tk.Button(b, text="Save...", command=save).pack(side="left", padx=4)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
