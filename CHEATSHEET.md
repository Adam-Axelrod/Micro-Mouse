# Robot cheatsheet

Practical commands for driving the Gemini micromouse. For *why* things are the
way they are, see the root `CLAUDE.md` and `Logs/`; this file is only
"which command do I type".

---

## 1. Hardware truths (bench-confirmed 2026-08-01)

Established on the real board, not in the sim. Trust these over any comment
that disagrees.

| Fact | Evidence |
|---|---|
| pin 3 = left forward, pin 2 = left reverse | BT-2 raw-channel sweep |
| pin 4 = right forward, pin 5 = right reverse | BT-2 raw-channel sweep |
| `drive.drive_motors(+, +)` drives both wheels forward | BT-2 |
| Both PWM channels at 65535 = **brake** (stops dead, no coast) | BT-3 |
| Buttons: SW1 = pin 15 (mode selector: 1=explore, 2=speed run, 3=bench test), SW2 = pin 14 (mode execute), active low | BT-1 |
| Sensors respond to a wall: L +2289, F +4427, R +2292 counts | BT-6 |


---

## 2. Getting code onto the Pico

Minimal deployment set (`CLAUDE.md` §Dual-target). Anything importing `pygame`
or `geometry` must never go on the board:

```
main.py setup.py config.py drive.py maze.py explorer.py exploration.py
speed_run.py search_algorithms.py commands.py motor_log.py max_speed_test.py
lap_log.py clock.py diagnostic_encoders.py  +  belief.num  +  route.mmc
```

`diagnostic_encoders.py` is now part of the base set: `setup.py` loads it on
first encoder read. `route.mmc` is what modes 5 and 6 drive, so copy the route
you mean to run: the board has no editor. Add for hardware work: `bench_test.py` — `main.py` imports
it lazily, so the set above boots without it.

`drive.py` is the motor boundary: every mode drives through it. The whole `sim/`
directory is PC-only and must never go on the board.

With `mpremote` (the VS Code MicroPico extension does the same thing via its
"Upload project" command):

```bash
mpremote cp main.py setup.py config.py drive.py maze.py explorer.py exploration.py speed_run.py search_algorithms.py commands.py motor_log.py max_speed_test.py lap_log.py clock.py diagnostic_encoders.py belief.num route.mmc :
```

```bash
mpremote repl
```

```bash
mpremote fs ls
```

Ctrl-D in the REPL soft-reboots and re-runs `main.py`. Ctrl-C interrupts a
running script — **if the motors are spinning, this leaves them spinning**, so
follow it with the stop below.

---

## 3. Emergency stop

Type this at a genuine `>>>` prompt:

```python
import main; main.stop_motors()
```

`main.stop_motors` is an alias for `drive.stop_motors`, which is where the motor
contract actually lives. `import drive; drive.stop_motors()` does the same thing
and is one import lighter.

Note: if a script is sitting at an `input()` prompt, typing that line just
feeds it as *text* to the prompt — it does not execute. Interrupt first
(Ctrl-C), then run it.

---

## 4. Bench tests (`bench_test.py`)

```python
import bench_test
bench_test.run_all()      # all checks, dependency order
bench_test.summary()      # paste-back block of results
bench_test.reset_results()
```

Single checks: `bench_test.bt2_motor_polarity()` etc.

| | Check | Powered? |
|---|---|---|
| BT-0 | boot, pins, LEDs | no |
| BT-1 | buttons | no |
| BT-2 | motor polarity + pin map | **yes** |
| BT-3 | brake vs coast | **yes** |
| BT-4 | encoders, hand-roll | no |
| BT-5 | motor↔encoder pairing | **yes** |
| BT-6 | reflective sensors + distance curve | no |
| BT-7 | encoder counts per wheel rev | no |
| BT-8 | track width | no |

Powered checks demand you confirm the wheels are off the ground, cap every
pulse at 1.2 s / 0.45 duty, and always end in `drive.stop_motors()`.

Order matters: BT-2 before BT-5 (a pairing failure is ambiguous between dead
motor and dead encoder unless polarity is known), BT-7 before BT-8 (track
width is derived through `MM_PER_TICK`).

