# Body-language metrics (M4)

Every number the mock interviewer's camera produces, how it is computed, and the threshold that turns it
into feedback. All thresholds live in one file, `frontend/src/vision/thresholds.ts`;
`backend/services/interview/nonverbal.py` keeps the same values, and a shared fixture
(`frontend/src/vision/__fixtures__/answers.json`) is checked by both test suites so the browser and the
server always agree.

**What it is not.** No emotion, personality, identity, age, gender or appearance is inferred. Every metric
is geometry on landmarks (angles, distances, speeds) or a facial-muscle level, measured against the user's
own baseline. Body language is 30% of the readiness score. It coaches habits; it does not judge people.

**Privacy.** The video never leaves the browser. MediaPipe runs on the user's device (WASM, GPU with CPU
fallback); frames are discarded as soon as they are measured. Only one small `NonVerbalSample` per second
is sent with the answer. The user can turn the camera off at any time (verbal-only mode) or hide the
landmark overlay.

## Pipeline

| Step | Where | What |
|---|---|---|
| Landmarks | `vision/landmarker.ts` | MediaPipe **Face Landmarker** (478 points, 52 blendshapes, head transform matrix) every frame; **Pose Landmarker lite** (33 points) and **Hand Landmarker** (21 points per hand, up to 2 hands) on alternate frames. ~15 fps. Models and WASM are served from `frontend/public/`, so it works offline |
| Per-frame geometry | `vision/metrics.ts` | Head angles, eye direction, nose position, shoulder line, lean, hand shape and speed, face-muscle levels, nods |
| Baseline | `Calibrator` in `vision/aggregate.ts` | Learns the user's "looking at the screen" head angle and eye direction, and their neutral face, from the ~3 s before each answer (median, clamped). Frozen while the answer is recorded |
| 1-second summary | `summarizeSecond` | One `NonVerbalSample` per second (`backend/schemas/interview.py`) |
| Per-answer metrics | `analyzeAnswer` (browser, live gauges) and `analyze_answer` (server, the stored result) | `NonVerbalMetrics` + the five sub-scores |
| Coaching notes | `nonverbal.coaching_notes` + `backend/prompts/coaching_notes.md` | 2-3 kind, concrete notes from the LLM; rule-based notes when no LLM is available |

## Per-frame measurements

| Measure | Formula |
|---|---|
| Head yaw / pitch / roll | Euler angles of the rotation part of the face transform matrix (column-major, columns normalised to remove scale) |
| Eye direction | From the eyeLook blendshapes: `gazeX = ((eyeLookOutLeft − eyeLookInLeft) + (eyeLookInRight − eyeLookOutRight)) / 2`, `gazeY = mean(eyeLookUp) − mean(eyeLookDown)`; each −1..1 |
| Nose position | Face landmark 1, normalised image coordinates |
| Shoulder tilt | Angle of the line between pose landmarks 11 and 12 (x scaled by the video aspect ratio), folded to −90..90° |
| Lean | Distance from pose nose (0) to the shoulder midpoint ÷ shoulder width |
| Hand shape | Per finger: straight if tip-to-wrist > 1.2 × knuckle(PIP)-to-wrist; curled if tip-to-wrist < 1.3 × base-knuckle(MCP)-to-wrist. Open hand = 3+ straight fingers; fist = all four curled |
| Palm speed | Palm centre (mean of hand landmarks 0, 5, 9, 13, 17) movement ÷ seconds ÷ shoulder width, matched to the nearest hand of the previous frame, smoothed (α = 0.4) |
| Finger speed | Fingertip movement relative to the palm centre, same units and smoothing |
| Smile | Mean of mouthSmileLeft/Right, minus the user's neutral level |
| Tension | Strongest of browDown, noseSneer, mouthPress, mouthFrown (each a left/right mean) above the user's neutral level |
| Nod | Head pitch moves ≥ 5° away and returns to within 2° in ≤ 1.2 s (0.5 s cooldown). A look-down that stays down is not a nod |

Pose wrists are deliberately **not** used: with hands below the desk the pose model still guesses wrist
positions, often on the shoulders. Hands come only from the hand model, which reports hands that are there.

## Per-second rules

| Rule | Threshold |
|---|---|
| Eye contact (per frame) | Head within **±15°** of the baseline (yaw and pitch) **and** eyes within **±0.3** of the baseline gaze. `eye_contact_frac` = share of the second's frames |
| Hand action (per hand, per frame), in priority order | Palm in the face box (+10%): **covering_mouth** if in its lower 40%, else **touching_face**; palm within 50% of the face size around/above it: **touching_head**; finger speed > 0.6 with palm speed < 0.5: **fiddling**; palm speed > 0.5 without an open hand: **restless**; **fist**; open hand moving ≥ 0.15: **gesturing**; otherwise **resting** |
| Hand action (per second) | A distracting action wins if seen on ≥ 1/3 of the frames with hands; else gesturing or resting, whichever is more common |
| Out of frame | No face, or nose outside x 0.08-0.92 / y 0.05-0.95 |
| Tilted | \|shoulder tilt\| > **8°** |
| Slouching | Nose lower than 0.65 of the frame height, or lean < **0.8 ×** the answer's baseline lean (median of its first 3 seconds with shoulders) |
| Tense second | Tension ≥ **0.15** above neutral |
| Smiling second | Smile ≥ **0.20** above neutral |

## Per-answer metrics and score

| Metric | Formula |
|---|---|
| `eye_contact_pct` | 100 × mean of `eye_contact_frac` |
| `head_stability` | var(nose x) + var(nose y) over seconds with a face |
| `posture_flags` | slouching if ≥ 25% of seconds; leaning_out_of_frame if ≥ 15%; shoulders_tilted if ≥ 25% |
| `fidget_pct` | 100 × share of seconds with a distracting hand action |
| `hand_actions` | Share of seconds (0-100) for each hand action seen |
| `expression_label` | **tense** if ≥ 25% of face seconds are tense (and at least as many as smiling); **engaged** if ≥ 20% are smiling; else neutral |
| `nod_count` | Number of nods |

**Body-language score (0-100)** = 0.35 × eye contact + 0.25 × posture + 0.20 × hands + 0.10 × head
stability + 0.10 × expression, where

- eye contact = `eye_contact_pct`
- posture = 100 × (1 − share of seconds out of frame, tilted or slouching)
- hands = 100 − `fidget_pct`
- head stability = 100 at a nose standard deviation ≤ 0.01, falling linearly to 0 at 0.06
- expression = engaged 100, neutral 75, tense 30

The weights are shown to the user in the gauge tooltip. Readiness = 0.70 × verbal + 0.30 × body language
(`backend/services/interview/scoring.py`); with the camera off, readiness is the verbal score.

## Calibration and tuning

The `/vision` page (camera playground) shows every raw value next to its threshold, live, and turns red
when a threshold is crossed. Tune `thresholds.ts` and the matching constants in `nonverbal.py` together,
then regenerate the shared fixture expectations and run both test suites:

```bash
cd frontend && npx vitest run src/vision
python -m pytest backend/tests/test_nonverbal.py -q
```

Calibrate on each team member (glasses, lighting, distance from the camera) and at the venue before the demo.
