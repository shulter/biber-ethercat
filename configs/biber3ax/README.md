# biber3ax — Weeke Vantage 33M

LinuxCNC config: 4× A6 EtherCAT servos (X gantry, Y, Z), Beckhoff I/O, KEB VFD spindle via EL4032.
Limits, speeds and homing values live in `biber3ax.ini`; scaling math in `docs/kinematics.md`.

## Start

```bash
sudo ethercat slaves      # 16 devices, all OP once LinuxCNC runs
linuxcnc biber3ax.ini
```
F1 (e-stop reset) → F2 (machine on) → home (Z, X tandem, Y).

New install: `cp linuxcnc.var.example linuxcnc.var` (untracked; #3990 only persists if it's listed there).

### Absolute encoders (`biber3ax-abs.sh`)

`./biber3ax-abs.sh` (instead of `linuxcnc biber3ax.ini`, LinuxCNC 2.9 or 2.10): the first Machine On homes each joint once
(no motion, no Home All, `abs-home.hal`), using the drives' battery-backed absolute position. Otherwise identical: it
regenerates `biber3ax-abs.ini.gen` from `biber3ax.ini` and the offsets in `biber3ax-abs.ini` on every start. Setup, once:

1. A6 drives: absolute encoder mode on, battery fitted, multi-turn data reset (drive manual).
2. Home with `biber3ax.ini`, then `./biber3ax-abs.sh measure` → offsets into `[ABS_ENCODER]`.

Re-measure after a battery/encoder alarm or multi-turn reset — otherwise every position is wrong.

## Files

| File | Content |
|------|---------|
| `biber3ax.ini` | Machine, joints, homing, remaps |
| `compat.tcl` | Loads the components LinuxCNC 2.10 renamed (2.9 and 2.10) |
| `ethercat-conf.xml` | Bus layout / PDO mapping |
| `ethercat.hal` | Servos, e-stop loop, drive-ready check, spindle analog out |
| `io.hal` | Beckhoff I/O and interlocks |
| `postgui.hal`, `panel.xml` | PyVCP panel |
| `machine-stats.py` | Drive error messages, job log, tool life, service counter |
| `remap/*.ngc` | M-codes below, `probe_*.ngc` probe cycles |
| `probe-tab.xml` | AXIS Probe tab (buttons -> `[HALUI]MDI_COMMAND`, `postgui.hal`) |

## Bus

```
[0] x-left  [1] x-right  [2] y  [3] z                     A6 servos
[4] EK1100  [5-8] EL1808 ×4  [9-10] EL2808 ×2
[11] EL1018  [12] EL9110  [13-14] EL2808 ×2  [15] EL4032
```
`idx` = bus position. Every slave must be declared: `lcec.0.state-op` needs all slaves in OP.
EL9110 is declared generic (vid `00000002`, pid `23963052`) — this lcec doesn't know the type.

## Safety logic

- **E-stop:** `emc-enable-in = user-enable-out (F1) AND lcec.0.state-op`. Physical e-stop is hardware-only.
- **Drive ready:** joint amp fault if a drive isn't CiA402 "operation enabled" within its
  `<joint>-not-op-delay.on-delay` after F2 (e.g. HV off).
- **Z brake** (`io-dout1.dout-1`): released 1.3 s after F2, engaged immediately on off/fault.

## Axes

- X: two mirrored motors, `CIA402_POS_SCALE` −/+ on joints 0/1, tandem homing.
- Homing switches (EL1018): X+ `din-1` (NC), Y− `din-2` (NO), Z+ `din-3` (NO); Z− limit `din-4` (NO).
  X and Z home +, Y homes −. `HOME_OFFSET` = switch position.
- `NO_FORCE_HOMING = 1` for now.

## Spindle

- EL4032 ch0: `spindle-scale` gain 1/24000 → `aout-0-value` (fraction, 1.0 = 10 V = 24000 rpm).
- VFD run: `io-dout2.dout-2` CW / `dout-3` CCW, gated by the clamp interlock.
- Contactors: `io-dout1.dout-3` HSK spindle, `dout-2` boring aggregate — the one selected by M6
  (`motion.digital-out-10`) is on with the machine, 10 s off-delay. KEB parameter set follows the
  contactor: `dout-6` = I4 (set 5, HSK), `dout-5` = I1 (set 2, boring).
- Tool numbers: T1–100 HSK (T1–T20 in the rack, T17 = dust seal dummy, `DUMMY_TOOL`), T101–107 vertical boring 1–7,
  T201/202 X horizontal aggregate, T203/204 Y horizontal aggregate.

## HSK tool release

- Release output `io-dout3.dout-1` = ((pendant `io-din1.din-0` AND no program) OR M250) AND not turning
  (`io-din2.din-4`) AND spindle off. "No program" = `halui.program.is-idle`: running, paused or MDI blocks it.
- `din2-2` = tool present and clamped; drawbar up without a tool: `din2-2` and `din2-3` both FALSE.
- Spindle start needs a tool clamped: `din2-2` TRUE, `din2-3` FALSE, release off. Else
  `spindle.0.inhibit` + spindle amp fault.

## Tool changer (M6)

Linear rack, 20 pockets along Y at the X− end. Tool number = pocket number (T1–T20, T0 = unload).
Pocket positions and approach offsets: `toolchanger.ini` (`#INCLUDE`d into `biber3ax.ini`).

- **Work area:** X ≥ `[AXIS_X]MIN_LIMIT` for jogging and programs (M220). M221 sets
  `motion.digital-out-08`, which lowers the X limit to `[TOOLCHANGER]X_MIN_LIMIT` (`ini.*` pins,
  `postgui.hal`). M6 does M221 … M220 itself; any abort restores the work area (`on_abort.ngc`).
  Panel check button "Tool change area" does the same by hand, e.g. to jog out after an abort.
- **Checks:** homed, air pressure (`io-din3.din-0`), tool sensor (`io-din2.din-2`) agrees with the
  loaded tool. M5 at the start without waiting; HSK spindle and VFD (`io-din2.din-4`, `din-0`) must be
  stopped at the first pocket + X_OFFSET and before the motor switches (up to 10 s each, else abort).
- **Deposit:** Z top → pocket + X_OFFSET → Z pocket → G1 into pocket → release + flush air → G1 +LIFT_CHECK_Z at LIFT_CHECK_FEED, clamp still open? → G0 Z +RELEASE_Z →
  drawbar up, tool must be gone (`din2-2` FALSE). Else: no further move, machine off (`halui.machine.off`), abort; on_abort clamps the drawbar.
- **Pick:** Z top (without a deposit: pocket + X_OFFSET) → flush air on + release → straight above pocket → blow nozzle on → down to pocket Z → flush air off → clamp → blow nozzle off
  (must report clamped, else machine off) → out by X_OFFSET → Z top → X to work area.
- **Boring tools (T101–107, T201–204):** HSK tool is swapped for the dummy T17, the VFD switches to the
  boring motor + set 2 (spindle stopped), the selected spindle/aggregate goes down
  (`io-dout4.dout-1..7`, `io-dout3.dout-6` / `io-dout4.dout-0`) and stays down until the next M6, which
  raises everything first. X/Y/Z offsets to the HSK spindle: `tool.tbl`.
- M6 ends with G43 for the new tool (G49 for T0); the spindle stays off.
- Tool in spindle survives restart: M6 and M61 (`remap/m61.ngc`) store it in #3990 (persistent via
  `linuxcnc.var`), `remap/startup.ngc` reloads it; a boring tool comes back as `DUMMY_TOOL`, spindles up.