**Serial quirk:** output is buffered until the next input is consumed, so the
`-> raw channel ...` line often appears *after* the wheel has already moved.
The `[Enter]` pause immediately before each pulse is your cue to watch — not
the printed line.

### Deeper encoder fault-finding

```python
import bench_test
bench_test.monitor()          # hand-roll, watch counts
bench_test.channel_levels()   # which of A/B is pinned = the open line
bench_test.wiggle_watch()     # flex the board, catch intermittents
bench_test.spin_check()       # POWERED, wheels off the ground
bench_test.encoder_fault_menu() # interactive menu
```

---

## 5. Running the robot

On the Pico, `main.py` runs at boot. SW1 selects a mode, SW2 runs it. After
each SW1 press the onboard LED blinks the mode number, so you always know what
SW2 will start.

| Mode | LED blinks | What it does |
|---|---|---|
| 1 | 1 | Explorer — updates the belief, writes `belief.num` |
| 2 | 2 | Speed run — loads `belief.num`, flood-fills, drives it |
| 3 | 3 | Bench test — the BT-0..BT-8 bring-up checks |
| 4 | 4 | Max speed test — one 5.2 m dash at full duty (§5.1) |
| 5 | 5 | Lap soak — 30 logged laps of `route.mmc`, then drift (§5.2) |
| 6 | 6 | Follow route — drive `route.mmc` verbatim, N laps (§5.3) |

Boot lands on mode 1 and blinks once. Each SW1 press steps to the next mode and
blinks its number; mode 4 wraps back to mode 1. To reach mode 4 from boot,
press SW1 three times and count four blinks, then press SW2. Mode 5 wraps
back to mode 1.

> Exploration has **no hardware path today** — `read_walls` reads
> `groundtruth.num` (not deployed to the Pico) and returns all four sides. On
> hardware, use speed run with a hand-authored `belief.num`.

Every Pico run traces commanded motor powers to `motor_log.csv` automatically:
`main.py` opens the trace before dispatching a mode and closes it after. Starting
a mode straight from the REPL bypasses `main`, so `max_speed_test.run()` and
`speed_run.soak()` open the trace themselves. Anything else run by hand needs
`import drive; drive.start_trace(force=True)` first.

On the PC:

```bash
python3 main.py            # headless sim, speed run
python3 main.py --render   # with pygame
python3 main.py --step     # mode 1, exploration
python3 main.py --bench    # mode 3, bench test (Pico only)
python3 main.py --maxspeed # mode 4, max speed test
python3 main.py --soak      # mode 5, 30 logged laps of route.mmc
python3 main.py --soak --laps=5 --power=0.3   # shorter and slower
python3 main.py --follow    # mode 6, one lap of route.mmc
python3 main.py --log      # also write a motor trace (automatic on hardware)
```

Replay a hardware trace into the PC sim:

```bash
python3 sim/replay_log.py            # headless, prints the reconstructed pose
python3 sim/replay_log.py --render   # watch it
```

---

### 5.1 Max speed test (mode 4)

This is how `MAX_WHEEL_SPEED_MMS` gets a measured number behind it. Every
open-loop `F n` duration divides by that constant, and it has never been
measured.

Set up:

1. Mark a start line and a line 5.00 m away on a clear, flat floor.
2. Leave at least 0.7 m of run-off past the far mark. The robot targets
   5.2 m, and it will overshoot if it is faster than the constant claims.
3. Line the robot's nose up on the start line, pointing down the lane.
4. Select mode 4 (SW1 ×3, count four blinks) and press SW2.

What the LED does, in order:

| Signal | Meaning |
|---|---|
| 4 fast blinks | armed — mode 4 confirmed |
| 3 slow blinks, ~0.7 s each | countdown, get the stopwatch ready |
| **solid ON** | the motors are driving — **start the stopwatch** |
| off | the brake is on |
| 2 slow blinks | run complete, the robot has stopped |

Stop the stopwatch as the nose crosses the 5.00 m mark. Then measure how far
the nose actually travelled, start line to where it stopped, and hand both
numbers back:

```python
import max_speed_test
max_speed_test.calibrate(travelled_mm=5060, stopwatch_s=10.4)
```

That prints two constants from one dash:

