# Rat OS — AI Controller: Next Steps

Branch: `ai-controlled-mission`
Scope: hardening and follow-on work for `missions/AI_controlled.py` and `AI_controller_client.py`.

---

## 1. Sensor Sanity / Pre-Flight Check

Goal: never let the AI mission drive on a sensor that's silently broken. Two layers — a fast one-shot check before the mission commits to running, and a continuous check while it runs.

**Pre-flight (robot side, `missions/AI_controlled.py`, before the telemetry/LED/ultrasonic threads spin up):**
- [ ] On mission start, take a few quick ultrasonic reads (e.g. 3 back-to-back) before opening telemetry. If all return `-1` / timeout, abort into `ERROR` instead of arming motors — don't let a dead sensor pass as "just far away."
- [ ] Same pattern for IR (`Infrared.read_all_infrared()`) — confirm it returns without exception and isn't stuck at a constant value across the burst if that's a plausible failure mode for this board.
- [ ] Keep this bounded — total pre-flight time should be well under a second (a handful of reads at the ultrasonic's existing pace), not a new multi-second gate in front of every mission start.
- [ ] On failure: log clearly which sensor failed, skip arming motors/threads, return `False` (or drop straight to `ERROR` via an exception) — don't leave the robot in a half-initialized state.

**Continuous (robot side, inside the existing tick loop):**
- [ ] Reuse the existing staleness idea (`AI_DIST_STALE_S`, already fail-closed on stale distance) but extend it into an explicit **abort**, not just "treat as obstacle," if the sensor stays stale/erroring past some longer threshold (e.g. 5–10x the normal read interval) — that's a dead sensor, not a slow one.
- [ ] Route this through the existing `_complete(brain, status, reason)` path with a new status like `"SENSOR_FAULT"`, so the client sees it the same way it sees `STUCK`/`TIMEOUT`/`GOAL_REACHED`.
- [ ] Config: add something like `AI_SENSOR_FAULT_TIMEOUT_S` rather than hardcoding.

**Client side (`AI_controller_client.py`):** no action needed beyond what's already there — it already just watches the `status` field and exits non-zero on anything but `GOAL_REACHED`, so a new `SENSOR_FAULT` status is handled for free.

---

## 2. Camera in the Loop (Vision Model)

Goal: move from text-only/occasional-snapshot to a vision model actually influencing driving decisions, not just riding along in telemetry.

- [ ] Pick a first vision model to standardize on for this pass (llava is the current default in `config.py`/README — moondream was tried first but produced no action commands; good default to start with).
- [ ] Confirm `AI_CAMERA_RATE` vs `AI_LOOP_RATE` — right now snapshots are captured independently of the LLM loop cadence; decide whether the loop should wait for a fresh frame before calling Ollama, or just use whatever's most recent (current behavior).
- [ ] Prompt tuning: the current `SYSTEM_PROMPT_TEMPLATE` only mentions `[image attached]` as a text placeholder — worth testing whether the model needs more explicit instruction on what to look for (obstacles, the target object, etc.) once it's actually driving off the image instead of just receiving it.
- [ ] Bandwidth/latency check: measure real round-trip time with an image attached at `AI_CAMERA_SIZE`/`AI_CAMERA_JPEG_QUALITY` against `AI_OLLAMA_TIMEOUT` (60s) and `AI_LOOP_RATE` (1s) — vision calls are the most likely thing to blow past the loop rate.
- [ ] Decide fallback behavior if the vision call is slow/fails on a given tick: keep last action vs. STOP. (Current text-only path already just skips the tick and retries — confirm that's still the right call once frames are decision-relevant, not just descriptive.)

---

## 3. `./start_ai` Launcher Script

Goal: one command to launch `AI_controller_client.py` with pre-baked flags, matching `start_rat.sh`/`stop_rat.sh` conventions already in the repo.

- [ ] New config block (or extend the existing AI config block) for default launch args: `--host`, `--model`, `--loop-rate`, `--task`, and the goal flags (`--goal-distance-cm` / `--goal-ir` / `--goal-tolerance-cm` / `--max-duration-s`).
- [ ] `start_ai` (dev PC side, alongside `AI_controller_client.py`) reads those config defaults and execs `python AI_controller_client.py` with them — should still accept CLI overrides for a one-off run without editing config.
- [ ] Keep task text in config as a plain string default (e.g. `AI_DEFAULT_TASK`) so a demo run is just `./start_ai` with no args.
- [ ] Match existing shell script style/safety (`start_rat.sh`/`stop_rat.sh`) — same shebang conventions, same error handling expectations.

---

## 4. README Consolidation

Goal: one README, not two drifting out of sync.

Current state: there are literally two `README.md` files —
- `/README.md` (repo root) — 143 lines, stale. Still lists `missions/test.py` (no longer exists), has no mention of `camera_test.py`, `motion_indication_test.py`, `sensory_test.py`, or `AI_controlled.py`, and duplicates content (repo layout, start/stop, config) that the other file already covers.
- `/Rat/README.md` — 319 lines, actively maintained. This is the one that got the new "AI Controller" section on this branch, has the full mission list, TCP command reference, troubleshooting, etc.

- [ ] Keep `Rat/README.md` as the single canonical README — it's the more complete, more current one and the one already being kept in sync with code changes on this branch.
- [ ] Delete `/README.md` at the repo root (or replace it with a one-line pointer to `Rat/README.md` if GitHub's repo-landing-page behavior matters to you — root READMEs render on the repo homepage, `Rat/README.md` doesn't unless someone navigates into `Rat/`).
- [ ] While merging: root README's Hardware table (PCB version, LED count, controller hardware) isn't duplicated in `Rat/README.md` — pull that in before deleting so it isn't lost.
- [ ] Rewrite/expand `Rat/README.md`'s AI Controller section into the canonical quick-reference: usage, flags, wire format summary, safety model (onboard interlock + client-side secondary check), goal system.
- [ ] Retire `docs/AI_controlled.md` (or trim to historical/design-rationale only, clearly marked superseded) — it predates the real implementation and its command set/telemetry format no longer matches the code (no goal system, no bounded motion, no onboard interlock in that doc).
- [ ] While in there: `Rat/README.md`'s project structure / roadmap sections have their own small drifts from actual file layout worth reconciling (e.g. `obstacle_course.py` listed but not present on this branch).

---

## 5. TCP / Threading Hazard Pass

Goal: audit the AI mission's concurrency for the failure modes that don't show up in a demo but will eventually show up in the field.

Known-good already in place (for reference, not re-doing):
- Generation counters (`_generation`) guard against a stale thread from a previous run surviving a HALT-then-reselect.
- `on_stop()` closes what it owns; the ultrasonic thread owns and closes its own sensor to avoid a cross-thread GPIO close race.
- Heartbeat keeps the command socket alive across slow Ollama calls.

Things to specifically check:
- [ ] **Telemetry socket**: `_telemetry_loop` reconnects on `client_address` but never re-reads it once connected — confirm behavior if the dev PC's IP changes mid-session (reconnect on a new controller connecting) vs. just retrying the old IP.
- [ ] **Four background threads per mission run** (telemetry, snapshot, ultrasonic, LED) — confirm none of them can block past their own loop's `_generation`/`_initialized` check in a way that delays HALT responsiveness (the brain-level HALT is instant since it never touches these threads, but a thread that never notices `_initialized = False` leaks forever).
- [ ] **`_send_lock` in the client** — confirms sends are serialized between the main loop and the heartbeat thread; double check there's no window where a heartbeat interleaves mid-write with a real command (unlikely given the lock, worth a quick read-through to confirm no partial-write edge case).
- [ ] **Camera subprocess (`rpicam-still`)**: `_capture_jpeg` has an 8s timeout — confirm a timed-out/killed process doesn't leave a zombie or hold the camera device such that the *next* capture in the loop fails too.
- [ ] **Servo calls from `_dispatch`**: these are synchronous on the main tick thread — confirm none of them can block long enough to threaten HALT responsiveness the way the old synchronous ultrasonic read used to.
- [ ] Sweep for any remaining place a socket/thread reference could be read on one thread while being reassigned/closed on another without a lock (the ultrasonic-instance handoff was already called out and solved — check the same pattern doesn't exist elsewhere).

---

## 6. General Cleanup Pass

Goal: lean, not padded — pass over `missions/AI_controlled.py`, `AI_controller_client.py`, `common_hardware/motor.py`, and `rat_brain/control_receiver_server.py` (all touched on this branch) for:

- [ ] Comments that explain *why* stay; comments that just restate the line above them go.
- [ ] Any duplicated logic between the client's `_apply_safety` and the robot's `_obstacle_ahead`/`_nets_forward` — keep both (defense in depth is intentional) but make sure they can't silently drift out of sync (e.g. shared threshold constant, not two hardcoded numbers).
- [ ] Confirm `config.py`'s new AI block and the motor kickstart/reversal-settle block are logically grouped and not scattered — they were added at the end of the file across two separate diffs.
- [ ] Re-check that the `motor.py` forward/backward polarity flip + kickstart/reversal-settle logic (bundled into this branch but not AI-specific — affects every mission) is called out as its own change, not folded silently into "AI cleanup."
- [ ] Pass for dead code / TODOs left over from the design-doc stage now that the real implementation exists (e.g. `camera_test.py`'s `_led_pass()`/`_led_error()` TODO stubs, if still relevant here).
- [ ] Confirm log levels are sane for a running mission (e.g. INFO-per-tick chatter vs. WARNING for actual anomalies) — check nothing added on this branch spams DEBUG/INFO in the 50ms tick loop.
