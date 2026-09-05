# Vantage 33M — Bench I/O Config (benchtest-io)

LinuxCNC configuration for bench-testing three StepperOnline A6 EtherCAT servos, one per axis
(X, Y, Z, no gantry pairing), plus the full Beckhoff EK1100 I/O terminal chain (40 DI / 32 DO)
and an EL4032 analog output terminal driving the spindle VFD's 0-10V speed input.

## Quick Start

1. Install dependencies on the LinuxCNC PC:
   ```bash
   # linuxcnc-ethercat (lcec) — see https://github.com/linuxcnc-ethercat/linuxcnc-ethercat
   # hal-cia402 — build cia402.comp and install
   ```

2. Configure EtherCAT master in `/etc/ethercat.conf` (set `MASTER0_DEVICE` to your NIC MAC).

3. Verify slaves are detected:
   ```bash
   sudo ethercat slaves
   # Expected: 15 devices — three A6/SV660N servos at position 0-2, then the
   # Beckhoff chain at 3-14 (EK1100, 4x EL1808, 4x EL2808, EL9110, EL1018,
   # EL4032). idx in ethercat-conf.xml must match this position column
   # exactly, or PDO registration fails ("Failed to register PDO entry").
   ```

4. Copy or symlink this config directory to your LinuxCNC configs path, then start:
   ```bash
   linuxcnc /path/to/benchtest-io.ini
   ```

5. Turn Machine On, enable all joints, jog X, Y, and Z. Each axis moves its own motor
   independently. Confirm the first EL2808's channel 0 output energizes (machine-enable
   indicator). Command a spindle speed (`M3 S<rpm>` or the AXIS spindle speed control) to
   verify the 0-10V output reaches the VFD.

## Files

| File | Purpose |
|------|---------|
| `benchtest-io.ini` | Machine parameters, joint limits, kinematics, spindle display range |
| `ethercat.hal` | lcec + cia402 wiring for 3 servos, plus EL4032 spindle analog-out wiring |
| `io.hal` | Beckhoff digital I/O terminal wiring (machine-enable output; rest are placeholders) |
| `ethercat-conf.xml` | EtherCAT slave topology and PDO mapping (servos, full Beckhoff chain) |
| `panel.xml` | PyVCP panel, shown beside the preview: 3x servo torque/speed bars + spindle speed bar |
| `postgui.hal` | HAL wiring for `panel.xml`'s pins (loaded after the GUI starts, see below) |
| `tool.tbl` | Minimal tool table |

## Joint / Axis Mapping

Joint numbers follow physical EtherCAT bus position (slave idx 0, 1, 2), which does not match
alphabetical axis order — `[KINS] KINEMATICS = trivkins coordinates=XZY` reflects this:

| Joint | Slave idx | Slave name | Axis |
|-------|-----------|------------|------|
| 0 | 0 | `x` | X |
| 1 | 1 | `z` | Z |
| 2 | 2 | `y` | Y |

## EtherCAT Bus Order

```
[0] x  [1] z  [2] y
[3] EK1100  [4] EL1808  [5] EL2808  [6] EL1808  [7] EL2808
[8] EL9110  [9] EL1808  [10] EL2808  [11] EL1808  [12] EL2808
[13] EL1018  [14] EL4032 (spindle)
```

## Machine I/O (Beckhoff)

- **EL1808 x4** — 8-channel digital input each (32 DI total, 3ms filter). Net names in `io.hal` are
  placeholders (`io-din1-0` ... `io-din4-7`), all commented out — assign to actual signals (e-stop
  chain, door interlocks, limit switches, etc.) once wiring is known. See `docs/retrofit-plan.md`
  Phase 4.
- **EL1018** — 8-channel digital input, 10us fast response (no input filtering) — for signals that need
  to be caught quickly, e.g. a probe or index pulse. Net names (`io-din5-0` ... `io-din5-7`) are
  placeholders like the EL1808s.
- **EL2808 x4** — 8-channel digital output each (32 DO total). Same placeholder scheme
  (`io-dout1-1` ... `io-dout4-7`), except **`io-dout1.dout-0`**, which is actively wired: it drives a
  machine-enable indicator (lamp/relay) from `halui.machine.is-on` — energized whenever LinuxCNC is
  switched on. This is a status output, not the safety interlock chain feeding
  `iocontrol.0.emc-enable-in`.
