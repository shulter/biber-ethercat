# biber-ethercat

LinuxCNC configuration for a Week Vantage 33M retrofit with StepperOnline A6 EtherCAT servos.

## Status

**Phase 1 (bench test):** Dual X gantry servos — config ready in `configs/vantage33m-bench/`.

**Final (all axes):** 4× A6 servos (X gantry, Y, Z) at full machine travel, with Beckhoff I/O and
spindle templates wired but commented out — `configs/biber3ax/`.

## Documentation

- [Retrofit plan](docs/retrofit-plan.md) — phased roadmap from bench to full machine
- [Kinematics & scaling](docs/kinematics.md) — encoder counts, velocities, pos-scale for all axes

## Configs

| Config | Description |
|--------|-------------|
| [`configs/vantage33m-bench/`](configs/vantage33m-bench/) | 2× A6 on X gantry for workbench EtherCAT testing |
| [`configs/biber3ax/`](configs/biber3ax/) | Final 3-axis config: 4× A6 (X gantry, Y, Z) + commented-out Beckhoff I/O and spindle |

## Hardware

- 4× StepperOnline A6 EtherCAT 1kW (CiA 402, Inovance SV660N OEM)
- 17-bit encoders (131072 counts/rev)
- X: 10:1 → M2×20T rack & pinion
- Y: 24T→60T belt → 25 mm ball screw
- Z: direct 5 mm ball screw

## Prerequisites

- LinuxCNC 2.9+
- [linuxcnc-ethercat](https://github.com/linuxcnc-ethercat/linuxcnc-ethercat) (`lcec`)
- [hal-cia402](https://github.com/linuxcnc-ethercat/hal-cia402) (`cia402.comp`)
- IgH EtherCAT master with dedicated NIC
