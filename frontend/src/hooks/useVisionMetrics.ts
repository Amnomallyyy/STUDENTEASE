// Runs the vision pipeline on the webcam (or a replay video) at ~15 fps, keeps the live gauges
// updated once a second, and records NonVerbalSample[] between startAnswer() and stopAnswer().
// The Interview page sends the returned samples with POST /interview/answer. No frame ever
// leaves the browser: only the numbers in NonVerbalSample do.

import type { NormalizedLandmark } from "@mediapipe/tasks-vision";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  analyzeAnswer,
  Calibrator,
  expressionFromSamples,
  gazeState,
  isFidgetSecond,
  isOutOfFrame,
  isSlouching,
  isTilted,
  mean,
  postureBaseline,
  SecondAggregator,
  smileLevel,
  tensionLevel,
  worstAction,
  type AnswerAnalysis,
  type ProcessedFrame,
} from "../vision/aggregate";
import { loadLandmarkers, type Delegate, type Landmarkers } from "../vision/landmarker";
import { classifyHand, extractFace, extractHands, extractPose, HandTracker, NodDetector } from "../vision/metrics";
import { clearOverlay, drawOverlay } from "../vision/overlay";
import { THRESHOLDS } from "../vision/thresholds";
import type {
  GazeState,
  HandAction,
  LiveVisionState,
  NonVerbalSample,
  PoseFrame,
  PostureFlag,
  VisionDebug,
} from "../vision/types";

export type VisionStatus = "idle" | "loading-models" | "starting-camera" | "running" | "error";

export interface VisionOptions {
  /** Turn the camera and models on. Default true. */
  enabled?: boolean;
  /** "camera" (default) or a video URL to replay through the same pipeline (stage fallback). */
  source?: "camera" | string;
  /** Target processing rate. Default 15. */
  fps?: number;
  /** Draw the landmark overlay. Default true. */
  overlay?: boolean;
}

export interface VisionController {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  status: VisionStatus;
  error: string | null;
  delegate: Delegate | null;
  live: LiveVisionState;
  /** Raw numbers for threshold tuning, refreshed once a second. */
  debug: VisionDebug | null;
  recording: boolean;
  /** Running per-answer metrics while recording; the final value after stopAnswer(). */
  answer: AnswerAnalysis | null;
  startAnswer(): void;
  /** Ends the answer and returns its 1 Hz samples for POST /interview/answer. */
  stopAnswer(): NonVerbalSample[];
  /** Re-learn where "looking at the screen" is and the neutral face (e.g. after the user moves the laptop). */
  recalibrate(): void;
}

const EMPTY_LIVE: LiveVisionState = {
  gazeNow: null,
  eyeContactRecentPct: null,
  postureIssue: null,
  fidgetRecentPct: null,
  expression: null,
  handsInView: 0,
  handAction: null,
  faceDetected: false,
  calibrated: false,
  fps: 0,
};

