# Robot cheatsheet

Practical commands for driving the Gemini micromouse. For *why* things are the
way they are, see the root `CLAUDE.md` / `DECISIONS.md`; this file is only
"which command do I type".

---

## 1. Hardware truths (bench-confirmed 2026-08-01)

Established on the real board, not in the sim. Trust these over any comment
that disagrees.

| Fact | Evidence |
|---|---|
| pin 3 = left forward, pin 2 = left reverse | BT-2 raw-channel sweep |
| pin 4 = right forward, pin 5 = right reverse | BT-2 raw-channel sweep |
| `drive_motors(+, +)` drives both wheels forward | BT-2 |
| Both PWM channels at 65535 = **brake** (stops dead, no coast) | BT-3 |
| Buttons: SW1 = pin 15 (mode selector: 1=explore, 2=speed run, 3=bench test), SW2 = pin 14 (mode execute), active low | BT-1 |
| Sensors respond to a wall: L +2289, F +4427, R +2292 counts | BT-6 |

**Still broken / unverified:**

- **Left encoder is dead** (broken J1 signal line, pins 8/9). The left *motor*
  is fine — BT-2 proved it turns. No closed-loop control is possible until
  this is repaired.
- Right encoder counts **negative** for forward, so `get_counts` negates it.
  The left side's sign is unverified — re-check after the J1 repair.
- `ENCODER_COUNTS_PER_WHEEL_REV` (config says 1400, one 150 mm sample said
  ~1306) and `TRACK_WIDTH_MM` (config says 70, a one-encoder pivot implied
  ~66) are both **still provisional**. Re-measure before trusting odometry.

---

## 2. Getting code onto the Pico

Minimal deployment set (`CLAUDE.md` §Dual-target). Anything importing `pygame`
or `geometry` must never go on the board:

```
main.py setup.py config.py maze.py explorer.py search_algorithms.py
commands.py motor_log.py  +  belief.num
```

Add for hardware work: `bench_test.py`, `diagnostic_encoders.py`.

With `mpremote` (the VS Code MicroPico extension does the same thing via its
"Upload project" command):

```bash
mpremote cp main.py setup.py config.py maze.py explorer.py search_algorithms.py commands.py motor_log.py belief.num :
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
pulse at 1.2 s / 0.45 duty, and always end in `stop_motors()`.

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

On the Pico, `main.py` runs at boot and picks its mode from the buttons:

- **LEFT / SW1** → exploration (updates belief, writes `belief.num`)
- **RIGHT / SW2** → speed run (loads `belief.num`, flood-fills, drives it)
- **no press** → defaults to speed run

> Exploration has **no hardware path today** — `read_walls` reads
> `groundtruth.num` (not deployed to the Pico) and returns all four sides. On
> hardware, use speed run with a hand-authored `belief.num`.

Every Pico run traces commanded motor powers to `motor_log.csv` automatically.

On the PC:

```bash
python3 main.py            # headless sim, speed run
python3 main.py --render   # with pygame
python3 main.py --step     # exploration (the PC's "left button")
python3 main.py --log      # also write a motor trace
```

---

## 6. Watching a hardware run afterwards

The Pico has no renderer, so replay the trace into the PC sim. A gap between
where the replay ends and where the robot physically stopped **is the
measurement** of how wrong the motor model is — that is the tool's purpose.

```bash
mpremote cp :motor_log.csv .
```

```bash
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
python3 tests/test_physics_sim.py
```

Inline self-tests: `python3 maze.py`, `python3 explorer.py`,
`python3 search_algorithms.py`, `python3 commands.py`.
