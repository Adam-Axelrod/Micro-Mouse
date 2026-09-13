# Constants

Every constant in `config.py`, and where its number came from.

Invariant 5 says a number in logic is a bug, so all of them live in one file.
That file says what each number IS. It does not say how much to trust it, and
those are different questions. A wrong `SOAK_DRIVE_POWER` is a slow run. A wrong
`TRACK_WIDTH_MM` is a lie the whole codebase then reasons from.

This document is the provenance. `tests/health/test_structure.py` fails if
`config.py` gains a constant that is not named here.

## The six classes

| Class | Means | Rule |
|---|---|---|
| **FIXED** | Competition spec or a datasheet. Not ours. | Change only if the spec does. |
| **MEASURED** | Taken off this physical robot. Carries a date and a method. | Change only with a new measurement and a log entry. |
| **DESIGNED** | Follows from how the part is built. Not measurable. | Hold it fixed. If ticks and a tape disagree, the ticks are wrong. |
| **DERIVED** | Computed from other constants here. | Never hand-edit. Edit its inputs. |
| **CHOSEN** | A preference. | Change freely. |
| **PROVISIONAL** | Reasoned from, never checked against the world. | Treat every result that depends on it as provisional too. |

FIXED and MEASURED continue the vocabulary set in
`Logs/2026-08-15_system-reset.md` §6b. The other four name distinctions that
kept being made in prose.

**PROVISIONAL is the class that earns this document.** It marks the numbers the
robot acts on that nothing has confirmed. Two of them set every drive power on
the machine.

## Chassis: the measured set

These six are the calibration. Mode 4 exists to produce two of them, and the
live traps in `AGENTS.md` are mostly about the ways they can be wrong together.

| Constant | Value | Class | Provenance, and what breaks |
|---|---|---|---|
| `WHEEL_DIAMETER_MM` | 32 | MEASURED | Ruler, 2026-08-31. Pololu 32x7. The effective rolling diameter under load is smaller by tenths of a mm, never larger. Scales every distance. |
| `TRACK_WIDTH_MM` | 75 | MEASURED | Ruler, wheel centre to centre, 2026-08-31. Replaced an unmeasured 70. Pivot timing divides by it, so a wrong value puts every turn out by the same percentage. The kinematic track is between the tyre CONTACT patches and a pivot scrubs, so the effective value can sit a few percent off. |
| `ENCODER_COUNTS_PER_WHEEL_REV` | 1400 | DESIGNED | 28 edges per motor shaft revolution at full quadrature, times a 50:1 gearbox. BT-7's ~1306 and BT-8's ~66 were decoder faults, not measurements. |
| `WHEEL_CIRCUMFERENCE_MM` | pi x 32 | DERIVED | From `WHEEL_DIAMETER_MM`. |
| `MM_PER_TICK` | ~0.0718 | DERIVED | `WHEEL_CIRCUMFERENCE_MM / ENCODER_COUNTS_PER_WHEEL_REV`. Every distance the robot believes is `ticks x MM_PER_TICK`. |
| `MAX_WHEEL_SPEED_MMS` | 681.0 | MEASURED | Mode 4, 2026-08-31: 5904 mm of wheel travel in 8.667 s, from the encoders, tape-agreed to 1.6%. An AVERAGE FROM REST over ~5.9 m, **not** a terminal speed. The same run gave 644 mm/s over 5.0 m, and that gap is the acceleration ramp. Nothing models the ramp, so this constant is only honest over metres. A 180 mm cell commands 0.264 s, which is almost all ramp, and falls short. |

**The trap that links them:** a pivot comes out at
`90 x (V_real/V_cfg) x (W_cfg/W_real)` degrees. Before 2026-08-31 both speed and
track were wrong and they cancelled to 90.1 degrees, so turns looked right while
straights over-ran by 7%. Fixing one alone BREAKS turns. Never change one of
these without recomputing the product.

## Chassis: the body frame

| Constant | Value | Class | Provenance |
|---|---|---|---|
| `BODY_LENGTH_MM` | 100 | PROVISIONAL | Origin unrecorded. No reader in the codebase today. |
| `BODY_WIDTH_MM` | 80 | PROVISIONAL | Origin unrecorded. Render only. |
| `WHEEL_AXIS_TO_BACK_MM` | 36 | PROVISIONAL | Origin unrecorded. Sets where the sim draws and rotates the chassis. |
| `WHEEL_AXIS_TO_FRONT_MM` | 64 | DERIVED | `BODY_LENGTH_MM - WHEEL_AXIS_TO_BACK_MM`. |

