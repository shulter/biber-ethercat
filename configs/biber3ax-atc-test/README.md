# Vantage 33M — ATC Test Config (biber3ax-atc-test)

3 servos, 3 axes: single-motor X (no gantry — this is bench test mode), Y, Z. Adds a HSK63F automatic
tool changer, 7 vertical + 4 horizontal fixed drill spindles, and an M106 tool-height-probing routine —
implemented via M6/M106 g-code remapping.

None of the toolchanger/drill/probe I/O hardware (Beckhoff EK1100 coupler, solenoids, probe) is
confirmed present yet — this config is meant to let you test the M6/M106 **logic and motion sequencing**
(tool table bookkeeping, remap control flow, X/Y/Z positioning) on the bench servos now, with the actual
I/O wiring ready to uncomment once the coupler and probe are connected.

## Quick Start

1. Install dependencies on the LinuxCNC PC (same as `vantage33m-bench`):
   ```bash
   # linuxcnc-ethercat (lcec) — see https://github.com/linuxcnc-ethercat/linuxcnc-ethercat
   # hal-cia402 — build cia402.comp and install
   ```
2. Configure EtherCAT master in `/etc/ethercat.conf` (set `MASTER0_DEVICE` to your NIC MAC).
3. Verify slaves are detected:
   ```bash
   sudo ethercat slaves
   # Expected: three devices at position 0-2 (A6 / SV660N: x, y, z)
   ```
4. Copy or symlink this config directory to your LinuxCNC configs path, then start:
   ```bash
   linuxcnc /path/to/biber3ax-atc-test.ini
   ```
5. Turn Machine On, home all joints, jog X/Y/Z to confirm normal motion still works before trying any
   `M6`/`M106` calls.

## Files

| File | Purpose |
|------|---------|
| `biber3ax-atc-test.ini` | Machine parameters, joint limits, kinematics, REMAP config |
| `ethercat.hal` | lcec + cia402 wiring for 3 servos (X, Y, Z); `num_dio=16` for the toolchanger I/O |
| `ethercat-conf.xml` | EtherCAT slave topology and PDO mapping — servos active, Beckhoff chain commented out |
| `io.hal` | Toolchanger I/O wiring (drill solenoids, drawbar, probe) — commented out |
| `panel.xml` / `postgui.hal` | PyVCP servo torque/speed panel (X, Y only) |
| `tool.tbl` | Tool table: T1 (dummy plug), T2-T20 (ATC pockets), T101-T107 (vertical drills), T201-T204 (horizontal drills) |
| `remap/atc-positions.ngc` | Shared position/config constants — **all placeholder values, see below** |
| `remap/m6_remap.ngc` | M6 remap: ATC tool change / drill select |
| `remap/return_tool.ngc`, `remap/fetch_tool.ngc` | M6 remap helpers: release/grab an ATC tool from its pocket |
| `remap/ensure_plug.ngc` | M6 remap helper: park the dummy plug (T1) in the spindle before a drill is used |
| `remap/m106_remap.ngc` | M106 remap: tool height probing |
| `remap/vdrill_probe_offset.ngc` | M106 remap helper: per-vertical-drill XY offset for the probe move |
| `remap/m107_remap.ngc` | M107 remap: deploy the Marposs workpiece touch probe |
| `remap/m108_remap.ngc` | M108 remap: retract the Marposs workpiece touch probe |
| `probe_z_example.ngc` | Example/template: Z touch-off + G54 zero using the Marposs probe |

## Tool Changer

Tool numbers select one of three physically different things, all handled by the same `M6`:

- **T1** — a short dummy/plug tool, not a cutting tool. Parked in the spindle whenever a fixed drill is
  engaged (see below) to keep dust out of the spindle and keep it clear of the workpiece.
- **T2-T20** — a real ATC tool change. The current ATC tool (if any) is returned to its pocket, then the
  new one is fetched: `G53` move to the pocket's X/Y, plunge Z, toggle the spindle drawbar solenoid
  (`motion.digital-out-11`), retract.
- **T101-T107** — one of 7 vertical drills. These are fixed-mounted on the machine (not stored in the
  ATC), so no travel happens to select one. `M6 T101` first makes sure the dummy plug (T1) is in the
  spindle — swapping it in via the same ATC pocket sequence as above if it isn't already there — then
  fires that drill's solenoid (`digital-out-00`..`06`) and turns off everything else.
- **T201-T204** — one of 4 horizontal drills (X+, X-, Y+, Y-). Same idea (dummy plug first, then
  solenoid), `digital-out-07`..`10`.

`remap/atc-positions.ngc` holds every position constant (pocket rack base/pitch, engage depth, safe
clearance Z). **All of these are placeholders**, chosen only to fit inside this bench config's reduced
soft limits (X ±500, Y 0-500, Z -155-0) so a dry run doesn't immediately fault — they do not reflect any
real measurement of the machine. Before trusting this for real tool changes, verify/measure:

- Pocket 1 position, pitch, and orientation (currently assumed spaced along X, "one end of the table" —
  confirm which end and which axis)
