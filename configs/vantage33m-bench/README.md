# Vantage 33M — X Gantry + Y Axis Bench Config

LinuxCNC configuration for bench-testing three StepperOnline A6 EtherCAT servos: two as a dual-motor X
gantry, plus one on the Y axis.

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
   # Expected: three devices at position 0, 1, and 2 (A6 / SV660N)
   ```

4. Copy or symlink this config directory to your LinuxCNC configs path, then start:
   ```bash
   linuxcnc /path/to/vantage33m-bench.ini
   ```

5. Turn Machine On, enable all joints, jog X and Y. Both X motors should move together; the Y motor
   moves independently.

## Files

| File | Purpose |
|------|---------|
| `vantage33m-bench.ini` | Machine parameters, joint limits, kinematics |
| `ethercat.hal` | lcec + cia402 wiring for 3 servos |
| `ethercat-conf.xml` | EtherCAT slave topology and PDO mapping |
| `tool.tbl` | Minimal tool table |

## Bench vs Machine Settings

| Setting | Bench | Full machine |
|---------|-------|--------------|
| Soft limits (X) | ±500 mm | 0–3780 mm |
| Soft limits (Y) | 0–500 mm | 0–1651 mm |
| Max velocity | 200 mm/s | 1215 mm/s (X) / 967 mm/s (Y) |
| Max acceleration | 500 mm/s² | 5000 mm/s² |
| NO_FORCE_HOMING | 1 | 0 |
| Joints | 3 (XXY) | 4 (XXYZ) |

## Troubleshooting

- **Slaves stuck in PREOP:** Use variable PDO mapping (0x1600/0x1A00) as in `ethercat-conf.xml`; avoid fixed PDOs.
- **Following error on enable:** Reduce acceleration; verify `CIA402_POS_SCALE` (10434.4 for X, 13107.2 for Y); check encoder resolution in drive params.
- **Only one X motor moves:** Confirm `trivkins coordinates=XXY` and both X `cia402` instances (0, 1) are wired.
- **Gantry skew:** After homing, adjust `HOME_OFFSET` on joint 0 or 1 to square the gantry.
- **Y motor doesn't move:** Confirm `cia402.2` is wired to `lcec.0.y.*` and `joint.2`, and `HOME_SEQUENCE = 1` (Y homes after the X tandem pair).

See `docs/kinematics.md` for pos-scale calculations and `docs/retrofit-plan.md` for the full retrofit roadmap.
