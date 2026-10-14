# biber3ax — Weeke Vantage 33M

LinuxCNC config: 4× A6 EtherCAT servos (X gantry, Y, Z), Beckhoff I/O, KEB VFD spindle via EL4032.
Limits, speeds and homing values live in `biber3ax.ini`; scaling math in `docs/kinematics.md`.

## Start

```bash
sudo ethercat slaves      # 16 devices, all OP once LinuxCNC runs
linuxcnc biber3ax.ini
```
F1 (e-stop reset) → F2 (machine on) → home (Z, X tandem, Y).

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
- Contactors: `io-dout1.dout-3` HSK spindle (on with machine, 10 s off-delay), `dout-2` boring
  aggregate (unused yet). KEB parameter set: `dout-6` = I4 (set 5, HSK), `dout-5` = I1 (set 2, boring, unused).
- Tool numbers (for the coming tool change): T1–100 HSK, T101–107 vertical boring 1–7, T201–204 horizontal boring.

## HSK tool release

- Release output `io-dout3.dout-1` = (pendant `io-din1.din-0` OR M250) AND not turning (`io-din2.din-4`)
  AND spindle off.
- Spindle start needs tool clamped: `din2-2` TRUE, `din2-3` FALSE, release off. Else
  `spindle.0.inhibit` + spindle amp fault.

## Tool magazine

Linear rack, 20 pockets along Y at the X− end. Machine coordinates (pocket 1 extrapolated, not populated):

| Pocket | X | Y | Z |
|--------|---|---|---|
| 20 | 18.116 | 0.237 | −103.387 |
| 2 | 14.936 | 1638.770 | −101.891 |
| 1 | 14.760 | 1729.800 | −101.808 |

Pocket *n* = pocket 20 + (20 − *n*) × (−0.1767, +91.0296, +0.0831). Pocket 1 is 2.2 mm inside Y `MAX_LIMIT`.

## M-codes

| Code | Function |
|------|----------|
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