- Engage depth and safe-clearance Z heights
- **Spindle drawbar solenoid sense** — `return_tool.ngc`/`fetch_tool.ngc` assume energized
  (`digital-out-11` on) = unclamp/release, de-energized = spring-clamped/grip. If your valve is wired the
  other way, swap the `M64`/`M65` in those two files.
- The `G4 P0.5` "settle" dwells after each clamp toggle are placeholders standing in for a real
  drawbar-clamped/unclamped confirmation input — there isn't one wired yet (see `io.hal`)

## Tool Height Probing

`M106` probes tool length at a fixed location:

- `M106` — probes whatever tool is currently in the spindle
- `M106 T<n>` — selects tool `<n>` first (a real `T<n> M6`, so LinuxCNC's own tool-in-spindle bookkeeping
  stays correct), then probes it

Vertical drills (T101-T107) **can** be probed: they share the spindle's Z orientation, so once `M6` has
parked the dummy plug and fired the drill's solenoid, the drill tip can dip onto the same fixed probe
just like an ATC tool. Each drill sits at a different physical offset from the spindle centerline
(mounted alongside it as a block that travels together in X/Y), so `vdrill_probe_offset.ngc` adds a
per-drill XY offset (`#<_vdrill1_dx>`/`#<_vdrill1_dy>` ... `#<_vdrill7_dx>`/`#<_vdrill7_dy>` in
`atc-positions.ngc`) to the base probe position before probing — **all placeholder (0,0)**, measure each
drill's real offset before trusting probed lengths.

`M106` refuses to probe a horizontal drill (T201-T204) — these point sideways, not down, so a Z-axis
touch probe can't measure their length the way it can the spindle or a vertical drill. It logs a message
and skips instead of writing garbage into the tool table.

The routine stops the spindle, moves to the fixed probe X/Y (also placeholders in
`atc-positions.ngc`, offset per-drill for verticals as above), probes down with `G38.2` (which already
aborts the program if it doesn't trigger — no separate handling needed for a probe that never trips), and
writes the resulting length offset into the tool table with `G10 L1 P<tool> Z<offset>`.

**Needs verification before trusting the numbers this produces:**
- `#5063` is used as "Z position of the last probe trip" — confirm this parameter number against your
  installed LinuxCNC version
- The length-offset sign convention (`#5063 - #<_probe_ref_z>`) is a best-effort guess, not calibrated
  against a real reference — probe a known tool and check the resulting `G43` behavior before trusting it
- `argspec=T` on the M106 remap (for the `M106 T1` syntax) — verify this parses as intended on your
  LinuxCNC version; if it doesn't, the fallback is splitting T onto its own preceding line (`T1 M106`,
  same as a normal tool prepare) instead of `M106T1`
- Per-vertical-drill probe offsets (`atc-positions.ngc`) are all `(0,0)` — every drill will probe at
  exactly the base probe position until measured, which is very likely wrong for at least 6 of the 7

## Workpiece Touch Probe (Marposs)

A Marposs touch probe on its own pneumatic linear actuator, mounted next to the HSK63F spindle — not
carried in a tool holder, so it never goes through `M6`/the tool table at all. It's controlled directly:

- **`M107`** — deploy (extend) the probe. Energizes `digital-out-12` (see `io.hal`).
- **`M108`** — retract the probe. De-energizes `digital-out-12`. **Always call this before resuming
  cutting motion** — nothing else in this config retracts it automatically, and left extended it's close
  enough to the spindle to be a crash risk.

Once deployed, probe with LinuxCNC's standard `G38.2`/`G38.3`/`G38.4`/`G38.5` straight-probe moves — no
custom macro needed for the touch move itself, only for deploy/retract. Example:

```
M107                      ; deploy
G38.2 Z-50 F100           ; probe toward the work; aborts the program if it never triggers
#<touch_z> = #5063        ; record the trip position (Z shown here; #5061/#5062 for X/Y)
G0 Z[#<touch_z> + 5]      ; retract clear
M108                      ; stow the probe
```

See `probe_z_example.ngc` for a runnable version of this that also zeroes G54 Z at the touched surface.

The probe's trigger contact shares LinuxCNC's single `motion.probe-input` pin with the fixed tool-height
probe via an `or2` in `io.hal` (LinuxCNC only has one probe input, and the two are never in position to
trip at once in correctly sequenced g-code — see the channel-assignment comment there).

**Needs on-machine verification before trusting this:**
- Deploy/retract solenoid sense — assumed energized = deployed, same "verify before running" caveat as
  the ATC drawbar; swap the `M64`/`M65` in `m107_remap.ngc`/`m108_remap.ngc` if reversed.
- Trigger contact polarity (normally-closed vs normally-open) — unverified, confirm against the actual
  Marposs unit's wiring/datasheet.
- Probe tip offset from the spindle centerline/gauge line — not modeled here since the actual mounting
  geometry isn't known yet. If you probe in X/Y (not just Z), you'll need to account for this offset the
  same way `remap/vdrill_probe_offset.ngc` does for the vertical drills.
