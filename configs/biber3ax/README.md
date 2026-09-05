# Vantage 33M — Final 3-Axis Config (biber3ax)

LinuxCNC configuration for the full Week Vantage 33M retrofit: 4x StepperOnline A6 EtherCAT servos
(dual-motor X gantry, Y, Z) at full machine travel. Machine I/O (Beckhoff EK1100 + terminals) and the
spindle (Beckhoff EL4032) are wired but commented out until that hardware is on the bus.

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
   # Expected: four devices at position 0-3 (A6 / SV660N: x-left, x-right, y, z)
   ```

4. Copy or symlink this config directory to your LinuxCNC configs path, then start:
   ```bash
   linuxcnc /path/to/biber3ax.ini
   ```

5. Turn Machine On, home all joints (X tandem, then Y, then Z), jog each axis.

## Files

| File | Purpose |
|------|---------|
| `biber3ax.ini` | Machine parameters, joint limits, kinematics |
| `ethercat.hal` | lcec + cia402 wiring for the 4 servos, plus commented-out spindle (EL4032) wiring |
| `io.hal` | Template for the Beckhoff digital I/O terminals — fully commented out |
| `ethercat-conf.xml` | EtherCAT slave topology and PDO mapping — servos active, Beckhoff chain commented out |
| `panel.glade` | GladeVCP panel embedded as an AXIS tab: 4x servo torque bars + spindle speed bar |
| `postgui.hal` | HAL wiring for `panel.glade`'s pins (loaded after the GUI starts, see below) |
| `tool.tbl` | Minimal tool table |

## EtherCAT Bus Order

```
[0] x-left  [1] x-right  [2] y  [3] z    <- active (A6 servos)
[4] EK1100  [5] EL1808  [6] EL2808  [7] EL1808  [8] EL2808
[9] EL9110  [10] EL1808  [11] EL2808  [12] EL1808  [13] EL2808  [14] EL4032
                                                                    <- commented out
