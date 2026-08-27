# Week Vantage 33M — LinuxCNC + EtherCAT Retrofit Plan

## Machine Overview

| Item | Detail |
|------|--------|
| Machine | Week (Weeke) Vantage 33M CNC router |
| Drives | 4× StepperOnline A6 EtherCAT 1kW servos (CiA 402) |
| X axis | Dual rack-and-pinion gantry (one servo per side) |
| Y axis | Ball screw via belt reduction |
| Z axis | Direct-drive ball screw |
| Fieldbus | EtherCAT via `lcec` + `cia402` HAL components |

## Phase 1 — Workbench EtherCAT Bring-Up (current config)

**Goal:** Prove bus communication, CiA 402 CSP mode, and dual-motor gantry motion before installing on the machine.

**Hardware on bench:**
- LinuxCNC PC with dedicated EtherCAT NIC
- 2× A6 servos daisy-chained (left + right gantry motors)
- 24 V supply, motor power, e-stop

**Software:** `configs/vantage33m-bench/`

**Steps:**
1. Install `linuxcnc-ethercat` and `hal-cia402` on the LinuxCNC PC
2. Configure `/etc/ethercat.conf` with the EtherCAT NIC MAC address
3. Run `ethercat slaves` — both A6 drives should appear at indices 0 and 1
4. Start LinuxCNC with the bench config; confirm both slaves reach OP
5. In HAL scope or `halcmd show pin`, verify `actual-position` counts change when motors are turned by hand
6. Enable drives (Machine On), jog X — both motors should move in unison
7. Verify `pos-scale` by commanding a known distance and measuring travel
8. Tune `FERROR` / acceleration once following error is acceptable

**Bench config specifics:**
- `trivkins coordinates=XX` — two joints, one X axis (gantry)
- `JOINTS = 2`, `COORDINATES = X`
- Soft limits ±500 mm (adjust for your bench setup)
- `NO_FORCE_HOMING = 1` until home switch is wired

## Phase 2 — Machine Installation (X axis)

**Goal:** Mount both X servos on the gantry, connect rack-and-pinion, wire home switch.

**Tasks:**
1. Install both X servos with 10:1 reducers and M2×20T pinions
2. Wire the single gantry home switch to both drives (or one drive, HAL-netted to both joints)
3. Update INI soft limits to 0–3780 mm
4. Set `NO_FORCE_HOMING = 0` and configure tandem homing (`HOME_SEQUENCE = -1` on both X joints)
5. Run gantry homing; square the gantry using `HOME_OFFSET` on each joint if needed
6. Verify max velocity (~1215 mm/s) and acceleration (5000 mm/s²) at reduced feed first

## Phase 3 — Y and Z Axes

**Goal:** Add remaining two servos and full 4-axis motion.

**Tasks:**
1. Add Y and Z slaves to `ethercat-conf.xml` (indices 2 and 3)
2. Change kinematics to `trivkins coordinates=XXYZ` with `JOINTS = 4`
3. Add `cia402.2` and `cia402.3` in HAL
4. Wire Y home/limit switches; Y uses a single ball screw so only one servo
5. Wire Z home/limit switches
6. Home sequence: X tandem (-1), then Y (1), then Z (2)
7. Full machine soft limits and velocity/acceleration limits

## Phase 4 — Machine I/O and Spindle

**Goal:** Integrate original machine I/O (vacuum, dust, tool change, spindle, doors).

**Tasks:**
1. Add Beckhoff EK1100 coupler + digital I/O terminals (or A6 onboard DIO where sufficient)
2. Map e-stop chain, door interlocks, spindle enable
3. Configure spindle (original Vantage spindle or retrofit VFD/analog)
4. Add PyVCP or GladeVCP panel for vacuum, dust, etc.

## Phase 5 — Tuning and Production

1. Tune servo gains in A6 drive parameters (Inovance SV660N OEM firmware)
2. Set up work coordinate systems and tool table
3. Test full-speed rapids and cutting feeds
4. Document drive parameter backup and INI version control

## EtherCAT Stack

```
LinuxCNC motion
    ↓ joint.N.motor-pos-cmd / motor-pos-fb
cia402.N (CiA 402 state machine, CSP mode 8)
    ↓ controlword, target-position / statusword, actual-position
lcec (IgH EtherCAT master HAL driver)
    ↓
A6 servos (vid=00400000, pid=00000715)
```

## Prerequisites on LinuxCNC PC

- LinuxCNC 2.9 (master) or 2.8+
- [linuxcnc-ethercat](https://github.com/linuxcnc-ethercat/linuxcnc-ethercat) — provides `lcec`, `lcec_conf`
- [hal-cia402](https://github.com/linuxcnc-ethercat/hal-cia402) — build and install `cia402.comp`
- IgH EtherCAT master configured in `/etc/ethercat.conf`
- Dedicated Intel NIC for EtherCAT (recommended)

## Reference Configs

- [CollinBardini/linuxcnc-a6-servo](https://github.com/CollinBardini/linuxcnc-a6-servo) — A6 PDO mapping
- [rodw-au/linuxcnc-cia402](https://github.com/rodw-au/linuxcnc-cia402) — CiA 402 gantry example
- [LinuxCNC EtherCAT docs](https://linuxcnc-ethercat.github.io/linuxcnc-ethercat/cia402.html)
