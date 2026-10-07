# Vantage 33M — Final 3-Axis Config (biber3ax)

LinuxCNC configuration for the full Week Vantage 33M retrofit: 4x StepperOnline A6 EtherCAT servos
(dual-motor X gantry, Y, Z) at full machine travel, plus the Beckhoff EK1100 I/O terminal chain
(40 DI / 32 DO) and an EL4032 analog output driving the spindle VFD's 0-10V speed input. The bus layout
is taken from `benchtest-io`, where it was verified against the real hardware.

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
   # Expected: 16 devices — four A6/SV660N servos at position 0-3 (x-left,
   # x-right, y, z), then the Beckhoff chain at 4-15 (EK1100, 4x EL1808,
   # 2x EL2808, EL9110, 2x EL2808, EL4032, EL1018). idx in ethercat-conf.xml
   # must match this position column exactly, or PDO registration fails
   # ("Failed to register PDO entry").
   ```

4. Copy or symlink this config directory to your LinuxCNC configs path, then start:
   ```bash
   linuxcnc /path/to/biber3ax.ini
   ```

5. Turn Machine On, home all joints (X tandem, then Y, then Z), jog each axis. Confirm the first
   EL2808's channel 0 output energizes (machine-enable indicator). Command a spindle speed
   (`M3 S<rpm>`) and verify the 0-10V output reaches the VFD.

## Files

| File | Purpose |
|------|---------|
| `biber3ax.ini` | Machine parameters, joint limits, kinematics, spindle display range |
| `ethercat.hal` | lcec + cia402 wiring for the 4 servos, plus EL4032 spindle analog-out wiring |
| `io.hal` | Beckhoff digital I/O terminal wiring (machine-enable output; rest are placeholders) |
| `ethercat-conf.xml` | EtherCAT slave topology and PDO mapping (servos, full Beckhoff chain) |
| `panel.glade` | GladeVCP panel embedded as an AXIS tab: 4x servo torque bars + spindle speed bar |
| `postgui.hal` | HAL wiring for `panel.glade`'s pins (loaded after the GUI starts, see below) |
| `tool.tbl` | Minimal tool table |

## EtherCAT Bus Order

```
[0] x-left  [1] x-right  [2] y  [3] z                          <- A6 servos
[4] EK1100  [5] EL1808  [6] EL1808  [7] EL1808  [8] EL1808
[9] EL2808  [10] EL2808  [11] EL9110  [12] EL2808  [13] EL2808
[14] EL4032 (spindle)  [15] EL1018
```

`idx` in `ethercat-conf.xml` is the real bus position. **Every** slave on the bus must be declared —
`lcec.0.state-op` (which gates `iocontrol.0.emc-enable-in`, and thus e-stop reset/F1) is only true when
all slaves are in OP, and the master leaves undeclared slaves in PREOP.

## Machine I/O (Beckhoff)

- **EL1808 x4** — 8-channel digital input each (32 DI total, 3ms filter). Net names in `io.hal` are
  placeholders (`io-din1-0` ... `io-din4-7`), all commented out, annotated with the signal each input is
  known to carry (pendant, VFD status, HSK drawbar, drill aggregates, vacuum/air, dust hood) — enable and
  rename as each signal is integrated. See `docs/retrofit-plan.md` Phase 4.
- **EL1018** — 8-channel digital input, 10us fast response (no input filtering) — for signals that need
  to be caught quickly, e.g. the tool height probe on `din-0`. Placeholders `io-din5-0` ... `io-din5-7`.
- **EL2808 x4** — 8-channel digital output each (32 DO total). Same placeholder scheme
  (`io-dout1-1` ... `io-dout4-7`), except **`io-dout1.dout-0`**, which is actively wired: it drives a
  machine-enable indicator (lamp/relay) from `halui.machine.is-on` — energized whenever LinuxCNC is
  switched on. This is a status output, not the safety interlock chain feeding
  `iocontrol.0.emc-enable-in`.
- **EL9110** — E-bus power supply feed terminal with diagnostics, bus position 11. This lcec build
  doesn't know its type, so it's declared as `type="generic"` with its real identity (vid `00000002`,
  pid `23963052`, from `ethercat slaves -p 11 -v`) and its one PDO mapped to
  `lcec.0.io-power.power-ok`. It must be declared: left undeclared, it stays in PREOP and keeps
  `lcec.0.state-op` false, which blocks e-stop reset (F1). Declaring it generic *without* vid/pid
  breaks the master's PDO registration (`Failed to register PDO entry`).

Pin names (`din-N`, `dout-N`) follow the standard lcec Beckhoff terminal driver naming — confirm with
`halcmd show pin` once running.

## Spindle (Beckhoff EL4032 → VFD)

Max speed 24000 RPM, controlled by a 0-10V analog signal on EL4032 channel 0 (channel 1 unused).
Wiring is in `ethercat.hal`: `spindle.0.speed-out-abs` -> `spindle-scale` (gain 10V/24000RPM =
0.00041667) -> `lcec.0.spindle.aout-0-value`. `spindle.0.on` gates `lcec.0.spindle.aout-0-enable`
(the terminal's output stays disabled/0V unless the spindle is actually commanded on).
`[DISPLAY]` `*_SPINDLE_0_*` settings in `biber3ax.ini` set the speed range (0-24000 RPM) and
override limits (50-100%).

**Not yet verified on hardware:** `spindle-scale`'s gain assumes `aout-0-value` takes volts directly
with the terminal's own `aout-0-scale`/`-offset` left at their defaults. Before trusting the VFD sees
the right speed, command a known RPM and measure the voltage at the EL4032's output terminals; if it's
off, adjust `spindle-scale.gain` in `ethercat.hal` or set `lcec.0.spindle.aout-0-scale`/`-offset`.

All `scale` instances (spindle and the panel's torque scaling) are loaded in one `loadrt scale` call in
`ethercat.hal` — the component can only be loaded once per HAL session, so `postgui.hal` only
`setp`s/`net`s them.

## Servo Torque / Spindle Speed Panel

AXIS gets an extra "Servo Monitor" tab (`[DISPLAY] EMBED_TAB_*` in `biber3ax.ini`) showing:

- **4x torque bars, 0-12 Nm** — one per servo (X left, X right, Y, Z), fed live from each drive's
  `actual-torque` PDO (6077h, CiA402-standard 0.1%-of-rated-torque units). 12 Nm is assumed to be the
  A6/SV660N's rated torque — verify against the datasheet and adjust `postgui.hal`'s `*-torque-scale.gain`
  (currently 0.012 Nm/count) if it differs. This works today since the 4 servos are already active.
- **1x spindle speed bar, 0-24000 RPM** — shows *commanded* speed (`spindle.0.speed-out-abs`), not
  measured feedback — there's no spindle encoder in this design, only an open-loop 0-10V drive via the
  EL4032.

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
- **E-stop reset (F1) greyed out / does nothing:** `iocontrol.0.emc-enable-in` is false because
  `lcec.0.state-op` is false — at least one slave isn't in OP. While LinuxCNC is running,
  `ethercat slaves` shows which one; any slave left out of `ethercat-conf.xml` stays in PREOP and
  causes this.
- **Slaves stuck in PREOP:** Use variable PDO mapping (0x1600/0x1A00) as in `ethercat-conf.xml`; avoid fixed PDOs.
- **Following error on enable:** Reduce acceleration; verify `CIA402_POS_SCALE` per axis; check encoder resolution in drive params.
- **Only one X motor moves:** Confirm `trivkins coordinates=XXYZ` and both X `cia402` instances (0, 1) are wired.
- **Gantry skew:** After homing, adjust `HOME_OFFSET` on joint 0 or 1 to square the gantry.
- **Z homes the wrong direction:** Z's home switch is at the top (Z=0); `HOME_SEARCH_VEL` is positive, unlike X/Y.
- **Beckhoff terminals not detected:** Confirm the full chain (EK1100 through EL1018) is wired in that
  order after the four servos, and that `sudo ethercat slaves` reports 16 devices.
- **"Failed to register PDO entry" / "PDO entry 0x7000:01 is not mapped":** A slave's `idx` in
  `ethercat-conf.xml` doesn't match its actual position column in `sudo ethercat slaves`. Re-run
  `sudo ethercat slaves` and check every `idx` against its position.
- **No voltage at the VFD input:** Confirm `lcec.0.spindle.aout-0-enable` is true (gated on
  `spindle.0.on` — the spindle must be commanded on, not just a nonzero S-word) and that a spindle speed
  has actually been commanded (`M3 S<rpm>`).
- **"Pin '...ao-0' does not exist":** The EL4032 uses lcec's `aout` class — the real pins are
  `aout-0-value`, `-scale`, `-offset`, `-enable`, etc. (`halcmd show pin lcec.0.spindle`).
- **Machine-enable output doesn't energize:** Confirm `io.hal`'s `net machine-enable` loaded without
  error (requires `HALUI = halui` in `[HAL]`, already set) and that the machine is switched on in AXIS.

See `docs/kinematics.md` for pos-scale calculations and `docs/retrofit-plan.md` for the full retrofit roadmap.