## Maze

| Constant | Value | Class | Provenance |
|---|---|---|---|
| `MM_PER_CELL` | 180 | FIXED | Classic spec, wall centre to wall centre. The key sim anchor. |
| `POST_SIDE_MM` | 12 | FIXED | Classic spec wall thickness. |
| `WALL_WIDTH_MM` | 12 | DERIVED | `= POST_SIDE_MM`. |
| `WALL_LENGTH_MM` | 168 | DERIVED | `MM_PER_CELL - POST_SIDE_MM`, written as a literal. The GAP between two posts. No reader in the codebase. |

The printed wall part is 172.5 mm, and that is not a disagreement with the 168
above: the part includes the tabs that seat into the posts at each end. A
`classic-maze-wall-plus-1mm.stl` exists in `Maze Construction/` and takes the
part to 173.5 mm. That change was a FIT tolerance, not a geometry change, and it
has never been printed. The maze is built from the original walls. Nothing about
either number reaches a run.

## Drive powers

| Constant | Value | Class | Provenance |
|---|---|---|---|
| `CRUISE_DUTY_POWER` | 0.55 | PROVISIONAL | Derived from the motor model, never measured on the chassis. Every speed run drives at it. |
| `TURN_DUTY_POWER` | 0.40 | PROVISIONAL | As above. A pivot scrubs both tyres sideways and needs more duty to break away than a straight does. The motor deadband is unmeasured, and under it the wheels do not start at all. |
| `INTER_COMMAND_SETTLE_S` | 0.1 | CHOSEN | Brake held between two verbs so a pivot does not start while the chassis is still rocking. |

**The open question these two carry:** speed is assumed LINEAR in duty, and
that has never been measured. A DC motor's deadband makes linearity false at low
duty. Mode 4 at `power=0.55` predicts 14.1 s over 5 m if it holds.

## Mode 4, the max speed test

| Constant | Value | Class | Provenance |
|---|---|---|---|
| `MAX_SPEED_TEST_DISTANCE_MM` | 5200.0 | CHOSEN | A 5 m marked run plus 200 mm of overrun. |
| `MAX_SPEED_TEST_POWER` | 1.0 | CHOSEN | Full duty. The point of the mode is the ceiling. |
| `MAX_SPEED_TEST_COUNTDOWN_BLINKS` | 3 | CHOSEN | Slow blinks before the dash starts. |
| `MAX_SPEED_TEST_COUNTDOWN_MS` | 700 | CHOSEN | On-time of one countdown blink. |
| `MAX_SPEED_TEST_BRAKE_HOLD_S` | 1.5 | CHOSEN | Brake held before reporting. |
| `MAX_SPEED_TEST_MAX_DURATION_S` | 20.0 | CHOSEN | Runaway guard. A bad argument must not leave the motors running across the room. |
| `MAX_SPEED_SAMPLE_INTERVAL_MS` | 20 | CHOSEN | Encoder poll period during the dash. |
| `MAX_SPEED_SAMPLE_LIMIT` | 1200 | CHOSEN | Pre-allocated sample slots. Allocated before the motors start, because allocating inside a timing loop invites a garbage collection pause that lands in the numbers. |
| `MAX_SPEED_RAMP_SMOOTH_SAMPLES` | 5 | CHOSEN | Samples averaged into one velocity point. |
| `MAX_SPEED_RAMP_PLATEAU_FRACTION` | 0.98 | CHOSEN | Fraction of terminal speed that counts as the ramp being over. |
| `MAX_SPEED_TABLE_ROW_MS` | 100 | CHOSEN | One printed table row per this much time. |
| `MAX_SPEED_TABLE_MIN_ROWS` | 20 | CHOSEN | Print every sample rather than fall below this many rows. |

## Mode 5, the lap soak

