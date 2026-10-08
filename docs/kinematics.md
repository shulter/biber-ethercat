# Vantage 33M — Kinematics and Scaling

All axes use 17-bit encoders: **131072 counts/rev** at the motor shaft.

`pos-scale` in HAL = encoder counts per machine unit (mm).

## X Axis — Dual Rack & Pinion (Gantry)

| Parameter | Value |
|-----------|-------|
| Gear reduction | 10:1 |
| Rack module | 2 mm |
| Pinion teeth | 20 |
| Pinion pitch diameter | 2 × 20 = **40 mm** |
| Linear travel per pinion rev | π × 40 = **125.664 mm** |
| Linear travel per motor rev | 125.664 / 10 = **12.566 mm** |
| **pos-scale** | 131072 / 12.566 = **10434.4 counts/mm** |
| Max motor RPM | 5800 |
| **Max velocity** | 5800/60 × 12.566 = **1215 mm/s** |
| Max travel | **3780 mm** |
| Max acceleration | **5000 mm/s²** (5 m/s²) |

## Y Axis — Ball Screw with Belt Reduction

| Parameter | Value |
|-----------|-------|
| Motor pulley | 24 teeth |
| Screw pulley | 60 teeth |
| Reduction | 60/24 = **2.5:1** |
| Ball screw pitch | **25 mm** |
| Linear travel per motor rev | 25 / 2.5 = **10 mm** |
| **pos-scale** | 131072 / 10 = **13107.2 counts/mm** |
| Max motor RPM | 5800 |
| **Max velocity** | 5800/60 × 10 = **967 mm/s** |
| Max travel | **1651 mm** |
| Max acceleration | **5000 mm/s²** |

## Z Axis — Direct Ball Screw

| Parameter | Value |
|-----------|-------|
| Ball screw pitch | **5 mm** |
| Linear travel per motor rev | **5 mm** |
| **pos-scale** | 131072 / 5 = **26214.4 counts/mm** |
| Max motor RPM | 3000 |
| **Max velocity** | 3000/60 × 5 = **250 mm/s** |
| Max travel | **155 mm** |
| Max acceleration | **5000 mm/s²** |

## Jerk Limiting (S-curve Trajectory Planner)

`MAX_JERK` enables LinuxCNC's jerk-limited trajectory planner, which rounds the trapezoidal
velocity profile into an S-curve. Convention used here: **MAX_JERK = 10 × MAX_ACCELERATION**
(i.e. accel ramps to full value in ~0.1 s). All axes share the same MAX_ACCELERATION (5000 mm/s²),
so all axes share the same jerk:

| Parameter | Full machine (`biber3ax.ini`) | Bench (`vantage33m-bench.ini`) |
|-----------|-------------------------------|--------------------------------|
| MAX_ACCELERATION (all axes) | 5000 mm/s² | 500 mm/s² |
| **MAX_JERK (all axes)** | **50000 mm/s³** | **5000 mm/s³** |

Set at `[TRAJ]`, each `[AXIS_x]`, and each `[JOINT_n]` in both configs. If retuning
`MAX_ACCELERATION` for an axis, recompute its `MAX_JERK` at the same 10× ratio.

## Homing / Limit Switches

All axes home in the **positive** direction onto their positive limit switch, which doubles as the
home switch (`HOME_IGNORE_LIMITS = YES`). The switches are on the Beckhoff EL1018 (`io.hal`):

| Switch | Input | Joints |
|--------|-------|--------|
| X positive limit / home | `io-din5.din-1` | 0, 1 (gantry) |
| Y positive limit / home | `io-din5.din-2` | 2 |
| Z positive limit / home (top) | `io-din5.din-3` | 3 |
| Z negative limit (bottom) | `io-din5.din-4` | 3 |

X and Y have no negative limit switch. `HOME_OFFSET` is the switch position in machine coordinates,
set 2 mm beyond `MAX_LIMIT` (X 3782, Y 1653, Z 2) with `HOME = MAX_LIMIT` (except Y, which finishes
50 mm below its switch: `HOME = 1603`), so moves up to the soft limit stay clear of the hard limit.
Homing order: Z (`HOME_SEQUENCE = 1`), then Y (`2`), then both X joints together (`-3`). These are placeholders: measure where each switch actually trips
and correct `HOME_OFFSET` (and `MAX_LIMIT` if the usable travel differs).

## Gantry Motor Direction

The two X gantry motors are mounted mirrored (facing each other across the gantry), so for the
same X move they must turn in opposite directions. Joint 0 (x-left) therefore uses a **negative**
scale, `CIA402_POS_SCALE = -10434.4`; joint 1 (x-right) uses `+10434.4`, so +X moves toward the X limit
switch. `cia402` multiplies the command by
`pos-scale` and divides the feedback by it, so the sign flips both consistently. If X as a whole
moves the wrong way, flip the sign on **both** X joints.

## Gantry Homing

The Vantage 33M has a **single home switch** for the X gantry. Both gantry servos share it:

- The switch is wired to `io-din5.din-1`; HAL nets the same signal to `home-sw-in` and
  `pos-lim-sw-in` of both `joint.0` and `joint.1`
- Use **tandem homing**: `HOME_SEQUENCE = -3` on both X joints (negative = move together; X homes
  last, after Z and Y)
- Adjust `HOME_OFFSET` per joint to square the gantry after homing

## Drive Encoder Setup

Confirm in the A6/SV660N drive parameters that the encoder resolution is set to 17-bit (131072 PPR). The `pos-scale` values above assume the CiA 402 `actual-position` object reports motor-shaft counts.

If the drive reports counts after electronic gearing, adjust `pos-scale` accordingly.