- `#5063`/`#5061`/`#5062` (probe trip position parameters) — confirm against your installed LinuxCNC
  version, same caveat as `remap/m106_remap.ngc`.

## Probing from Fusion 360

Fusion 360's dedicated **Probe** CAM operation (Inspect workspace) targets vendor canned-cycle macros
(Renishaw/Blum/Heidenhain-style `G65`/cycle calls) baked into specific posts for controls like Fanuc,
Haas, or Siemens. The stock LinuxCNC post does not implement those cycle handlers, so Fusion's Probe
operation either errors during post-processing or produces output that won't run — **don't use it** with
this config.

Instead, use Fusion's **Manual NC** operation (Milling → Manual NC) to insert raw g-code text at the
point in the toolpath sequence where you want probing to happen — it's passed through to the post
unchanged. For example, at the start of a Setup, before the first real cutting operation:

```
M107
G38.2 Z-50 F100
G10 L20 P1 Z0
G0 Z5
M108
```

Two ways to use this in practice:
- **Inline, per-job** — add a Manual NC block at the top of the Fusion Setup so probing/WCS-zeroing is
  baked into every posted program for that job.
- **Once, outside Fusion** — probe/zero the WCS directly on the LinuxCNC controller (MDI, or run
  `probe_z_example.ngc`) before loading the Fusion-generated program at all, and let Fusion's output be
  pure toolpath with no probing in it. Simpler, and the more common pattern for shops that don't need
  probing baked into every posted file.

Either way, Fusion isn't computing anything from the probe result — `#5061`/`#5062`/`#5063` and the
`G10 L20` write happen entirely on the LinuxCNC side after the physical touch, same as any other
LinuxCNC-native probing.

## Toolchanger I/O

`io.hal` nets `motion.digital-out-00`..`12` (drills, drawbar, Marposs probe deploy) and
`motion.probe-input` (tool height probe OR'd with the Marposs probe trigger) to specific channels on the
same Beckhoff EK1100 chain used by `configs/biber3ax/` — all commented out, since the coupler isn't on
this bench either. See the comments at the top of `io.hal` for the full channel assignment. Uncomment
together with the matching slaves in `ethercat-conf.xml` — don't enable only one file, or slave
indices/pin names will mismatch.

## Bench vs Machine Settings

Same as `vantage33m-bench` for X/Y (single X motor here, not the dual gantry — see that config's README
for the general bench-vs-machine numbers) — Z uses full-machine values (not bench-reduced) since the
ATC/probe/drill positions already need real Z travel and are placeholders pending measurement regardless:

| Setting | Z |
|---------|---|
| Soft limits | -155-0 mm |
| Max velocity | 250 mm/s |
| Max acceleration | 5000 mm/s² |
| Max jerk | 50000 mm/s³ |
| pos-scale | 26214.4 |
| Home direction | toward 0 (max, top) |

## Troubleshooting

Same as `vantage33m-bench` for the servo/EtherCAT basics, plus:

- **"Machine On" refuses to enable, or the machine drops out on its own:** `iocontrol.0.emc-enable-in` is
  netted to `lcec.0.state-op` (`ethercat.hal`) — Machine On is refused, and an already-enabled machine is
  disabled like a fault, whenever the EtherCAT master hasn't got all slaves into OP state. Run
  `sudo ethercat slaves` to see which slave is stuck and in what state before assuming this is a config bug.
- **`M6`/`M106` errors on startup ("unknown code")**: Confirm `SUBROUTINE_PATH = ./remap` and both
  `REMAP=` lines are present in `[RS274NGC]`, and that `remap/` sits next to the `.ini` file.
- **Tool change moves to the wrong place**: Expected — `remap/atc-positions.ngc` is entirely placeholder
  values. Measure the real machine and update it.
- **`G38.2 probing move failed` on `M106`**: Expected without the probe wired — this is the built-in
  LinuxCNC behavior when a probe move doesn't trigger, not a bug in the remap.
- **`M106 T201` (or any horizontal drill number) does nothing but print a message**: Expected — see
  "Tool Height Probing" above, a horizontal drill can't be measured by a Z-axis probe.
- **`M106 T101` (or any vertical drill) probes the same spot every time**: Expected until you measure and
  fill in that drill's offset in `atc-positions.ngc` — they're all `(0,0)` placeholders right now.
- **`M107`/`M108` errors on startup ("unknown code")**: Same cause/fix as the `M6`/`M106` bullet above —
  confirm the `REMAP=M107`/`REMAP=M108` lines are present.
- **`G38.2 probing move failed` when using the Marposs probe**: Expected without the probe wired — same
  built-in LinuxCNC behavior as the `M106` case above. If it's wired, confirm `M107` actually ran first
  (probe must be deployed) and check the trigger contact's NC/NO polarity in `io.hal`.
- **Marposs probe doesn't retract / stays extended**: `M108` isn't called automatically by anything —
  it's on you (or your g-code) to call it after every probing sequence. There's no interlock in this
  config that prevents cutting motion with the probe still deployed.

See `docs/kinematics.md` for pos-scale calculations and `docs/retrofit-plan.md` for the full retrofit roadmap.