```

The EK1100 coupler and everything behind it are commented out in `ethercat-conf.xml`, `ethercat.hal`,
and `io.hal` — the coupler isn't on the test bench yet. Uncomment the three in lockstep once it's wired
in; do not enable only one file, or slave indices/pin names will mismatch.

## Machine I/O (Beckhoff, not yet connected)

- **EL1808 x4** — 8-channel digital input each (32 DI total). Net names in `io.hal` are placeholders
  (`io-din1-0` ... `io-din4-7`) — assign to actual signals (e-stop chain, door interlocks, limit
  switches, etc.) once wiring is known. See `docs/retrofit-plan.md` Phase 4.
- **EL2808 x4** — 8-channel digital output each (32 DO total). Same placeholder scheme (`io-dout1-0` ...
  `io-dout4-7`) — vacuum, dust collection, tool change, spindle enable, etc.
- **EL9110** — E-bus power supply feed terminal. No process data, no HAL pins; just refreshes bus power
  for the terminals downstream of it. Needed in the chain for power budget, not wired in HAL.
- **EL4032** — 2-channel ±10V analog output. Channel 0 drives the spindle (see below); channel 1 unused.

Pin names (`din-N`, `dout-N`, `ao-N`) follow the standard lcec Beckhoff terminal driver naming and are
unverified on this hardware — confirm with `halcmd show pin` once the coupler is connected.

## Spindle (Beckhoff EL4032, not yet connected)

Max speed 24000 RPM, controlled by a 0-10V analog signal on EL4032 channel 0. Wiring is in
`ethercat.hal` (commented out): `spindle.0.speed-out-abs` -> `scale` component (gain 10V/24000RPM =
0.00041667) -> `lcec.0.spindle.ao-0`. Uncomment alongside the `spindle` slave in `ethercat-conf.xml` and
the `[DISPLAY]` `*_SPINDLE_0_*` settings in `biber3ax.ini`.

## Servo Torque / Spindle Speed Panel

AXIS gets an extra "Servo Monitor" tab (`[DISPLAY] EMBED_TAB_*` in `biber3ax.ini`) showing:

- **4x torque bars, 0-12 Nm** — one per servo (X left, X right, Y, Z), fed live from each drive's
  `actual-torque` PDO (6077h, CiA402-standard 0.1%-of-rated-torque units). 12 Nm is assumed to be the
  A6/SV660N's rated torque — verify against the datasheet and adjust `postgui.hal`'s `*-torque-scale.gain`
  (currently 0.012 Nm/count) if it differs. This works today since the 4 servos are already active.
- **1x spindle speed bar, 0-24000 RPM** — shows *commanded* speed (`spindle.0.speed-out-abs`), not
  measured feedback — there's no spindle encoder in this design, only an open-loop 0-10V drive via the
  EL4032. It works without the Beckhoff coupler on the bus, since `spindle.0.speed-out-abs` is a core
  LinuxCNC motion pin, not hardware-dependent.

The panel's HAL pins (`torquemeters.*`) don't exist until the GladeVCP tab has loaded, so their wiring
lives in `postgui.hal` (loaded via `[HAL] POSTGUI_HALFILE`), not `ethercat.hal`.

`panel.glade` was hand-written, not exported from Glade, and hasn't been loaded against a real
`gladevcp` yet — if `gladevcp -c torquemeters panel.glade` errors on widget registration, open it in
Glade with the HAL widget catalog loaded and correct the `HAL_Bar` class name/properties from there.
Likewise double check `EMBED_TAB_LOCATION = notebook_mode` against the Integrator's Manual for your
LinuxCNC version — the valid notebook names can differ across releases.

## Full Machine Settings

| Setting | X | Y | Z |
|---------|---|---|---|
| Soft limits | 0–3780 mm | 0–1651 mm | -155–0 mm |
| Max velocity | 1215 mm/s | 967 mm/s | 250 mm/s |
| Max acceleration | 5000 mm/s² | 5000 mm/s² | 5000 mm/s² |
| Max jerk | 50000 mm/s³ | 50000 mm/s³ | 50000 mm/s³ |
| pos-scale | 10434.4 | 13107.2 | 26214.4 |
| Home direction | toward 0 (min) | toward 0 (min) | toward 0 (max, top) |

`NO_FORCE_HOMING = 0` — home switches must be wired and homing completed before jogging.

This config uses LinuxCNC's jerk-limited (S-curve) trajectory planner: `MAX_JERK` is set at
`[TRAJ]`, each `[AXIS_x]`, and each `[JOINT_n]` (10× the axis's `MAX_ACCELERATION`, see
`docs/kinematics.md`). It requires a LinuxCNC build with S-curve TP support — if `MAX_JERK` isn't
recognized by your build, remove those lines to fall back to the trapezoidal planner.

## Troubleshooting

- **"Machine On" refuses to enable, or the machine drops out on its own:** `iocontrol.0.emc-enable-in` is
  netted to `lcec.0.state-op` (`ethercat.hal`) — Machine On is refused, and an already-enabled machine is
  disabled like a fault, whenever the EtherCAT master hasn't got all slaves into OP state. Run
  `sudo ethercat slaves` to see which slave is stuck and in what state before assuming this is a config bug.
- **Slaves stuck in PREOP:** Use variable PDO mapping (0x1600/0x1A00) as in `ethercat-conf.xml`; avoid fixed PDOs.
- **Following error on enable:** Reduce acceleration; verify `CIA402_POS_SCALE` per axis; check encoder resolution in drive params.
- **Only one X motor moves:** Confirm `trivkins coordinates=XXYZ` and both X `cia402` instances (0, 1) are wired.
- **Gantry skew:** After homing, adjust `HOME_OFFSET` on joint 0 or 1 to square the gantry.
- **Z homes the wrong direction:** Z's home switch is at the top (Z=0); `HOME_SEARCH_VEL` is positive, unlike X/Y.
- **Beckhoff terminals not detected:** Confirm the EK1100 and everything after it are uncommented in
  `ethercat-conf.xml`, and that the slave count matches what `sudo ethercat slaves` reports.

See `docs/kinematics.md` for pos-scale calculations and `docs/retrofit-plan.md` for the full retrofit roadmap.
