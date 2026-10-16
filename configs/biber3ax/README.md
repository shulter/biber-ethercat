# biber3ax — Weeke Vantage 33M

LinuxCNC config: 4× A6 EtherCAT servos (X gantry, Y, Z), Beckhoff I/O, KEB VFD spindle via EL4032.
Limits, speeds and homing values live in `biber3ax.ini`; scaling math in `docs/kinematics.md`.

## Start

```bash
sudo ethercat slaves      # 16 devices, all OP once LinuxCNC runs
linuxcnc biber3ax.ini
```
F1 (e-stop reset) → F2 (machine on) → home (Z, X tandem, Y).

### Absolute encoders (`biber3ax-abs.ini`)

`linuxcnc biber3ax-abs.ini`: Machine On homes all joints at once (no motion, `abs-home.hal`), using the drives'
battery-backed absolute position. Otherwise identical: `abs-ini.sh` regenerates it from
`biber3ax.ini` on every start. Setup, once:

1. A6 drives: absolute encoder mode on, battery fitted, multi-turn data reset (drive manual).
2. Home with `biber3ax.ini`, then `./abs-ini.sh measure` → offsets into `[ABS_ENCODER]`.

Re-measure after a battery/encoder alarm or multi-turn reset — otherwise every position is wrong.

## Files

| File | Content |
|------|---------|
| `biber3ax.ini` | Machine, joints, homing, remaps |
| `ethercat-conf.xml` | Bus layout / PDO mapping |
| `ethercat.hal` | Servos, e-stop loop, drive-ready check, spindle analog out |
| `io.hal` | Beckhoff I/O and interlocks |
| `postgui.hal`, `panel.xml` | PyVCP panel |
| `remap/*.ngc` | M-codes below |

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

- Release output `io-dout3.dout-1` = (pendant `io-din1.din-0` OR M250) AND not turning (`io-din2.din-4`)
  AND spindle off.
- Spindle start needs tool clamped: `din2-2` TRUE, `din2-3` FALSE, release off. Else
  `spindle.0.inhibit` + spindle amp fault.

## Tool changer (M6)

Linear rack, 20 pockets along Y at the X− end. Tool number = pocket number (T1–T20, T0 = unload).
Pocket positions and approach offsets: `toolchanger.ini` (`#INCLUDE`d into `biber3ax.ini`).

- **Work area:** X ≥ `[AXIS_X]MIN_LIMIT` for jogging and programs (M220). M221 sets
  `motion.digital-out-08`, which lowers the X limit to `[TOOLCHANGER]X_MIN_LIMIT` (`ini.*` pins,
  `postgui.hal`). M6 does M221 … M220 itself; any abort restores the work area (`on_abort.ngc`).
- **Checks:** homed, air pressure (`io-din3.din-0`), tool sensor (`io-din2.din-2`) agrees with the
  loaded tool. M5 at the start without waiting; the spindle must be stopped at the first pocket +
  X_OFFSET (waits up to 10 s, else abort).
- **Deposit:** Z top → pocket + X_OFFSET → Z pocket → G1 into pocket → release + flush air → Z +Z_CHECK →
  tool must be gone. Else: back down, clamp, move out, machine off (`halui.machine.off`), abort.
- **Pick:** Z top → X +X_BACKOFF → pocket + X_OFFSET → above pocket → release + flush air → down → clamp
  (must report clamped, else machine off) → out by X_OFFSET → Z top → X to work area.
- **Boring tools (T101–107, T201–204):** HSK tool is swapped for the dummy T17, the VFD switches to the
  boring motor + set 2 (spindle stopped), the selected spindle/aggregate goes down
  (`io-dout4.dout-1..7`, `io-dout3.dout-6` / `io-dout4.dout-0`) and stays down until the next M6, which
  raises everything first. X/Y/Z offsets to the HSK spindle: `tool.tbl`.
- M6 ends with G43 for the new tool (G49 for T0); the spindle stays off.
- Tool in spindle survives restart: M6 stores it in #3990 (persistent via `linuxcnc.var`),
  `remap/startup.ngc` reloads it. A manual `M61 Q…` is not stored.
- Preview (`#<_task>` = 0) only sets the tool, no moves.

## M-codes

| Code | Function |
|------|----------|
| M6 | Tool change, see above |
| M220 / M221 | X soft limits: work area / extended into the tool change area |
| M210 | Measure loaded tool length on the probe (`[TOOLCHANGER]PROBE_*`), write to tool table |
| M250 / M251 | Release tool (checks spindle off + not turning) / clamp |
| M200 / M201 | Dust hood down / up (also panel toggle) |
| M231 / M230 | Reg pins up / down |
| M241 / M242 / M243 / M240 | Vacuum both / left / right / off |

## Panel

Torque and speed per servo, commanded spindle speed, spindle-turning LED, dust hood toggle.

## Troubleshooting

- **F1 does nothing / machine drops to e-stop:** a slave isn't in OP — `ethercat slaves`.
- **Joint amp fault after F2:** drive not operation-enabled — check HV, `cia402.N.statusword`.
- **Spindle amp fault on M3:** tool not seen as clamped — `halcmd show pin lcec.0.io-din2`.
- **Limit error with no axis on a switch:** switch polarity — swap `din-N` / `din-N-not` in `io.hal`.
- **"Failed to register PDO entry":** an `idx` doesn't match `ethercat slaves`.
