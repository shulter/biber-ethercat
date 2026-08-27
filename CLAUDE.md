# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

LinuxCNC configuration files (INI/HAL/XML) for retrofitting a Week (Weeke) Vantage 33M CNC router with
StepperOnline A6 EtherCAT servos (CiA 402, Inovance SV660N OEM firmware). There is no application code,
build system, or test suite — this is machine configuration under version control. "Correctness" means
the INI/HAL/XML are internally consistent and match the physical machine's kinematics.

## Repo layout

- `configs/<name>/` — one directory per LinuxCNC config (currently only `vantage33m-bench/`, the Phase 1
  bench-test config for the dual X-axis gantry servos). Each config directory is self-contained: `.ini`
  (machine/joint parameters), `ethercat.hal` (lcec + cia402 HAL wiring), `ethercat-conf.xml` (EtherCAT
  slave PDO mapping), `tool.tbl`.
- `docs/retrofit-plan.md` — the phased roadmap (bench → X install → Y/Z → machine I/O → tuning). Read this
  before changing scope (e.g. adding an axis) to know what phase a change belongs to.
- `docs/kinematics.md` — authoritative source for every `pos-scale`, velocity, and travel-limit number used
  in the INI files. Any change to gear ratios, screw pitch, or encoder resolution must be reflected here
  first, then propagated to the relevant `[JOINT_n]` `CIA402_POS_SCALE` and `MAX_VELOCITY`/`MAX_LIMIT` values.

## Validating changes (no automated tests exist)

There is no CI/build/lint in this repo. Validation is manual, against the running LinuxCNC/EtherCAT stack:

```bash
sudo ethercat slaves          # confirm slaves detected and reach OP state
linuxcnc /path/to/<config>.ini
halcmd show pin               # verify actual-position counts change when motors are hand-turned
```

When reviewing or authoring config changes, check consistency by hand instead of running a linter:
- Every `pos-scale` in `ethercat.hal` / `CIA402_POS_SCALE` in the `.ini` must match the value derived in
  `docs/kinematics.md` for that axis.
- `[KINS] JOINTS` / `KINEMATICS = trivkins coordinates=...` in the INI must match the number of `cia402`
  instances loaded in the HAL file (`loadrt cia402 count=N`) and the slave count in `ethercat-conf.xml`.
- Each `[JOINT_n]` block's `MIN_LIMIT`/`MAX_LIMIT`/`MAX_VELOCITY`/`MAX_ACCELERATION` must match the
  corresponding `[AXIS_x]` block, and match the bench-vs-full-machine table in the config's own README.
- `HOME_SEQUENCE` values encode homing order/grouping: the same negative value on multiple joints means
  "home together" (tandem gantry homing), not independent phases.

## Architecture: the EtherCAT/CiA402 signal chain

Motion commands flow through three layers, wired together in `ethercat.hal`:

```
LinuxCNC motion (joint.N.motor-pos-cmd / motor-pos-fb)
    -> cia402.N          (CiA 402 state machine, CSP mode; controlword/statusword, target/actual position)
    -> lcec.<master>.<slave-name>.*  (IgH EtherCAT master HAL driver, PDO-mapped pins)
    -> A6 servo drive over EtherCAT
```

Each physical servo needs one `cia402.N` instance and one `<slave>` block in `ethercat-conf.xml`, wired by
matching HAL net names (e.g. `x-left-*`, `x-right-*`). PDO entries in `ethercat-conf.xml` (`halPin=`) must
have a corresponding `net` in `ethercat.hal` connecting `lcec.<idx>.<name>.<pin>` to the matching
`cia402.N` pin — a mismatch here is the most common source of "slave stuck in PREOP" or motors not moving.

Gantry axes (two motors driving one logical machine axis, e.g. X here) use `trivkins coordinates=XX` (one
letter per joint sharing that axis) and a single shared home switch signal netted to both joints'
`home-sw-in`, with the same negative `HOME_SEQUENCE` on both joints for tandem homing. Per-joint
`HOME_OFFSET` is the mechanism for squaring the gantry after homing, not for backlash compensation.

## Conventions when extending

- New config variants go in their own `configs/<name>/` directory with the same four files
  (`.ini`, `ethercat.hal`, `ethercat-conf.xml`, `tool.tbl`) plus a README following the existing
  Quick Start / Files / Bench-vs-Machine-settings pattern in `configs/vantage33m-bench/README.md`.
- Future axes (Y, Z) are sketched as commented-out `[AXIS_y]`/`[JOINT_n]` blocks at the bottom of
  `vantage33m-bench.ini` — when activating one, uncomment, wire the corresponding `cia402` instance and
  slave in the HAL/XML files, and bump `[KINS] JOINTS` and `coordinates=`.
- Keep `docs/kinematics.md` as the single source of truth for scaling math; don't recompute `pos-scale`
  inline in HAL/INI comments without cross-referencing it.