export function useVisionMetrics(options: VisionOptions = {}): VisionController {
  const { enabled = true, source = "camera", fps = 15, overlay = true } = options;

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [status, setStatus] = useState<VisionStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [delegate, setDelegate] = useState<Delegate | null>(null);
  const [live, setLive] = useState<LiveVisionState>(EMPTY_LIVE);
  const [debug, setDebug] = useState<VisionDebug | null>(null);
  const [recording, setRecording] = useState(false);
  const [answer, setAnswer] = useState<AnswerAnalysis | null>(null);

  // Pipeline state lives in a ref: it changes 15 times a second and must not re-render React.
  const pipe = useRef(newPipeline());
  const overlayRef = useRef(overlay);
  overlayRef.current = overlay;

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let stream: MediaStream | null = null;
    let stopLoop = () => {};
    const video = videoRef.current;
    if (!video) return;
    pipe.current = newPipeline();

    (async () => {
      try {
        setError(null);
        setStatus("loading-models");
        const lm = await loadLandmarkers();
        if (cancelled) return;
        setDelegate(lm.delegate);

        setStatus("starting-camera");
        if (source === "camera") {
          stream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
            audio: false,
          });
          if (cancelled) return stopStream(stream);
          video.srcObject = stream;
        } else {
          video.srcObject = null;
          video.src = source;
          video.loop = true;
        }
        video.muted = true;
        video.playsInline = true;
        await video.play();
        if (cancelled) return;
        setStatus("running");
        stopLoop = runLoop(video, lm, fps);
      } catch (err) {
        if (!cancelled) {
          setError(describeError(err));
          setStatus("error");
        }
      }
    })();

    function runLoop(v: HTMLVideoElement, lm: Landmarkers, targetFps: number): () => void {
      const minGap = 1000 / targetFps;
      let last = 0;
      let handle = 0;
      let stopped = false;
      const useRvfc = "requestVideoFrameCallback" in v;
      const schedule = () => {
        if (stopped) return;
        handle = useRvfc ? v.requestVideoFrameCallback(tick) : requestAnimationFrame(tick);
      };
      const tick = () => {
        const now = performance.now();
        if (now - last >= minGap && v.readyState >= 2 && v.videoWidth > 0) {
          last = now;
          try {
            processFrame(v, lm, now);
          } catch (err) {
            console.error("vision frame failed", err);
          }
        }
        schedule();
      };
      schedule();
      return () => {
        stopped = true;
        if (useRvfc) v.cancelVideoFrameCallback(handle);
        else cancelAnimationFrame(handle);
      };
    }

    function processFrame(v: HTMLVideoElement, lm: Landmarkers, now: number) {
      const p = pipe.current;
      p.frameIndex += 1;
      const aspect = v.videoWidth / v.videoHeight;

      // Face on every frame; pose and hands take turns, so each frame runs two models.
      const faceRes = lm.detectFace(v, now);
      const faceLm = faceRes.faceLandmarks[0];
      const face = extractFace(faceLm, faceRes.faceBlendshapes[0], faceRes.facialTransformationMatrixes[0]);

      let pose: PoseFrame | null | undefined;
      let hands: ProcessedFrame["hands"];
      if (p.frameIndex % 2 === 0) {
        const poseRes = lm.detectPose(v, now);
        p.lastPoseLm = poseRes.landmarks[0];
        pose = extractPose(p.lastPoseLm, aspect);
        if (pose?.shoulders) p.shoulderWidth = pose.shoulderWidth;
        p.debug.shoulderTiltDeg = pose?.shoulders ? pose.shoulderTiltDeg : null;
        p.debug.lean = pose?.shoulders ? pose.lean : null;
      } else {
        const handRes = lm.detectHands(v, now);
        const found = extractHands(handRes.landmarks, handRes.handedness, aspect);
        const motion = p.handTracker.update(now, found, p.shoulderWidth);
        const actions = found.map((h, i) => classifyHand(h, motion[i], face));
        const palms = motion.map((m) => m.palm).filter((x): x is number => x !== null);
        const fingers = motion.map((m) => m.fingers).filter((x): x is number => x !== null);
        p.lastHandsLm = handRes.landmarks;
        p.lastHandActions = actions;
        hands = { count: found.length, speed: palms.length ? Math.max(...palms) : null, action: worstAction(actions) };
        Object.assign(p.debug, {
          hands: found.length,
          handSpeed: palms.length ? Math.max(...palms) : null,
          fingerSpeed: fingers.length ? Math.max(...fingers) : null,
          extendedFingers: found.length ? Math.max(...found.map((h) => h.extendedFingers)) : null,
          handAction: hands.action,
        });
      }

      p.calibrator.observe(face);
      const baseline = p.calibrator.baseline;
      const gaze: GazeState | null = face ? gazeState(face, baseline) : null;
      const frame: ProcessedFrame = { t: now, face, pose, hands, nod: p.nods.update(now, face?.pitchDeg ?? null) };

      if (face) {
        const b = baseline;
        const tension = tensionLevel(face, b);
        Object.assign(p.debug, {
          yawDeg: face.yawDeg - (b?.yawDeg ?? 0),
          pitchDeg: face.pitchDeg - (b?.pitchDeg ?? 0),
          gazeX: face.gazeX - (b?.gazeX ?? 0),
          gazeY: face.gazeY - (b?.gazeY ?? 0),
          smile: smileLevel(face, b),
          tension: tension.level,
          tensionSource: tension.source,
          noseY: face.noseY,
        });
      } else {
        Object.assign(p.debug, { yawDeg: null, pitchDeg: null, gazeX: null, gazeY: null, smile: null, tension: null, tensionSource: null, noseY: null });
      }

      // Live gauges: one sample per second since the camera started.
      p.liveAgg ??= new SecondAggregator(now);
      const liveSample = p.liveAgg.push(frame, baseline);
      if (liveSample) {
        p.liveSamples.push(liveSample);
        if (p.liveSamples.length > 30) p.liveSamples.shift();
        if (!p.liveLeanBaseline && p.liveSamples.filter((s) => s.pose_detected).length >= THRESHOLDS.postureBaselineSeconds)
          p.liveLeanBaseline = postureBaseline(p.liveSamples);
        p.debug.leanBaseline = p.liveLeanBaseline;
        setDebug({ ...p.debug });
      }

      // Answer recording.
      if (p.answerAgg) {
        const s = p.answerAgg.push(frame, baseline);
        if (s) {
          p.answerSamples.push(s);
          setAnswer(analyzeAnswer(p.answerSamples));
        }
      }

      // FPS counter.
      p.fpsFrames += 1;
      if (now - p.fpsSince >= 1000) {
        p.fps = Math.round((p.fpsFrames * 1000) / (now - p.fpsSince));
        p.fpsFrames = 0;
        p.fpsSince = now;
      }

      if (liveSample || gaze !== p.lastGaze) {
        p.lastGaze = gaze;
        setLive(liveState(p, gaze, face !== null));
      }

      const canvas = canvasRef.current;
      if (canvas) {
        if (canvas.width !== v.videoWidth) canvas.width = v.videoWidth;
        if (canvas.height !== v.videoHeight) canvas.height = v.videoHeight;
        if (overlayRef.current)
          drawOverlay(canvas, { face: faceLm, pose: p.lastPoseLm, hands: p.lastHandsLm, handActions: p.lastHandActions, gaze });
        else clearOverlay(canvas);
      }
    }

    return () => {
      cancelled = true;
      stopLoop();
      stopStream(stream);
      if (video) {
        video.pause();
        video.srcObject = null;
        video.removeAttribute("src");
        video.load();
      }
      if (canvasRef.current) clearOverlay(canvasRef.current);
      setStatus("idle");
      setLive(EMPTY_LIVE);
      setDebug(null);
      setRecording(false);
    };
  }, [enabled, source, fps]);

  const startAnswer = useCallback(() => {
    const p = pipe.current;
    p.calibrator.freeze();
    p.answerAgg = new SecondAggregator(performance.now());
    p.answerSamples = [];
    setAnswer(null);
    setRecording(true);
  }, []);

  const stopAnswer = useCallback((): NonVerbalSample[] => {
    const p = pipe.current;
    if (!p.answerAgg) return [];
    const last = p.answerAgg.flush(p.calibrator.baseline);
    if (last) p.answerSamples.push(last);
    const samples = p.answerSamples;
    p.answerAgg = null;
    p.answerSamples = [];
    p.calibrator.reset(); // re-learn while the user reads the next question
    setAnswer(analyzeAnswer(samples));
    setRecording(false);
    return samples;
  }, []);

  const recalibrate = useCallback(() => {
    const p = pipe.current;
    p.calibrator.reset();
    if (p.answerAgg) p.calibrator.freeze();
    p.liveLeanBaseline = 0;
  }, []);

  return { videoRef, canvasRef, status, error, delegate, live, debug, recording, answer, startAnswer, stopAnswer, recalibrate };
}

