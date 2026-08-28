# Vantage 33M — X Gantry + Y Axis Bench Config

LinuxCNC configuration for bench-testing three StepperOnline A6 EtherCAT servos: two as a dual-motor X
gantry, plus one on the Y axis.

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

5. Turn Machine On, enable all joints, jog X and Y. Both X motors should move together; the Y motor
   moves independently.

## Files

| File | Purpose |
|------|---------|
| `vantage33m-bench.ini` | Machine parameters, joint limits, kinematics |
| `ethercat.hal` | lcec + cia402 wiring for 3 servos |
| `ethercat-conf.xml` | EtherCAT slave topology and PDO mapping |
| `panel.xml` | PyVCP panel, shown beside the preview: 3x servo torque bars + numeric readouts |
| `postgui.hal` | HAL wiring for `panel.xml`'s pins (loaded after the GUI starts, see below) |
| `tool.tbl` | Minimal tool table |

## Bench vs Machine Settings

| Setting | Bench | Full machine |
|---------|-------|--------------|
| Soft limits (X) | ±500 mm | 0–3780 mm |
| Soft limits (Y) | 0–500 mm | 0–1651 mm |
| Max velocity | 200 mm/s | 1215 mm/s (X) / 967 mm/s (Y) |
| Max acceleration | 500 mm/s² | 5000 mm/s² |
| Max jerk | 5000 mm/s³ | 50000 mm/s³ |
| NO_FORCE_HOMING | 1 | 0 |
| Joints | 3 (XXY) | 4 (XXYZ) |

This config uses LinuxCNC's jerk-limited (S-curve) trajectory planner: `MAX_JERK` is set at
`[TRAJ]`, each `[AXIS_x]`, and each `[JOINT_n]` (10× `MAX_ACCELERATION`, see
`docs/kinematics.md`). It requires a LinuxCNC build with S-curve TP support — if `MAX_JERK` isn't
recognized by your build, remove those lines to fall back to the trapezoidal planner.

## Servo Torque Panel

A PyVCP panel (`[DISPLAY] PYVCP = panel.xml`) renders in the pane beside the g-code preview — no
separate tab, no embedding setup. It shows, per servo (X left, X right, Y): a bar graph (0-12 Nm) and a
numeric readout, fed live from each drive's `actual-torque` PDO (6077h, CiA402-standard
0.1%-of-rated-torque units). 12 Nm is assumed to be the A6/SV660N's rated torque — verify against the
datasheet and adjust `postgui.hal`'s `*-torque-scale.gain` (currently 0.012 Nm/count) if it differs.

The panel's HAL pins (`pyvcp.*`) don't exist until the PyVCP panel has loaded, so their wiring lives in
`postgui.hal` (loaded via `[HAL] POSTGUI_HALFILE`), not `ethercat.hal`. Each torque signal fans out to
two pins — `pyvcp.<axis>-torque` (bar) and `pyvcp.<axis>-torque-num` (numeric readout) — since a PyVCP
widget's `halpin` name must be unique per widget.

`panel.xml` was hand-written, not exported from a PyVCP designer, and hasn't been loaded in a real
AXIS/PyVCP yet — if AXIS fails to parse it on startup, check the Integrator's Manual "PyVCP" chapter and
correct the tag names/nesting (`bar`, `number`, `min_`/`max_`, `halpin`, `format`, `labelframe`) from
there.

## Troubleshooting

- **Slaves stuck in PREOP:** Use variable PDO mapping (0x1600/0x1A00) as in `ethercat-conf.xml`; avoid fixed PDOs.
- **Following error on enable:** Reduce acceleration; verify `CIA402_POS_SCALE` (10434.4 for X, 13107.2 for Y); check encoder resolution in drive params.
- **Only one X motor moves:** Confirm `trivkins coordinates=XXY` and both X `cia402` instances (0, 1) are wired.
- **Gantry skew:** After homing, adjust `HOME_OFFSET` on joint 0 or 1 to square the gantry.
- **Y motor doesn't move:** Confirm `cia402.2` is wired to `lcec.0.y.*` and `joint.2`, and `HOME_SEQUENCE = 1` (Y homes after the X tandem pair).

See `docs/kinematics.md` for pos-scale calculations and `docs/retrofit-plan.md` for the full retrofit roadmap.
