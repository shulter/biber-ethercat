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
   # 2x EL2808, EL1018, EL9110, 2x EL2808, EL4032). idx in ethercat-conf.xml
   # must match this position column exactly, or PDO registration fails
   # ("Failed to register PDO entry").
   ```

4. Copy or symlink this config directory to your LinuxCNC configs path, then start:
   ```bash
   linuxcnc /path/to/biber3ax.ini
   ```

5. Turn Machine On, home all joints (Z, then X tandem, then Y), jog each axis. Confirm the first
   EL2808's channel 0 output energizes (machine-enable indicator). Command a spindle speed
   (`M3 S<rpm>`) and verify the 0-10V output reaches the VFD.

## Files

| File | Purpose |
|------|---------|
| `biber3ax.ini` | Machine parameters, joint limits, kinematics, spindle display range |
| `ethercat.hal` | lcec + cia402 wiring for the 4 servos, plus EL4032 spindle analog-out wiring |
| `io.hal` | Beckhoff digital I/O wiring: machine-enable lamp, Z brake, limit/home switches, HSK tool release interlock |
| `remap/m250.ngc`, `remap/m251.ngc` | Remapped M250 (release tool, with safety checks) / M251 (clamp tool) |
| `remap/m200.ngc`, `remap/m201.ngc` | Remapped M200 (dust hood down) / M201 (dust hood up) |
| `remap/m230.ngc`, `remap/m231.ngc` | Remapped M230 (reg pins down) / M231 (reg pins up) |
| `remap/m240.ngc` … `remap/m243.ngc` | Remapped M240 (vacuum off) / M241 (both zones) / M242 (left zone) / M243 (right zone) |
| `ethercat-conf.xml` | EtherCAT slave topology and PDO mapping (servos, full Beckhoff chain) |
| `panel.xml` | PyVCP panel, shown beside the preview: 4x servo torque + speed bars, spindle speed bar |
| `postgui.hal` | HAL wiring for `panel.xml`'s pins (loaded after the GUI starts, see below) |
| `tool.tbl` | Minimal tool table |

## EtherCAT Bus Order

```
[0] x-left  [1] x-right  [2] y  [3] z                          <- A6 servos
[4] EK1100  [5] EL1808  [6] EL1808  [7] EL1808  [8] EL1808
[9] EL2808  [10] EL2808  [11] EL1018 (limit switches)  [12] EL9110
[13] EL2808  [14] EL2808  [15] EL4032 (spindle)
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
  (`io-dout1-2` ... `io-dout4-7`); see `io.hal` for the outputs that are actively wired. Among them:
  - **`io-dout1.dout-0`** drives a machine-enable indicator (lamp/relay) from `halui.machine.is-on` —
    energized whenever LinuxCNC is switched on. A status output, not the safety interlock chain
    feeding `iocontrol.0.emc-enable-in`.
  - **`io-dout1.dout-1`** is the Z axis holding brake (TRUE = released). It releases 1.3 s after
    Machine On (`z-brake-delay`, a `timedelay` on Z's `amp-enable-out`) so the servo is powered and
    holding first, and engages immediately when the machine is switched off or faults.
  - **`io-dout1.dout-3`** / **`io-dout1.dout-2`** are the VFD output contactors for the HSK milling
    spindle / the boring aggregate (one KEB VFD feeds either motor). For now the milling spindle
    contactor is closed whenever the machine is on (`machine-enable`) and the boring aggregate
    contactor stays open. Planned tool-number mapping for the tool change routine: T1–T100 milling
    spindle, T101–T107 vertical boring spindles 1–7, T201–T204 horizontal boring head (both boring
    heads on the boring aggregate contactor).
  - **`io-dout1.dout-6`** / **`io-dout1.dout-5`** drive KEB inputs I4 / I1, which select the VFD
    parameter set: I4 = set 5 (HSK spindle with milling tool, 400 Hz), I1 = set 2 (boring aggregate,
    50 Hz). With no set input active the KEB stays in its stop set 0. For now I4 follows the HSK
    contactor (on with `machine-enable`, off 10 s later) and I1 stays off.
- **EL9110** — E-bus power supply feed terminal with diagnostics, bus position 12. This lcec build
  doesn't know its type, so it's declared as `type="generic"` with its real identity (vid `00000002`,
  pid `23963052`, from `ethercat slaves -p 12 -v`) and its one PDO mapped to
  `lcec.0.io-power.power-ok`. It must be declared: left undeclared, it stays in PREOP and keeps
  `lcec.0.state-op` false, which blocks e-stop reset (F1). Declaring it generic *without* vid/pid
  breaks the master's PDO registration (`Failed to register PDO entry`).

Pin names (`din-N`, `dout-N`) follow the standard lcec Beckhoff terminal driver naming — confirm with
`halcmd show pin` once running.

## Spindle (Beckhoff EL4032 → VFD)

Max speed 24000 RPM, controlled by a 0-10V analog signal on EL4032 channel 0 (channel 1 unused).
Wiring is in `ethercat.hal`: `spindle.0.speed-out-abs` -> `spindle-scale` (gain 1/24000 =
0.0000416667) -> `lcec.0.spindle.aout-0-value`. `spindle.0.on` gates `lcec.0.spindle.aout-0-enable`
(the terminal's output stays disabled/0V unless the spindle is actually commanded on).
`[DISPLAY]` `*_SPINDLE_0_*` settings in `biber3ax.ini` set the speed range (0-24000 RPM) and
override limits (50-100%).

**`aout-0-value` is a fraction of full scale, not volts:** lcec's aout class turns it into a duty cycle
(`value / aout-0-scale + offset`, default scale 1), clamped to `aout-0-min-dc`/`max-dc` = −1…+1, where
+1.0 = +10 V. A volts-based gain (10 V / 24000 rpm) made the spindle reach full speed at 2400 rpm
commanded; the gain is therefore 1/24000. Fine-tune `spindle-scale.gain` if the measured speed at a
known S-word is still off (e.g. VFD analog-input calibration).

All `scale` instances (spindle and the panel's torque/speed scaling) are loaded in one `loadrt scale` call in
`ethercat.hal` — the component can only be loaded once per HAL session, so `postgui.hal` only
`setp`s/`net`s them.

## HSK Tool Release (Drawbar)

`io-dout3.dout-1` pushes the HSK drawbar and releases the tool. It is driven by an interlock in
`io.hal` (`lut5` `drawbar-release`):

```
release = (pendant button io-din1-0  OR  M250 request)
          AND spindle not turning (io-din2-4, back-EMF)  AND  NOT spindle.0.on
```

- **Pendant button** (`io-din1.din-0`): the tool is released only while the button is held.
- **M250** (`remap/m250.ngc`): checks that the spindle is off (`spindle.0.on` via
  `motion.digital-in-01`) and not turning (`io-din2.din-4` via `motion.digital-in-00`), aborting the
  program with a message if either fails, then sets the release request (`M64 P0` →
  `motion.digital-out-00`). The request stays set until **M251** (`M65 P0`) clamps the tool again.
- The HAL interlock enforces the same conditions independently, so the release drops immediately if the
  spindle is switched on or starts turning, whichever way it was requested.

**Spindle start interlock** (`io.hal`, `lut5` `spindle-inhibit` / `spindle-tool-fault`): the spindle
may only run with the tool clamped, i.e. `io-din2.din-2` (clamped) TRUE, `io-din2.din-3` (released)
FALSE and the drawbar release output off. Otherwise `spindle.0.inhibit` holds the spindle speed at 0,
and commanding the spindle on (M3/M4 or the AXIS spindle button) raises `spindle.0.amp-fault-in`, which
switches the machine off and aborts a running program. Both switches have to agree, so a stuck or
broken drawbar switch also blocks the spindle.

Polarity: `io-din2.din-4` reads TRUE while the spindle stands still (checked on the running machine).
With the tool clamped, `io-din2.din-2` reads TRUE and `io-din2.din-3` FALSE.
The pendant button reads FALSE when not pressed, so it's treated as normally-open (TRUE while pressed).

## Dust Hood

The dust hood is moved by two pneumatic solenoids on EL2808 #3: `io-dout3.dout-3` pushes it down,
`io-dout3.dout-2` pushes it up. The hood position is held in a HAL `flipflop` (`dust-hood`, in
`io.hal`) whose `out` drives the down solenoid and `out-not` the up solenoid, so exactly one is always
energised — the hood is pushed **up** as soon as HAL starts.

- **M200** (`remap/m200.ngc`) lowers the hood, **M201** (`remap/m201.ngc`) raises it. Each pulses a
  motion digital output for 50 ms (`M64`, `G4 P0.05`, `M65`) onto the flipflop's `set`
  (`motion.digital-out-01`) or `reset` (`motion.digital-out-02`).
- **Panel button** "Hood Up / Down" (`pyvcp.dust-hood-toggle`, wired in `postgui.hal`) toggles the
  hood on each press. It's pure HAL, so it works at any time, including while a program runs. The LED
  next to it is lit while the hood is down.

## Reg Pins

All reg pins (Y0, Y1, rechts, links) are raised by one output, `io-dout3.dout-0` (TRUE = up / active).
**M231** (`remap/m231.ngc`) raises them, **M230** (`remap/m230.ngc`) lowers them again, via
`motion.digital-out-03` (`M64 P3` / `M65 P3`). They stay where they were last put, and are down when
LinuxCNC starts.

## Vacuum Table

The vacuum pump contactor is `io-dout1.dout-4`; the left and right vacuum ports are opened by
`io-dout2.dout-4` and `io-dout2.dout-6`, and closed by separate valves on `io-dout2.dout-5` (left) and
`io-dout2.dout-7` (right). Each close valve is driven by the inverse of its open output (HAL `not`
components `vacuum-left-close` / `vacuum-right-close` in `io.hal`), so exactly one valve of each pair is
energised and both ports are closed as soon as HAL starts. They're driven through `motion.digital-out-04` (pump), `-05` (left)
and `-06` (right) with `M64`/`M65`, which is why `motmod` is loaded with `num_dio=8` in `ethercat.hal`.

| M-code | Pump | Left port | Right port |
|--------|------|-----------|------------|
| **M241** | on | open | open |
| **M242** | on | open | closed |
| **M243** | on | closed | open |
| **M240** | off | closed | closed |

The state holds until the next of these M-codes; at LinuxCNC start everything is off/closed.

## Servo Torque / Speed Panel

A PyVCP panel (`[DISPLAY] PYVCP = panel.xml` in `biber3ax.ini`) renders in the pane beside the g-code
preview — no separate tab, no embedding setup. Layout is the one from the benchtest-servo config,
extended to all 4 servos (X left, X right, Y, Z):

- **Servo Torque** — bidirectional bar per servo (-11 to 0 to +11 Nm, covering the 11.13 Nm peak
  torque), fed live from each drive's `actual-torque` PDO (6077h, 0.1% of rated torque per count). Rated
  torque is 3.18 Nm, so `postgui.hal`'s `*-torque-scale.gain` is 3.18 / 1000 = 0.00318 Nm/count.
- **Servo Speed** — absolute motor RPM per servo (0-6000), from each drive's `actual-velocity` PDO (606Ch),
  assumed to be in encoder counts/s: RPM = counts/s × 60/131072 (`*-vel-scale.gain` = 0.00045777). Verify
  against the drive parameters.
- **Spindle** — *commanded* speed bar, 0-24000 RPM (`spindle.0.speed-out-abs`), not measured feedback —
  there's no spindle encoder in this design, only an open-loop 0-10V drive via the EL4032. Below it a
  green "turning" LED driven by the HSK spindle's back-EMF standstill input (`io-din2-4`, inverted), so
  it shows actual rotation, including coast-down after `M5`.
- **Dust Hood** — up/down toggle button and a "down" LED (see [Dust Hood](#dust-hood)).

The panel's HAL pins (`pyvcp.*`) don't exist until the PyVCP panel has loaded, so their wiring lives in
`postgui.hal` (loaded via `[HAL] POSTGUI_HALFILE`), not `ethercat.hal`.

The red/negative-green/positive coloring of the torque bars is an assumption about the stock `bar`
widget's fill behavior when `min_` is negative — if it doesn't render that way, this can be redone as
two stacked bars (green fed by `max(torque,0)`, red fed by `-min(torque,0)`) instead.

## Full Machine Settings

| Setting | X | Y | Z |
|---------|---|---|---|
| Soft limits | 0–3780 mm | 0–1651 mm | -155–0 mm |
| Max velocity | 1215 mm/s | 967 mm/s | 250 mm/s |
| Max acceleration | 2000 mm/s² | 2000 mm/s² | 2000 mm/s² |
| Max jerk | 20000 mm/s³ | 20000 mm/s³ | 20000 mm/s³ |
| pos-scale | −10434.4 (x-left), 10434.4 (x-right, mirrored) | 13107.2 | 26214.4 |
| Home direction | + (onto positive limit) | − (onto negative limit, Y0 end) | + (onto positive limit, top) |
| Limit/home switches (EL1018) | `din-1` (+) | `din-2` (−) | `din-3` (+), `din-4` (−) |
| HOME_OFFSET / HOME | 3782 / see `[JOINT_0/1] HOME` | −2 / 200 | 1 / 0 |
| HOME_SEQUENCE | −2 (tandem) | 3 (last) | 1 (first) |

Each axis homes onto its positive limit switch, which doubles as the home switch (wired in `io.hal`,
see `docs/kinematics.md` "Homing / Limit Switches"). The X switch is normally-closed (wired via
lcec's inverted `din-1-not` pin); the Y, Z+ and Z− switches are normally-open (netted directly). `HOME_OFFSET` values
are placeholders until the real trip points are measured.

`NO_FORCE_HOMING = 1` — jogging/MDI allowed without homing. Set it to `0` once homing is verified.

This config uses LinuxCNC's jerk-limited (S-curve) trajectory planner: `MAX_JERK` is set at
`[TRAJ]`, each `[AXIS_x]`, and each `[JOINT_n]` (10× the axis's `MAX_ACCELERATION`, see
`docs/kinematics.md`). It requires a LinuxCNC build with S-curve TP support — if `MAX_JERK` isn't
recognized by your build, remove those lines to fall back to the trapezoidal planner.

## Troubleshooting

- **E-stop loop:** `iocontrol.0.emc-enable-in` = `iocontrol.0.user-enable-out` (F1) AND
  `lcec.0.state-op` (`and2` `estop-chain` in `ethercat.hal`, net `estop-ok`). In LinuxCNC 2.9 the e-stop
  state *is* `!emc-enable-in` and F1 only toggles `user-enable-out`, so `user-enable-out` must be in this
  loop — wiring `emc-enable-in` from `state-op` alone leaves LinuxCNC permanently in ESTOP_RESET with F1
  dead. This is only LinuxCNC's internal e-stop state — the physical emergency stop circuit is
  hardware-only and not driven by LinuxCNC.
- **E-stop won't reset, or the machine drops into e-stop on its own:** `estop-ok` is false because
  `lcec.0.state-op` is false — at least one slave isn't in OP. While LinuxCNC is running,
  `ethercat slaves` shows which one; any slave left out of `ethercat-conf.xml` stays in PREOP and
  causes this.
- **"Joint N amplifier fault" about 1 s after Machine On (F2):** that drive didn't reach CiA402
  "operation enabled" — most likely its HV (main circuit) supply is off. The A6 stays in OP on
  EtherCAT and raises no drive fault in that case, so `ethercat.hal` treats "enabled but not
  operation-enabled for > 1 s" as an amp fault (`<joint>-not-op` / `-not-op-delay` / `-fault-or`).
  `halcmd show pin cia402.N.stat-op-enabled` and `cia402.N.statusword` show the drive's state. If a
  drive legitimately needs longer to enable, raise `<joint>-not-op-delay.on-delay`.
- **"Spindle amplifier fault" when starting the spindle, or the spindle won't turn:** the tool isn't
  seen as clamped. Check `halcmd show pin lcec.0.io-din2` — `din-2` (clamped) must be TRUE and `din-3`
  (released) FALSE — and that the drawbar release output (`lcec.0.io-dout3.dout-1`) is off (M251).
- **Slaves stuck in PREOP:** Use variable PDO mapping (0x1600/0x1A00) as in `ethercat-conf.xml`; avoid fixed PDOs.
- **Following error on enable:** Reduce acceleration; verify `CIA402_POS_SCALE` per axis; check encoder resolution in drive params.
- **Only one X motor moves:** Confirm `trivkins coordinates=XXYZ` and both X `cia402` instances (0, 1) are wired.
- **Gantry skew:** After homing, adjust `HOME_OFFSET` on joint 0 or 1 to square the gantry.
- **Joint limit error as soon as the machine is on, with no axis on a switch:** a switch's polarity
  doesn't match `io.hal`. While clear, `halcmd show pin lcec.0.io-din5` should read din-1 TRUE (X, NC)
  and din-2..din-4 FALSE (Y/Z, NO). For the switch that differs, swap
  between `lcec.0.io-din5.din-N` and its inverted `din-N-not` pin in `io.hal`.
- **Homing runs into the switch without stopping / "limit switch" error during homing:** confirm
  `HOME_IGNORE_LIMITS = YES` on every joint and that the switch's `*-pos-lim` net reaches the joint's
  `home-sw-in` (`halcmd show sig x-pos-lim`).
- **Beckhoff terminals not detected:** Confirm the full chain (EK1100 through EL4032) is wired in the
  order above after the four servos, and that `sudo ethercat slaves` reports 16 devices.
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