**`MAX_WHEEL_SPEED_MMS`**, from the stopwatch over the marked 5 m. This is
ground speed. It depends on nothing already in `config.py`, which is exactly why
it is the reference every other number gets checked against.

**An encoder verdict**, from the ticks over the distance really covered. Both
constants it leans on are known: 1400 counts per revolution is fixed by the
gearbox, and the wheel is a ruler-confirmed 32 mm. So the implied diameter
should come back within a percent or two of 32.

It moves opposite to the tick count, because it is `travelled × 1400 / ticks`:

| Implied diameter | Meaning |
|---|---|
| ~32 mm | the encoder is honest, ticks are trustworthy |
| above 32 | too few ticks. Dropped edges, this board's known fault |
| below 32 | too many ticks. A wheel spun without carrying the robot |

BT-7's ~1306 counts implies a 34.3 mm wheel and BT-8's ~66 mm track is 12%
under the ruler. Both come off tick counts, both landed short, and a 32 mm wheel
cannot roll as 34.3. Treat a repeat of that signature as a dead giveaway that
the decoder is still losing edges.

The tick half needs the encoders to read, which on this board they mostly do
not. The dash and the stopwatch work regardless; the mode says so and carries on.

Cross-check the speed against where the nose stopped. Short of the 5.2 m mark
means `MAX_WHEEL_SPEED_MMS` is too high; past it, too low.

Each run appends a row to `max_speed_test.csv` on the Pico
(`power,assumed_speed_mms,target_distance_mm,commanded_s,measured_s,left_ticks,right_ticks`),
and `calibrate()` appends its results as a comment beneath. Copy it off with
`mpremote cp :max_speed_test.csv .`.

From the REPL you can vary the dash without re-flashing:

```python
import max_speed_test
max_speed_test.run()                    # 5.2 m at full duty
max_speed_test.run(distance_mm=3000)    # shorter lane
max_speed_test.run(power=0.55)          # at cruise duty instead
```

Note the acceleration bias: the robot starts from rest, so the time over the
first metre includes the ramp-up and the derived speed reads low. For the top
speed alone, start the robot about 0.5 m behind the start line and time only
the marked 5 m.

Beware the circular case. On the PC the sim both plans and simulates with
`MAX_WHEEL_SPEED_MMS`, so `python3 main.py --maxspeed` always lands exactly on
target. That checks the arithmetic and says nothing about the chassis.

### 5.3 Follow route (mode 6)

Drives `route.mmc` exactly as written, with no planning. Nothing about the
planner is involved, so a route driven wrongly is the drive layer's fault.

Draw one on the PC, then copy it over:

```bash
python3 sim/route_editor.py                    # 3x3 blank grid, the physical maze
python3 sim/route_editor.py --size 16x16       # any grid, no maze file needed
python3 sim/route_editor.py mazes/test_mazes/blank3x3.num   # walls from a file
mpremote cp route.mmc :
```

Click cells to build the route, `r` to rotate the start heading, `s` to save.
The window scales itself to the grid, so a 3x3 draws large cells and a 16x16
draws small ones.

**Place the robot as the header says.** `.mmc` verbs are egocentric, so the same
file drives a different shape from a different pose. The editor records the pose
it was drawn from, and mode 6 prints it before the motors arm:

```
# grid: 3x3
# start: 0 0 n
# goal: 0 0
```

A file with no header is driven from cell (0, 0) facing north, and mode 6 says so
rather than guessing silently. Redraw it to record a pose.

Laps are the maze-relevant drift test. Every lap should return the robot to its
start pose, so the offset after N laps is the accumulated open-loop error, turn
error included. §5.2 is the same drive, run long and logged.

```python
import speed_run; speed_run.follow(laps=10)
```

A route driven in laps must return to its start **cell AND heading**. A drawn
route does neither by default: `path_to_commands` derives turns from cell
transitions, so it always ends on a drive, and the last cell is wherever you
stopped clicking. Mode 6 refuses more than one lap of a route that does not close,
and says where it ends instead. Append the closing moves by hand — see
`routes/lap3x3.mmc` (the bare perimeter) and `routes/lap3x3_via_centre.mmc` (the
perimeter plus the centre cell, all nine cells of a 3x3).

### 5.2 Lap soak (mode 5)