- **EL9110** — E-bus power supply feed terminal. No process data, no HAL pins; just refreshes bus power
  for the terminals downstream of it. Physically present at bus position 8 but **not declared** in
  `ethercat-conf.xml` — this lcec build doesn't recognize its type, and since it has nothing to
  configure, an undeclared bus position is harmless (EtherCAT frames pass through it regardless).
  Declaring it as `type="generic"` without the correct `vid`/`pid` previously broke the whole master's
  PDO registration (`Failed to register PDO entry: No such file or directory`) — don't add it back
  without real Beckhoff vid/pid values for it.

Pin names (`din-N`, `dout-N`) follow the standard lcec Beckhoff terminal driver naming and are
unverified on this hardware — confirm with `halcmd show pin` once running.

## Bench vs Machine Settings

| Setting | Bench | Full machine |
|---------|-------|--------------|
| Soft limits (X) | ±500 mm | 0–3780 mm |
| Soft limits (Y) | 0–500 mm | 0–1651 mm |
| Soft limits (Z) | -155–0 mm | -155–0 mm |
| Max velocity | 200 mm/s (X/Y/Z) | 1215 mm/s (X) / 967 mm/s (Y) / 250 mm/s (Z) |
| Max acceleration | 500 mm/s² | 5000 mm/s² |
| Max jerk | 5000 mm/s³ | 50000 mm/s³ |
| NO_FORCE_HOMING | 1 | 0 |
| Joints | 3 (X, Z, Y) | 3 (X, Z, Y) |

This config uses LinuxCNC's jerk-limited (S-curve) trajectory planner: `MAX_JERK` is set at
`[TRAJ]`, each `[AXIS_x]`, and each `[JOINT_n]` (10× `MAX_ACCELERATION`, see
`docs/kinematics.md`). It requires a LinuxCNC build with S-curve TP support — if `MAX_JERK` isn't
recognized by your build, remove those lines to fall back to the trapezoidal planner.

## Spindle (Beckhoff EL4032 → VFD)

