#!/usr/bin/env python3
"""HAL user component: drive fault messages, job log, tool life, service counter.

Usage: loadusr -Wn mstats ./machine-stats.py <grease hours>
       ./machine-stats.py reset-tool <tool>     (new tool: clears its ToolLife)

Files, next to this script, not in git:
  machine-stats.json  totals, the source of truth, saved every minute and after each job
  job-stats.csv       one line per program run
  drive-faults.log    drive error codes with time stamps
tool.tbl gets "ToolLife: 1h24 - 354m" in front of each comment after a job and on exit,
regenerated from machine-stats.json, so a tool table rewrite by LinuxCNC (M210) can't lose it.
Cutting = feed or arc move with the spindle on. Service counter = machine on and not in position.
"""
import csv
import datetime
import json
import os
import re
import signal
import sys
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))

STATE = "machine-stats.json"
JOBS = "job-stats.csv"
FAULTS = "drive-faults.log"
TOOL_TABLE = "tool.tbl"
RESET_REQUEST = "tool-life.reset"
DRIVES = ("x-left", "x-right", "y", "z")
FEED, ARC = 2, 3         # motion.motion-type
SAVE_PERIOD = 60         # s
JOB_END_GRACE = 0.5      # s, on_abort's pulse comes after the program is idle
JOB_FIELDS = ("start", "end", "file", "status", "run_time", "paused", "cut_time", "cut_m", "kwh", "tools")
LIFE = re.compile(r"^ToolLife: \d+h\d\d - \d+m\s*")


def write_atomic(path, text):
    with open(path + ".tmp", "w") as f:
        f.write(text)
    os.replace(path + ".tmp", path)