Thirty laps of the route in `route.mmc`, logged lap by lap. A 3x3 perimeter lap is
about 0.72 m of driving, so thirty laps is ~22 m and turns a per-move bias too
small to see into an offset the tape reads off the floor. Unlike the sprint it
replaced, a lap cannot cancel its own error: the turns accumulate too.

Defaults: 30 laps at drive power 0.40, turns at 0.40. Slower than a speed run on
purpose — the first question is whether the robot holds a line at all. Press
either button between laps to abort.

**Before starting:**

1. Copy the route you mean to drive into `route.mmc`, or draw one (§5.3).
2. Place the robot at the **CENTRE** of the start cell the route names, not back
   against a wall. A half-cell offset at the start is a half-cell error for the
   whole run.
3. Mark the start pose: both wheel contact points **and** a heading line. Without
   the heading mark half the result is unreadable.

```python
import speed_run
speed_run.soak()                  # the default 30 laps of route.mmc
speed_run.soak(laps=5)            # a shorter first go
speed_run.soak(power=0.30)        # slower still
speed_run.soak(route_path="routes/lap3x3_via_centre.mmc")
speed_run.soak(retrace=True)      # drive an open route out and back
```

**An open route can be driven out and back.** `--retrace` (or `retrace=True`)
appends a U-turn, the path walked backwards, and a U-turn home, so any drawn route
becomes lappable without redrawing it. Know what it costs: retracing cancels its
own symmetric error, because an equal shortfall each way subtracts and every right
turn going out is a left turn coming back. The two U-turns per lap are what
accumulates, so a retrace lap chiefly measures the pivot. A route that closes on
its own geometry measures distance, turns and pivots together.

**Otherwise it refuses a route that does not close.** Thirty laps of a route ending two
cells from its start drives into a wall on lap 2, so mode 5 walks the verbs on the
grid first and will not arm the motors. It prints the cell and heading the route
really ends on. The saved editor route is the common case: four right turns close
the HEADING while the last cell is somewhere else entirely.

What to look for in the report:

| Reading | What it means |
|---|---|
| Heading residual the same sign every lap | a mistimed turn, not noise. Fix `TRACK_WIDTH_MM` or the turn power before anything else |
| Ticks per lap falling over the run | battery sag or a hot motor. Laps are a fixed DURATION, so fewer ticks is less distance |
| `ENCODER DROPOUT` on a lap | the intermittent channel. This is the fault a soak run exists to catch |
| Offset from the start mark | the one thing only the tape can tell you |

Every lap appends a row to `lap_soak.csv`:

```
lap,elapsed_s,left_ticks,right_ticks,d_left,d_right,turn_residual_deg,
left_lit,left_unlit,front_lit,front_unlit,right_lit,right_unlit
```

The trend survives an abort, because every row is flushed as it is written.

The six light columns are read while braked at the end of each lap, lit minus
unlit, at the same pose every time. They are there for the wall-distance work
that has not been done yet: thirty readings of one pose say how repeatable the
sensors are before anything trusts them to correct a heading. Both halves are
kept, because lit alone cannot tell a wall from the room lights changing.

---

## 6. Getting files off the Pico

The robot writes `motor_log.csv`, `max_speed_test.csv` and `lap_soak.csv` to its own
filesystem. On the Pico `config.PACKAGE_DIR` is empty, so everything sits at the
root and the remote path is just `:name.csv`.

### With the VS Code extension (MicroPico 4.3.4)

The download commands are hidden until you mount the board. Their `when` clause
is `resourceScheme == pico`, so with the Virtual File System off you only ever
see the upload half, which is why the extension looks write-only.

1. Command palette → **MicroPico: Toggle Virtual File System**. It reloads the
   window and closes any open vREPL.
2. The board appears in the Explorer as a folder called **Mpy Remote
   Workspace**. Open a file to read it in place, no copy needed.
3. Right-click a file → **Download file from Pico**.

That folder is **virtual**, backed by the `pico:` scheme. Nothing is created on
disk and there is nothing to add to `.gitignore`; `find` and `git status` will
both show you it does not exist. If it lists as empty, either the board really
has no files or the extension has not finished connecting. `mpremote fs ls`
settles which, but only once VS Code lets go of the port.

