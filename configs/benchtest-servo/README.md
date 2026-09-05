# Vantage 33M — X / Y / Z Bench Config

LinuxCNC configuration for bench-testing three StepperOnline A6 EtherCAT servos, one per axis
(X, Y, Z) — no gantry pairing. All three joints move independently.

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
   # Expected: three devices at position 0, 1, and 2 (A6 / SV660N)
   ```

4. Copy or symlink this config directory to your LinuxCNC configs path, then start:
   ```bash
   linuxcnc /path/to/vantage33m-bench.ini
   ```

5. Turn Machine On, enable all joints, jog X, Y, and Z. Each axis moves its own motor
   independently.

## Files

| File | Purpose |
|------|---------|
| `vantage33m-bench.ini` | Machine parameters, joint limits, kinematics |
| `ethercat.hal` | lcec + cia402 wiring for 3 servos |
| `ethercat-conf.xml` | EtherCAT slave topology and PDO mapping |
| `panel.xml` | PyVCP panel, shown beside the preview: 3x servo torque bars + numeric readouts |
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

## Servo Torque / Speed Panel

A PyVCP panel (`[DISPLAY] PYVCP = panel.xml`) renders in the pane beside the g-code preview — no
separate tab, no embedding setup. It has two groups:

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

The panel's HAL pins (`pyvcp.*`) don't exist until the PyVCP panel has loaded, so their wiring lives in
`postgui.hal` (loaded via `[HAL] POSTGUI_HALFILE`), not `ethercat.hal`.

`panel.xml` was hand-written, not exported from a PyVCP designer, but its tag structure (`bar`, `number`,
`min_`/`max_`, `halpin`, `format`, `labelframe`) has been confirmed working against a real AXIS/PyVCP.
The red/negative-green/positive coloring when `min_` is negative is an assumption about the stock `bar`
widget's default fill behavior, not yet confirmed — if it doesn't render that way, this can be redone as
two stacked bars (green fed by `max(torque,0)`, red fed by `-min(torque,0)`) instead.

## Troubleshooting

- **Slaves stuck in PREOP:** Use variable PDO mapping (0x1600/0x1A00) as in `ethercat-conf.xml`; avoid fixed PDOs.
- **Following error on enable:** Reduce acceleration; verify `CIA402_POS_SCALE` (10434.4 for X, 26214.4 for Z, 13107.2 for Y); check encoder resolution in drive params.
- **Wrong axis moves:** Confirm `trivkins coordinates=XZY` and that `lcec.0.x.*` / `lcec.0.z.*` / `lcec.0.y.*` are wired to `cia402.0` / `cia402.1` / `cia402.2` respectively — joint number follows EtherCAT bus position, not alphabetical axis order.
- **Z motor doesn't move:** Confirm `cia402.1` is wired to `lcec.0.z.*` and `joint.1`, and `HOME_SEQUENCE = 2` (Z homes last).
- **Y motor doesn't move:** Confirm `cia402.2` is wired to `lcec.0.y.*` and `joint.2`, and `HOME_SEQUENCE = 1` (Y homes second).

See `docs/kinematics.md` for pos-scale calculations and `docs/retrofit-plan.md` for the full retrofit roadmap.