function newPipeline() {
  return {
    frameIndex: 0,
    calibrator: new Calibrator(),
    handTracker: new HandTracker(),
    nods: new NodDetector(),
    shoulderWidth: 0,
    lastPoseLm: undefined as NormalizedLandmark[] | undefined,
    lastHandsLm: [] as NormalizedLandmark[][],
    lastHandActions: [] as (HandAction | null)[],
    liveAgg: null as SecondAggregator | null,
    liveSamples: [] as NonVerbalSample[],
    liveLeanBaseline: 0,
    answerAgg: null as SecondAggregator | null,
    answerSamples: [] as NonVerbalSample[],
    lastGaze: null as GazeState | null,
    fps: 0,
    fpsFrames: 0,
    fpsSince: performance.now(),
    debug: {
      yawDeg: null,
      pitchDeg: null,
      gazeX: null,
      gazeY: null,
      smile: null,
      tension: null,
      tensionSource: null,
      hands: 0,
      handSpeed: null,
      fingerSpeed: null,
      extendedFingers: null,
      handAction: null,
      shoulderTiltDeg: null,
      lean: null,
      leanBaseline: 0,
      noseY: null,
    } as VisionDebug,
  };
}

function liveState(p: ReturnType<typeof newPipeline>, gazeNow: GazeState | null, faceDetected: boolean): LiveVisionState {
  const recent = p.liveSamples.slice(-THRESHOLDS.recentWindowSeconds);
  const latest = recent[recent.length - 1];
  let postureIssue: PostureFlag | null = null;
  if (latest) {
    if (isOutOfFrame(latest)) postureIssue = "leaning_out_of_frame";
    else if (isSlouching(latest, p.liveLeanBaseline)) postureIssue = "slouching";
    else if (isTilted(latest)) postureIssue = "shoulders_tilted";
  }
  return {
    gazeNow,
    eyeContactRecentPct: recent.length ? Math.round(100 * mean(recent.map((s) => s.eye_contact_frac))) : null,
    postureIssue,
    fidgetRecentPct: recent.length ? Math.round((100 * recent.filter(isFidgetSecond).length) / recent.length) : null,
    expression: recent.some((s) => s.face_detected) ? expressionFromSamples(recent) : null,
    handsInView: p.debug.hands,
    handAction: latest?.hand_action ?? null,
    faceDetected,
    calibrated: p.calibrator.baseline !== null,
    fps: p.fps,
  };
}

function stopStream(stream: MediaStream | null): void {
  stream?.getTracks().forEach((t) => t.stop());
}

function describeError(err: unknown): string {
  const name = err instanceof DOMException ? err.name : "";
  if (name === "NotAllowedError") return "Camera permission was denied. Allow camera access to get body-language feedback, or continue in verbal-only mode.";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "No camera was found. You can continue in verbal-only mode.";
  if (name === "NotReadableError") return "The camera is being used by another app. Close it and try again.";
  return `Body-language analysis could not start: ${err instanceof Error ? err.message : String(err)}`;
}
