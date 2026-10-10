// Loads MediaPipe Face, Pose (lite) and Hand Landmarkers once per page. WASM and models are served
// from public/ (no CDN), so the demo still works on a dead venue connection. GPU first, CPU fallback.

import { FaceLandmarker, FilesetResolver, HandLandmarker, PoseLandmarker } from "@mediapipe/tasks-vision";
import type { FaceLandmarkerResult, HandLandmarkerResult, PoseLandmarkerResult } from "@mediapipe/tasks-vision";
import { THRESHOLDS } from "./thresholds";

const BASE = import.meta.env.BASE_URL;
const WASM_PATH = `${BASE}mediapipe-wasm`;
const FACE_MODEL = `${BASE}models/face_landmarker.task`;
const POSE_MODEL = `${BASE}models/pose_landmarker_lite.task`;
const HAND_MODEL = `${BASE}models/hand_landmarker.task`;

export type Delegate = "GPU" | "CPU";

export interface Landmarkers {
  delegate: Delegate;
  detectFace(video: HTMLVideoElement, timestampMs: number): FaceLandmarkerResult;
  detectPose(video: HTMLVideoElement, timestampMs: number): PoseLandmarkerResult;
  detectHands(video: HTMLVideoElement, timestampMs: number): HandLandmarkerResult;
}

let loading: Promise<Landmarkers> | null = null;

/** Shared for the page lifetime: the models take a few seconds to load and React may mount twice. */
export function loadLandmarkers(): Promise<Landmarkers> {
  loading ??= create().catch((err) => {
    loading = null; // allow a retry after a failure
    throw err;
  });
  return loading;
}

async function create(): Promise<Landmarkers> {
  const fileset = await FilesetResolver.forVisionTasks(WASM_PATH);
  try {
    return await build(fileset, "GPU");
  } catch (gpuError) {
    console.warn("MediaPipe GPU delegate failed, falling back to CPU", gpuError);
    return build(fileset, "CPU");
  }
}

async function build(fileset: Awaited<ReturnType<typeof FilesetResolver.forVisionTasks>>, delegate: Delegate) {
  const [face, pose, hands] = await Promise.all([
    FaceLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: FACE_MODEL, delegate },
      runningMode: "VIDEO",
      numFaces: 1,
      outputFaceBlendshapes: true,
      outputFacialTransformationMatrixes: true,
    }),
    PoseLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: POSE_MODEL, delegate },
      runningMode: "VIDEO",
      numPoses: 1,
    }),
    HandLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: HAND_MODEL, delegate },
      runningMode: "VIDEO",
      numHands: 2,
      minHandDetectionConfidence: THRESHOLDS.minHandConfidence,
      minHandPresenceConfidence: THRESHOLDS.minHandConfidence,
    }),
  ]);

  // Each task rejects a timestamp that is not strictly greater than its previous one.
  const last = { face: -1, pose: -1, hands: -1 };
  const next = (k: keyof typeof last, ts: number) => (last[k] = Math.max(ts, last[k] + 1));
  return {
    delegate,
    detectFace: (video, ts) => face.detectForVideo(video, next("face", ts)),
    detectPose: (video, ts) => pose.detectForVideo(video, next("pose", ts)),
    detectHands: (video, ts) => hands.detectForVideo(video, next("hands", ts)),
  } satisfies Landmarkers;
}