- Preview (`#<_task>` = 0) only sets the tool, no moves.

## M-codes

| Code | Function |
|------|----------|
| M6 | Tool change, see above |
| M61 Q… | Set the loaded tool without a change, stored for restart |
| M220 / M221 | X soft limits: work area / extended into the tool change area |
| M300 P*xy* [Q*z*] | Max acceleration X/Y [, Z] in mm/s², effective immediately (calls M100 + queue buster) |
| M210 | Measure loaded tool length on the probe (`[TOOLCHANGER]PROBE_*`), write to tool table |
| M250 / M251 | Release tool (checks spindle off + not turning) / clamp |
| M200 / M201 | Dust hood down / up (also panel toggle) |
| M231 / M232 / M230 | Reg pins left up / right up / all down (left foot switch toggles all, only with no program) |
| M241 / M240 | Vacuum pump on / off (right foot switch toggles, only with no program) |
| M242 / M243 [P0] | Open [close] left / right vacuum gate (pump unchanged) |
| M270 | X rack oiling cycle now (normally every 30 min of X movement) |

## Workpiece probe (Probe tab)

Pneumatic probe, `[PROBE]` in the INI. Park it above the stock, over it ~10 mm in from the bottom left corner. Every cycle
first touches the stock top (height shown on the tab, no G92), lifts, goes out past the edge, drops `EDGE_DEPTH` below the
top and touches the edge. X/Y edge cycles put the hit at 0 with G92 (tip radius and `X/Y_OFFSET` included, G49 during the
touch). Skew touches an edge twice and sets the work coordinate rotation (`G10 L2 P0 R`); order: skew, then X, Y. Hole / Pin: park over the centre, enter the expected diameter; the centre goes to X0 Y0 (G92) and the measured diameter shows.
Clear drops G92 and rotation.
**Not wired yet:** probe signal and extend output are TODO in `io.hal`; set `X/Y/Z_OFFSET` and `EXTEND_DOUT`.

## Panel

Servo load (average, % of rated torque) and speed per servo, commanded spindle speed, spindle-turning LED, vacuum pump and dust hood toggles.

Grease row: hours to the next grease service, red LED and operator message when due, **Greased** restarts the count.
X skew row: joint 0 - joint 1 position feedback in mm, and the largest |skew| since start (counted once all joints are homed).

## Pendant

- F1: idle, machine on and homed: AUTO and run the loaded program; paused: resume.
- F2: running: pause (feed hold); paused: resume.

## Stats (`machine-stats.py`)

- `job-stats.csv`: one line per program: start, end, file, finished/aborted, run time without pauses, paused, cut time, cut metres, kWh, per tool. kWh is the whole workshop (Shelly).
- `tool.tbl`: `ToolLife: 1h24 - 354m` in front of the comment, updated after each job. Totals live in `machine-stats.json`; edits to the ToolLife text are overwritten. New tool: `./machine-stats.py reset-tool 5`.
- Cutting = feed or arc move with the spindle on, so air cutting counts.
- `drive-faults.log`: drive error codes (603Fh), also shown as a LinuxCNC error. Look up the hex code in the A6 manual.

## Troubleshooting

- **F1 does nothing / machine drops to e-stop:** a slave isn't in OP — `ethercat slaves`.
- **Joint amp fault after F2:** drive not operation-enabled — check HV, `cia402.N.statusword`.
- **Spindle amp fault on M3:** tool not seen as clamped — `halcmd show pin lcec.0.io-din2`.
- **Limit error with no axis on a switch:** switch polarity — swap `din-N` / `din-N-not` in `io.hal`.
- **"Failed to register PDO entry":** an `idx` doesn't match `ethercat slaves`.
