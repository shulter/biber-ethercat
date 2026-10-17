# Vantage 33M — Kinematics and Scaling

17-bit encoders: **131072 counts/rev**. `pos-scale` = counts per mm. Configured limits, speeds and
accelerations are in `configs/biber3ax/biber3ax.ini`; the maxima below are mechanical/theoretical.

## X — dual rack & pinion (gantry)

| Parameter | Value |
|-----------|-------|
| Reduction | 10:1 |
| Pinion | helical M2, 19°31'42", 18T → 18 × 2π / cos β = 120 mm/rev |
| Travel per motor rev | **12 mm** |
| **pos-scale** | 131072 / 12 = **10922.667** |
| Max velocity @ 5800 rpm | 1160 mm/s |

Verified: 2000 mm workpiece read 2094.11 mm with the former straight-20T assumption (10434.4).

## Y — ball screw, belt reduction

| Parameter | Value |
|-----------|-------|
| Belt | 24T → 60T = 2.5:1 |
| Screw pitch | 25 mm |
| Travel per motor rev | **10 mm** |
| **pos-scale** | 131072 / 10 = **13107.2** |
| Max velocity @ 5800 rpm | 967 mm/s |

## Z — direct ball screw

| Parameter | Value |
|-----------|-------|
| Screw pitch | 5 mm |
| **pos-scale** | 131072 / 5 = **26214.4** |
| Max velocity @ 3000 rpm | 250 mm/s |

## Gantry

- Motors are mirrored: joint 0 (x-left) `CIA402_POS_SCALE = -10922.667`, joint 1 (x-right) `+10922.667`.
  If X moves the wrong way, flip both signs.
- One home switch for both joints, tandem homing (same negative `HOME_SEQUENCE`). Square the gantry
  via per-joint `HOME_OFFSET`.

## Homing / limit switches (EL1018)

| Switch | Input | Type |
|--------|-------|------|
| X+ limit / home | `io-din5.din-1` | NC |
| Y− limit / home (Y0 end) | `io-din5.din-2` | NO |
| Z+ limit / home (top) | `io-din5.din-3` | NO |
| Z− limit | `io-din5.din-4` | NO |

X and Z home +, Y homes −. `HOME_OFFSET` = switch position, just outside the soft limit.

## Drive setup

Drive encoder resolution must be 17-bit with no electronic gearing, or `pos-scale` changes.
