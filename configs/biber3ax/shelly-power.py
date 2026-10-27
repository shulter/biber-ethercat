#!/usr/bin/env python3
"""HAL user component: workshop power from a Shelly Pro 3EM (local RPC API).

Usage: loadusr -Wn shelly ./shelly-power.py <host>
Pins: shelly.power-kw (total active power), shelly.session-kwh (energy since
start), shelly.ok (last poll succeeded).
The Shelly's energy counter only advances about once a minute, so session-kwh
is the power integrated up to the counter's first step, then the counter delta
plus the power integrated since its last step.
"""
import json
import sys
import time
import urllib.request

import hal

host = sys.argv[1] if len(sys.argv) > 1 else "172.20.10.2"
url = f"http://{host}/rpc/Shelly.GetStatus"

h = hal.component("shelly")
h.newpin("power-kw", hal.HAL_FLOAT, hal.HAL_OUT)
h.newpin("session-kwh", hal.HAL_FLOAT, hal.HAL_OUT)
h.newpin("ok", hal.HAL_BIT, hal.HAL_OUT)
h.ready()

first = start = last_counter = None   # Wh
offset = 0.0    # Wh integrated before the counter's first step
partial = 0.0   # Wh integrated since the last counter step
last_t = None

try:
    while True:
        try:
            with urllib.request.urlopen(url, timeout=0.8) as r:
                d = json.load(r)
            p = d["em:0"]["total_act_power"]   # W
            counter = d["emdata:0"]["total_act"]  # Wh
            now = time.monotonic()
            if first is None:
                first = last_counter = counter
            elif counter != last_counter:
                if start is None:
                    start, offset = counter, partial
                last_counter, partial = counter, 0.0
            elif last_t is not None and now - last_t < 10:
                partial += p * (now - last_t) / 3600
            last_t = now
            h["power-kw"] = p / 1000
            base = offset + last_counter - start if start is not None else 0.0
            h["session-kwh"] = (base + partial) / 1000
            h["ok"] = True
        except Exception:
            h["ok"] = False
            last_t = None
        time.sleep(1)
except KeyboardInterrupt:
    pass