Max speed 24000 RPM, controlled by a 0-10V analog signal on EL4032 channel 0 (channel 1 unused).
Wiring is in `ethercat.hal`: `spindle.0.speed-out-abs` -> `spindle-scale` (gain 10V/24000RPM =
0.00041667) -> `lcec.0.spindle.aout-0-value`. `spindle.0.on` gates `lcec.0.spindle.aout-0-enable`
(the terminal's output stays disabled/0V unless the spindle is actually commanded on).
`[DISPLAY]` `*_SPINDLE_0_*` settings in `benchtest-io.ini` set the speed range (0-24000 RPM) and
override limits (50-100%) used by the S-word and spindle override slider.

**Not yet verified on hardware:** the EL4032 uses lcec's shared `aout` analog-output class
(`aout-0-value`, `-scale`, `-offset`, `-enable`, ...; there is no flat `ao-N` pin — confirmed via
`strings /usr/lib/linuxcnc/modules/lcec.so`, which shows `lcec_class_aout.c`). `spindle-scale`'s
gain assumes `aout-0-value` takes volts directly with the terminal's own `aout-0-scale`/`-offset`
left at their defaults — this isn't confirmed. **Before trusting the VFD sees the right speed**,
command a known RPM and measure the actual voltage at the EL4032's output terminals with a
multimeter; if it's off, either adjust `spindle-scale.gain` in `ethercat.hal`, or set
`lcec.0.spindle.aout-0-scale`/`-offset` directly (run `halcmd show pin lcec.0.spindle` to see
their current values and defaults).

There is no spindle encoder in this design — only an open-loop 0-10V command to the VFD — so both
the panel display and `spindle.0.speed-out-abs` reflect *commanded* speed, not measured feedback.

## Servo Torque / Speed / Spindle Panel

A PyVCP panel (`[DISPLAY] PYVCP = panel.xml`) renders in the pane beside the g-code preview — no
separate tab, no embedding setup. It has three groups:

- **Servo Torque** — per servo (X, Z, Y): a bidirectional bar graph (-10 to 0 to +10 Nm —
  empty at 0, red toward negative, green toward positive), fed live from each drive's `actual-torque`
  PDO (6077h, CiA402-standard 0.1%-of-rated-torque, signed). 12 Nm is assumed to be the A6/SV660N's
  rated torque (100% = 1000 raw counts) — verify against the datasheet and adjust `postgui.hal`'s
  `*-torque-scale.gain` (currently 0.012 Nm/count) if it differs; the bar's ±10 Nm range is just the
  display window and will clip values beyond it.
- **Servo Speed** — per servo (X, Z, Y): a 0-6000 RPM bar showing absolute speed, fed from each drive's
  `actual-velocity` PDO (606Ch). Assumed raw units are encoder counts/s (131072 counts/rev, no SI
  velocity object configured) — RPM = counts/s × 60/131072 — verify this against the A6/SV660N drive
  parameters; if wrong, `postgui.hal`'s `*-vel-scale.gain` (currently 0.00045777) needs correcting.
- **Spindle** — a 0-24000 RPM bar showing commanded spindle speed (`spindle.0.speed-out-abs`, tapped
  from the same `spindle-speed-cmd` net used for the EL4032 output).

The panel's HAL pins (`pyvcp.*`) don't exist until the PyVCP panel has loaded, so their wiring lives in
`postgui.hal` (loaded via `[HAL] POSTGUI_HALFILE`), not `ethercat.hal`.

`panel.xml` was hand-written, not exported from a PyVCP designer, but its tag structure (`bar`, `number`,
`min_`/`max_`, `halpin`, `format`, `labelframe`) has been confirmed working against a real AXIS/PyVCP.
The red/negative-green/positive coloring when `min_` is negative is an assumption about the stock `bar`
widget's default fill behavior, not yet confirmed — if it doesn't render that way, this can be redone as
two stacked bars (green fed by `max(torque,0)`, red fed by `-min(torque,0)`) instead.

## Troubleshooting

- **"Machine On" refuses to enable, or the machine drops out on its own:** `iocontrol.0.emc-enable-in` is
  netted to `lcec.0.state-op` (`ethercat.hal`) — Machine On is refused, and an already-enabled machine is
  disabled like a fault, whenever the EtherCAT master hasn't got all slaves into OP state. Run
  `sudo ethercat slaves` to see which slave is stuck and in what state before assuming this is a config bug.
- **Slaves stuck in PREOP:** Use variable PDO mapping (0x1600/0x1A00) as in `ethercat-conf.xml`; avoid fixed PDOs.
- **Following error on enable:** Reduce acceleration; verify `CIA402_POS_SCALE` (10434.4 for X, 26214.4 for Z, 13107.2 for Y); check encoder resolution in drive params.
- **Wrong axis moves:** Confirm `trivkins coordinates=XZY` and that `lcec.0.x.*` / `lcec.0.z.*` / `lcec.0.y.*` are wired to `cia402.0` / `cia402.1` / `cia402.2` respectively — joint number follows EtherCAT bus position, not alphabetical axis order.
- **Z motor doesn't move:** Confirm `cia402.1` is wired to `lcec.0.z.*` and `joint.1`, and `HOME_SEQUENCE = 2` (Z homes last).
- **Y motor doesn't move:** Confirm `cia402.2` is wired to `lcec.0.y.*` and `joint.2`, and `HOME_SEQUENCE = 1` (Y homes second).
- **Beckhoff terminals not detected:** Confirm the full chain (EK1100 through EL4032) is wired in that order after the three servos, and that `sudo ethercat slaves` reports 15 devices.
- **"Failed to register PDO entry" / "PDO entry 0x7000:01 is not mapped":** A slave's `idx` in `ethercat-conf.xml` doesn't match its actual position column in `sudo ethercat slaves` — the master is trying to map one device's object dictionary onto a different physical device. Re-run `sudo ethercat slaves` and check every `idx` against its position.
- **No voltage at the VFD input:** Confirm `lcec.0.spindle.aout-0-value` is netted (`spindle-voltage-cmd` in `ethercat.hal`), that `lcec.0.spindle.aout-0-enable` is true (gated on `spindle.0.on` — the spindle must be commanded on, not just a nonzero S-word), and that a spindle speed has actually been commanded (`M3 S<rpm>`).
- **"Pin '...ao-0' does not exist":** The EL4032 uses lcec's `aout` class, not a flat `ao-N` pin — the real pins are `aout-0-value`, `-scale`, `-offset`, `-enable`, etc. (`halcmd show pin lcec.0.spindle` lists them all).
- **Machine-enable output doesn't energize:** Confirm `io.hal`'s `net machine-enable <= halui.machine.is-on => lcec.0.io-dout1.dout-0` loaded without error (requires `HALUI = halui` in `[HAL]`, already set) and that the machine is actually switched on in AXIS, not just estop-reset.

See `docs/kinematics.md` for pos-scale calculations and `docs/retrofit-plan.md` for the full retrofit roadmap.