| Constant | Value | Class | Provenance |
|---|---|---|---|
| `SOAK_LAPS` | 30 | CHOSEN | About 22 m of driving on a 3x3 perimeter, which turns a per-move bias too small to see into an offset a tape reads off the floor. |
| `SOAK_DRIVE_POWER` | 0.40 | CHOSEN | Below the cruise duty on purpose: the first question is whether the robot holds a line at all. Do not go far below it, because the deadband is unmeasured. |
| `SOAK_TURN_POWER` | 0.40 | CHOSEN | Held equal to `TURN_DUTY_POWER`. Turns are not slowed with the straights. |
| `SOAK_ABORT_POLL_S` | 0.05 | CHOSEN | Button poll while settling between laps. The only way to stop a 30 lap run without pulling the battery. |
| `SOAK_SENSOR_SAMPLES` | 8 | CHOSEN | ADC reads averaged into one sensor value, to beat noise. |
| `SOAK_EMITTER_SETTLE_S` | 0.002 | PROVISIONAL | Emitter settle before a read. The boundary contract says ~75 us; this is 2 ms, generous by 26x and never checked against the phototransistor's real rise time. |
| `SOAK_TICK_DROPOUT_FRACTION` | 0.5 | CHOSEN | Below this fraction of the median lap is reported as an encoder dropout, not a slow lap. Generous, because battery sag over 30 laps is real. |
| `SOAK_SLOWDOWN_WARN_PERCENT` | -5.0 | CHOSEN | First-to-last tick change that gets reported as battery sag. |

## Mode 6, follow route

| Constant | Value | Class | Provenance |
|---|---|---|---|
| `FOLLOW_ROUTE_LAPS` | 1 | CHOSEN | Laps per run. Above 1 accumulates drift. |
| `INTER_LAP_SETTLE_S` | 1.0 | CHOSEN | Brake held between laps. |

## The motor trace

| Constant | Value | Class | Provenance |
|---|---|---|---|
| `MOTOR_LOG_POWER_EPSILON` | 0.001 | CHOSEN | Commanded powers closer than this count as unchanged. Guards against a float round-trip emitting a record that says nothing. |

## Simulation

| Constant | Value | Class | Provenance |
|---|---|---|---|
| `SIM_TIMESTEP_S` | 0.01 | CHOSEN | Fixed timestep. The sim is deterministic in this step, not in wall-clock time. The renderer samples it and never sets it. |

## Sensors

Nothing converts an ADC reading into a sensed wall yet, so this whole block is
model, not measurement. It is what hardware calibration replaces.

| Constant | Value | Class | Provenance |
|---|---|---|---|
| `SENSOR_MOUNTS` | 3 mounts | PROVISIONAL | Mount positions and angles in the body frame. Origin unrecorded; not checked against the built chassis. |
| `SENSOR_RANGE_MM` | 250.0 | PROVISIONAL | Ray cap. Beyond it the sensor reads the floor. |
| `SENSOR_BACKGROUND_MM` | 240.0 | PROVISIONAL | Distance at or after which nothing is seen. |
| `SENSOR_ADC_FLOOR` | 200 | PROVISIONAL | Unlit background reading, 16-bit counts. |
| `SENSOR_ADC_CEILING` | 65535 | FIXED | 16-bit ADC saturation. A property of the hardware, not a choice. |
| `SENSOR_INTENSITY_SCALE` | 4.5e7 | PROVISIONAL | Counts x mm^2 in the `SCALE / (d + OFFSET)^2` law. |
| `SENSOR_DISTANCE_OFFSET_MM` | 15.0 | PROVISIONAL | Emitter-to-target standoff in the same law. |

## Grid and compass conventions

Definitions, not measurements. Changing one changes what north means.

| Constant | Class | Note |
|---|---|---|
| `DIRECTIONS` | FIXED | `("n", "e", "s", "w")`. The wall-tuple order depends on it. |
| `SIDE_DELTA` | FIXED | North is +y. |
| `OPPOSITE` | FIXED | Used by `mark_wall` to mirror a shared edge. |
| `WALL_INDEX` | DERIVED | Index of each side in `DIRECTIONS`. |
| `DELTA_SIDE` | DERIVED | `SIDE_DELTA` inverted. |
| `HEADING_RADIANS` | DERIVED | World-frame heading per side, matching `SIDE_DELTA`. |
| `START_POS` | FIXED | `(0, 0)`, the corner cell. The mouse starts facing north. |

## Paths

All CHOSEN, all built by `_package_path`, which returns a bare filename on the
Pico because `PACKAGE_DIR` is `""` there and MicroPython has no `os.path`.