**MicroPico: Download project from Pico** pulls everything in one go. It will
overwrite your local `.py` files with whatever was last deployed, so use it on
an empty folder or not at all.

### With mpremote

```bash
mpremote devs                                   # which port the board is on
mpremote fs ls                                  # what it has written
mpremote cat :max_speed_test.csv                # read it without copying
mpremote cp :max_speed_test.csv .               # pull one file
mpremote cp :max_speed_test.csv :motor_log.csv .  # several at once
mpremote rm :max_speed_test.csv                 # start a fresh baseline
```

Keep runs from overwriting each other by pulling into a dated folder:

```bash
mkdir -p runs/$(date +%F) && mpremote cp :max_speed_test.csv runs/$(date +%F)/
```

Four things that actually go wrong:

**Only one program owns the serial port.** If the MicroPico extension is
connected, `mpremote` fails with "it may be in use by another program".
Disconnect in VS Code first, or just use the extension route above. Same for an
open Thonny or an `mpremote repl` in another terminal. `lsof | grep usbmodem`
names the process holding it.

**`mpremote` interrupts whatever is running.** It drops the board into the raw
REPL, so a `main.py` mid-run stops. That is usually what you want after a run,
but do not do it while the robot is driving.

**A log is only complete once it is closed.** `max_speed_test.csv` opens and
closes per row, so it is safe to pull at any time. `motor_log.csv` stays open
for the whole run and needs its `close()`, so pull it after the run ends, not
during.

**Do not `cp -r : .`** It would drag every `.py` on the board into the working
directory and overwrite your source with whatever was last deployed.

### Replaying a motor trace

The Pico has no renderer, so replay the trace into the PC sim. A gap between
where the replay ends and where the robot physically stopped **is the
measurement** of how wrong the motor model is — that is the tool's purpose.

```bash
mpremote cp :motor_log.csv .
python3 replay_log.py --render
```

---

## 7. Maze files

`.num` format: one line per cell, `x y n e s w` (1 = wall).

- `groundtruth.num` — sim truth, PC only, never deployed
- `belief.num` — what the robot thinks; **speed run reads this**

`belief.num` must exist on the Pico. If it is missing, the planner falls back
to `groundtruth.num`, which is not deployed — so the run dies with a
`FileNotFoundError`.

### Making a blank N×N maze

Maze size is read from the file, so any size works. The goal is
`(cols//2 - 1, rows//2 - 1)` — for 6×6 that is cell `(2, 2)`.

Write it under its own name — do **not** overwrite the repo's 16×16
`belief.num`:

```bash
python3 -c "import maze; m = maze.MazeStructure(cols=6, rows=6); maze.num_file_export('mazes/blank6x6.num', m.cells); print(m)"
```

Verify the planned route before driving it:

```bash
python3 -c "import maze, config, search_algorithms, commands; c,x,y = maze.num_file_import('mazes/blank6x6.num'); m = maze.MazeStructure(cells=c, cols=x, rows=y); r = search_algorithms.flood_fill(m, config.START_POS); print(r); print(commands.path_to_commands(r))"
```

Then deploy it *as* `belief.num`, which is the name speed run reads:

```bash
mpremote cp mazes/blank6x6.num :belief.num
```

A blank 6×6 gives `[(0,0),(0,1),(0,2),(1,2),(2,2)]` → `['F 2', 'R', 'F 2', 'H']`.
Verified in sim: lands 2.6 mm from the goal-cell centre.

### Route verbs (`commands.py`)

`F n` drive forward n cells · `L` / `R` pivot 90° · `U` 180° · `H` halt.

Executed as **open-loop timed PWM drives** derived from
`CRUISE_DUTY_POWER × MAX_WHEEL_SPEED_MMS`. Nothing is measured, nothing is
corrected. Expect real drift.

---

## 8. PC-side tests

```bash
python3 tests/run_all.py          # every division
python3 tests/run_all.py health   # logic | hardware | sim | health
```

`health` is the one to run after moving anything: it catches a call to a symbol
that moved, a deployment set that would not boot, and pygame escaping `sim/`.

Inline self-tests: `python3 maze.py`, `python3 explorer.py`,
`python3 search_algorithms.py`, `python3 commands.py`, `python3 motor_log.py`.
