# biber-ethercat

LinuxCNC config for a Weeke Vantage 33M retrofit with StepperOnline A6 EtherCAT servos and Beckhoff I/O.

- [`configs/biber3ax/`](configs/biber3ax/) — machine config (4× A6: X gantry, Y, Z)
- [`docs/kinematics.md`](docs/kinematics.md) — scaling, homing, gantry
- [`docs/retrofit-plan.md`](docs/retrofit-plan.md) — original phased plan
- [`tools/servo-tune.py`](tools/servo-tune.py) — GUI: A6 gain/feedforward over EtherCAT SDO, live, with peak following error

## Hardware

- 4× StepperOnline A6 1 kW (CiA 402, Inovance SV660N OEM), 17-bit encoders
- X: 10:1 → M2×20T rack & pinion; Y: 24T→60T belt → 25 mm screw; Z: direct 5 mm screw
- Beckhoff EK1100 + EL1808/EL2808/EL1018/EL9110/EL4032; KEB F5 VFD

## Prerequisites

LinuxCNC 2.9+, [linuxcnc-ethercat](https://github.com/linuxcnc-ethercat/linuxcnc-ethercat) (`lcec`),
[hal-cia402](https://github.com/linuxcnc-ethercat/hal-cia402), IgH EtherCAT master on a dedicated NIC.