| Constant | File | Note |
|---|---|---|
| `PACKAGE_DIR` | — | `""` on the Pico, the repository root on the PC. |
| `DEFAULT_MAZE` | `groundtruth.num` | Sim truth. Committed. |
| `SAVED_BELIEF_MAZE` | `belief.num` | Run artefact. Gitignored and untracked. |
| `SAVED_ROUTE` | `route.mmc` | Run artefact. Copy the fixture you mean to drive. |
| `MAZES_DIR` | `mazes/` | Committed fixtures. |
| `ROUTES_DIR` | `routes/` | Committed fixtures. |
| `MOTOR_LOG_PATH` | `motor_log.csv` | Run artefact. |
| `MAX_SPEED_LOG_PATH` | `max_speed_test.csv` | Run artefact, appended per run. |
| `MAX_SPEED_SAMPLE_LOG_PATH` | `max_speed_samples.csv` | Run artefact, appended per run. |
| `SOAK_LOG_PATH` | `lap_soak.csv` | Run artefact, one row per lap. |

## Render and editor

PC-only. `sim/renderer.py` and `sim/route_editor.py` are the only readers and
neither goes on the board. They live here so invariant 5 holds without an
exception, not because the Pico will ever read them. All CHOSEN unless marked.

**Scale:** `PX_PER_MM` (0.25) is a FALLBACK only. The Renderer picks its own
scale per maze and stores it on the instance, so pixels stay inside the
renderer. Reading `PX_PER_MM` outside `sim/renderer.py` is a bug.
`TILE_PX` is DERIVED from it and `MM_PER_CELL`.

`RENDER_TARGET_WINDOW_PX` 720, `RENDER_MIN_TILE_PX` 24, `RENDER_MAX_TILE_PX` 160,
`RENDER_MARGIN_PX` 10, `RENDER_FPS` 60, `RENDER_PATH_STEP_DELAY_S` 0.05,
`RENDER_DONE_STEP_DELAY_S` 0.025, `RENDER_MOUSE_OUTLINE_PX` 2.

**Colours,** all RGB triples: `RENDER_BACKGROUND`, `RENDER_WALL_KNOWN`,
`RENDER_WALL_UNKNOWN`, `RENDER_TILE_DONE`, `RENDER_TILE_PATH`,
`RENDER_MOUSE_BODY`, `RENDER_MOUSE_NOSE`, `RENDER_TILE_START`,
`RENDER_TILE_END`, `RENDER_TILE_REJECT`, `RENDER_HEADING_ARROW`,
`RENDER_ROUTE_LINE`, `RENDER_ROUTE_LABEL`, `RENDER_END_RING`,
`RENDER_HUD_BACKGROUND`, `RENDER_HUD_TEXT`.

**Route drawing,** so a route shows its ORDER and not just which cells it
visits: `RENDER_ROUTE_LINE_PX` 5, `RENDER_ROUTE_ARROW_FRACTION` 0.16,
`RENDER_ROUTE_LABEL_MIN_TILE_PX` 56, `RENDER_ROUTE_LABEL_FONT_FRACTION` 0.2,
`RENDER_HEADING_ARROW_PX` 3, `RENDER_END_RING_PX` 5, `RENDER_END_RING_INSET` 0.22.

**Status bar:** `RENDER_HUD_PX` 54, `RENDER_HUD_FONT_PX` 15,
`RENDER_HUD_LINE_PX` 19.

**Editor:** `ROUTE_EDITOR_REJECT_FLASH_S` 0.6,
`ROUTE_EDITOR_DEFAULT_COLS` 3 and `ROUTE_EDITOR_DEFAULT_ROWS` 3 (the physical
test maze), `ROUTE_EDITOR_START_HEADING` `"n"`.

## Before and after a bench run

Mode 4's `calibrate()` reports new numbers for the MEASURED set. It prints them;
it does not write them. When you promote one:

1. Edit `config.py`.
2. Recompute the pivot product above, because distance and turn error cancel.
3. Update the row here, with the date and the method.
4. Write the log entry. A MEASURED constant with no log entry is a PROVISIONAL
   one wearing a better label.

## Known contradictions, found while writing this

- `BODY_LENGTH_MM`, `WALL_LENGTH_MM` and `WALL_WIDTH_MM` have no reader in the
  codebase at all. They are documentation that happens to be executable.
