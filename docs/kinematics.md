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

## Gantry Homing

The Vantage 33M has a **single home switch** for the X gantry. Both gantry servos share it:

- Wire the switch to one A6 digital input (or parallel to both)
- HAL nets the same `home-sw-in` signal to `joint.0` and `joint.1`
- Use **tandem homing**: `HOME_SEQUENCE = -1` on both X joints (negative = move together)
- Adjust `HOME_OFFSET` per joint to square the gantry after homing

## Drive Encoder Setup

Confirm in the A6/SV660N drive parameters that the encoder resolution is set to 17-bit (131072 PPR). The `pos-scale` values above assume the CiA 402 `actual-position` object reports motor-shaft counts.

If the drive reports counts after electronic gearing, adjust `pos-scale` accordingly.