def hms(s):
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def tool_life(seconds, metres):
    h, m = divmod(int(seconds) // 60, 60)
    return f"{h}h{m:02d} - {round(metres)}m"


def tool_table_text(text, tools):
    """text with each tool's ToolLife in front of its comment; 0 cut time removes it."""
    out = []
    for line in text.splitlines():
        m = re.match(r"\s*T(\d+)\b", line)
        life = tools.get(m.group(1)) if m else None
        if life is not None:
            head, _, comment = line.partition(";")
            comment = LIFE.sub("", comment.strip())
            if life["s"] > 0:
                comment = f"ToolLife: {tool_life(life['s'], life['m'])}  {comment}".rstrip()
            line = f"{head.rstrip()}  ;{comment}" if comment else head.rstrip()
        out.append(line)
    return "\n".join(out) + "\n"


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except FileNotFoundError:
        pass
    except ValueError:
        os.replace(STATE, STATE + ".bad")
    return {"tools": {}, "service_s": 0.0}


class Stats:
    def __init__(self, grease_hours, notify, program_file):
        self.limit = grease_hours * 3600
        self.notify, self.program_file = notify, program_file   # notify(text, is_error)
        self.state = load_state()
        self.last_save = self.last_t = None
        self.job = None
        self.end_at = None
        self.codes = [0] * len(DRIVES)
        self.was_on = self.was_reset = False

    def save(self):
        write_atomic(STATE, json.dumps(self.state, indent=1))

    def update_tool_table(self):
        try:
            with open(TOOL_TABLE) as f:
                old = f.read()
            new = tool_table_text(old, self.state["tools"])
            if new != old:
                write_atomic(TOOL_TABLE, new)
        except OSError as e:
            self.notify(f"Tool table not updated: {e}", True)

    def check_drives(self, p, now):
        for i, name in enumerate(DRIVES):
            code = p[f"error-{i}"]
            if code != self.codes[i]:
                self.codes[i] = code
                if code:
                    text = f"Drive {name}: error code 0x{code:04X}"
                    self.notify(text + " (603Fh, see the A6 manual)", True)
                    with open(FAULTS, "a") as f:
                        f.write(f"{datetime.datetime.now().isoformat(' ', 'seconds')} {text}\n")

    def check_service(self, p, dt):
        due = self.state["service_s"] >= self.limit
        if p["machine-on"] and not p["in-position"]:
            self.state["service_s"] += dt
        reset = p["service-reset"]
        if reset and not self.was_reset:
            self.state["service_s"] = 0.0
            self.save()
        self.was_reset = reset
        now_due = self.state["service_s"] >= self.limit
        if now_due and (not due or (p["machine-on"] and not self.was_on)):
            self.notify(f"Service: {self.limit / 3600:g} h of movement reached - grease all parts, then press Greased", False)
        self.was_on = p["machine-on"]
        p["service-due"] = now_due
        p["service-hours-left"] = max(0.0, (self.limit - self.state["service_s"]) / 3600)

    def add_cut(self, p, dt):
        if not (p["spindle-on"] and p["motion-type"] in (FEED, ARC)):
            return
        metres = p["current-vel"] * dt / 1000
        tool = p["tool"]
        if tool > 0:
            life = self.state["tools"].setdefault(str(tool), {"s": 0.0, "m": 0.0})
            life["s"] += dt
            life["m"] += metres
        if self.job:
            self.job["cut_s"] += dt
            self.job["cut_m"] += metres
            t = self.job["tools"].setdefault(tool, [0.0, 0.0])
            t[0] += dt
            t[1] += metres

    def start_job(self, p):
        self.job = {"start": datetime.datetime.now(), "file": self.program_file(), "paused": 0.0, "cut_s": 0.0,
                    "cut_m": 0.0, "tools": {}, "aborted": False,
                    "kwh": p["session-kwh"] if p["shelly-ok"] else None}

    def finish_job(self, p):
        j, self.job, self.end_at = self.job, None, None
        end = datetime.datetime.now()
        kwh = p["session-kwh"] - j["kwh"] if p["shelly-ok"] and j["kwh"] is not None else None
        row = (j["start"].isoformat(" ", "seconds"), end.isoformat(" ", "seconds"), j["file"],
               "aborted" if j["aborted"] else "finished",
               hms(max(0, (end - j["start"]).total_seconds() - j["paused"])), hms(j["paused"]),
               hms(j["cut_s"]), f"{j['cut_m']:.1f}", "" if kwh is None else f"{kwh:.3f}",
               " ".join(f"T{t}:{tool_life(s, m).replace(' - ', '/')}" for t, (s, m) in sorted(j["tools"].items())))
        new = not os.path.exists(JOBS)
        with open(JOBS, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(JOB_FIELDS)
            w.writerow(row)
        self.save()
        self.update_tool_table()

    def track_job(self, p, dt, now):
        running = not p["program-idle"] and p["mode-auto"]
        if self.job and self.end_at is None and p["program-idle"]:
            self.end_at = now + JOB_END_GRACE
        if self.job:
            self.job["aborted"] = self.job["aborted"] or p["job-aborted"]
            if p["program-paused"]:
                self.job["paused"] += dt
            if self.end_at is not None and (now >= self.end_at or running):
                self.finish_job(p)
        if running and not self.job:
            self.start_job(p)

    def check_reset_request(self, p):
        if p["program-idle"] and os.path.exists(RESET_REQUEST):
            with open(RESET_REQUEST) as f:
                tools = f.read().split()
            os.remove(RESET_REQUEST)
            for t in tools:
                self.state["tools"][t] = {"s": 0.0, "m": 0.0}
            self.save()
            self.update_tool_table()

    def tick(self, p, now):
        dt = min(now - self.last_t, 1.0) if self.last_t is not None else 0.0
        self.last_t = now
        self.check_drives(p, now)
        self.check_service(p, dt)
        self.add_cut(p, dt)
        self.track_job(p, dt, now)
        self.check_reset_request(p)
        if self.last_save is None or now - self.last_save >= SAVE_PERIOD:
            self.last_save = now
            self.save()


def main():
    import hal
    import linuxcnc

    h = hal.component("mstats")
    for name, kind in (("program-idle", hal.HAL_BIT), ("program-paused", hal.HAL_BIT), ("mode-auto", hal.HAL_BIT),
                       ("spindle-on", hal.HAL_BIT), ("machine-on", hal.HAL_BIT), ("in-position", hal.HAL_BIT),
                       ("job-aborted", hal.HAL_BIT), ("shelly-ok", hal.HAL_BIT), ("service-reset", hal.HAL_BIT),
                       ("motion-type", hal.HAL_S32), ("tool", hal.HAL_S32),
                       ("current-vel", hal.HAL_FLOAT), ("session-kwh", hal.HAL_FLOAT)):
        h.newpin(name, kind, hal.HAL_IN)
    for i in range(len(DRIVES)):
        h.newpin(f"error-{i}", hal.HAL_U32, hal.HAL_IN)
    h.newpin("service-due", hal.HAL_BIT, hal.HAL_OUT)
    h.newpin("service-hours-left", hal.HAL_FLOAT, hal.HAL_OUT)
    h.ready()

    command, status = linuxcnc.command(), linuxcnc.stat()

    def notify(text, is_error):
        (command.error_msg if is_error else command.display_msg)(text)

    def program_file():
        try:
            status.poll()
            return status.file
        except linuxcnc.error:
            return ""

    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    stats = Stats(float(sys.argv[1]), notify, program_file)
    try:
        while True:
            stats.tick(h, time.monotonic())
            time.sleep(0.05)
    except KeyboardInterrupt:
        stats.save()
        stats.update_tool_table()


if __name__ == "__main__":
    if sys.argv[1:2] == ["reset-tool"]:
        with open(RESET_REQUEST, "a") as f:
            f.write(f"{int(sys.argv[2])}\n")
    else:
        main()
