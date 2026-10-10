// Mock interview screen (M3; M4 fills the centre), rendered inside M2's Shell at /interview.
// The role comes from ?role= (the chatbot's open_interview action), else the profile's target role.
// After every answer the shared profile is refreshed, so the Dashboard's readiness tile updates. Three zones: question + transcript on the left,
// webcam with landmark overlay in the centre, live speaking / STAR / body-language gauges on the right.
// After each answer: score card, STAR quotes, what to fix, coaching notes and the rewrite.
// After the last question: the readiness report.

import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import AnswerFeedback from "../components/interview/AnswerFeedback";
import LiveTranscript from "../components/interview/LiveTranscript";
import NonVerbalGauges from "../components/interview/NonVerbalGauges";
import QuestionCard from "../components/interview/QuestionCard";
import ReportView from "../components/interview/ReportView";
import StarChecklist from "../components/interview/StarChecklist";
import VerbalGauges from "../components/interview/VerbalGauges";
import WebcamPanel from "../components/interview/WebcamPanel";
import { useAudioRecorder } from "../hooks/useAudioRecorder";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { useVisionMetrics } from "../hooks/useVisionMetrics";
import { countFillers, wordCount } from "../lib/fillers";
import { api } from "../lib/api";
import { getReport, startInterview, submitAnswer, transcribeClip } from "../lib/interviewApi";
import { liveStar } from "../lib/starCues";
import { hasCV, useProfileStore } from "../store/profile";
import type { AnswerResult, InterviewQuestion, InterviewReport } from "../types/profile";

type Phase = "setup" | "answering" | "submitting" | "feedback" | "report";

export default function Interview() {
  const [phase, setPhase] = useState<Phase>("setup");
  const [params] = useSearchParams();
  const profile = useProfileStore((s) => s.profile);
  const setProfile = useProfileStore((s) => s.setProfile);
  const [role, setRole] = useState(() => params.get("role") ?? profile?.target_role ?? "");
  const [cameraOn, setCameraOn] = useState(true);
  // Hiding the landmark overlay only changes the picture: body language is still measured.
  const [showLandmarks, setShowLandmarks] = useState(true);
  const [questions, setQuestions] = useState<InterviewQuestion[]>([]);
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<Record<string, AnswerResult>>({});
  const [report, setReport] = useState<InterviewReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const speech = useSpeechRecognition();
  const audio = useAudioRecorder();
  const vision = useVisionMetrics({ enabled: cameraOn && phase !== "setup" && phase !== "report", overlay: showLandmarks });
  const [mode, setMode] = useState<"speak" | "type">(speech.supported ? "speak" : "type");
  const [typed, setTyped] = useState("");
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startedAt = useRef(0);
  // Whisper text of the 5-second live clips, by clip index. Chrome's live transcript drops "um"/"uh",
  // so the live filler gauge counts from these instead.
  const [clips, setClips] = useState<Record<number, string>>({});
  const answerToken = useRef(0);
  // Whether the microphone recording started: if the live captions drop, a recorded answer is still transcribed on submit.
  const [audioRecording, setAudioRecording] = useState(false);

  // The assistant can open this page for a role (?role=...) while it is already open.
  useEffect(() => {
    const r = params.get("role");
    if (r && phase === "setup") setRole(r);
  }, [params, phase]);

  // The profile store may sync from the server after the first render: pick up its target role then.
  const targetRole = profile?.target_role;
  useEffect(() => {
    if (targetRole && phase === "setup") setRole((r) => r || targetRole);
  }, [targetRole, phase]);

  /** Pull the server's profile (which now carries the interview report) into the shared store. */
  function refreshProfile() {
    api
      .getProfile()
      .then(setProfile)
      .catch(() => {}); // the Dashboard just keeps the previous numbers
  }

  useEffect(() => {
    if (!recording) return;
    const id = setInterval(() => setElapsed((performance.now() - startedAt.current) / 1000), 250);
    return () => clearInterval(id);
  }, [recording]);

  const question = questions[index];
  const result = question ? results[question.id] : undefined;
  const text = mode === "speak" ? `${speech.finalText} ${speech.interim}`.trim() : typed;
  const whisperText = useMemo(
    () =>
      Object.keys(clips)
        .map(Number)
        .sort((a, b) => a - b)
        .map((i) => clips[i])
        .join(" "),
    [clips],
  );
  const liveFillers = useMemo(() => {
    const total = (t: string) => Object.values(countFillers(t)).reduce((a, b) => a + b, 0);
    return Math.max(total(text), total(whisperText));
  }, [text, whisperText]);
  const star = useMemo(() => liveStar(text), [text]);
  // After scoring, the gauges show the scored (Whisper) numbers rather than the live estimate.
  const scored = phase === "feedback" ? result : undefined;

  async function begin() {
    setError(null);
    setStarting(true);
    try {
      const qs = await startInterview(role.trim());
      setQuestions(qs);
      setIndex(0);
      setResults({});
      setReport(null);
      resetAnswer();
      setPhase("answering");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setStarting(false);
    }
  }

  function resetAnswer() {
    speech.reset();
    setTyped("");
    setElapsed(0);
    setClips({});
    answerToken.current += 1; // late clip results from a previous answer are ignored
  }

  async function startSpeaking() {
    setError(null);
    resetAnswer();
    startedAt.current = performance.now();
    speech.start();
    const token = answerToken.current;
    // Optional: the full recording improves the final transcript; the clips drive the live filler gauge.
    void audio
      .start({
      segmentMs: 5000,
      onSegment: (clip, i) => {
        transcribeClip(clip)
          .then((t) => {
            if (t && answerToken.current === token) setClips((prev) => ({ ...prev, [i]: t }));
          })
          .catch(() => {}); // rate limit or offline: the live gauge just falls back to Chrome's transcript
      },
    })
      .then(setAudioRecording);
    if (vision.status === "running") vision.startAnswer();
    setRecording(true);
  }

  async function stopSpeaking() {
    const transcript = speech.stop();
    const duration = (performance.now() - startedAt.current) / 1000;
    setRecording(false);
    setElapsed(duration);
    const samples = vision.recording ? vision.stopAnswer() : [];
    const blob = await audio.stop();
    setAudioRecording(false);
    await send(transcript, duration, samples, blob);
  }

  async function send(transcript: string, durationS: number, samples: ReturnType<typeof vision.stopAnswer>, blob: Blob | null) {
    if (!question) return;
    if (!transcript.trim() && !blob) {
      setError("No answer was heard. Check your microphone, or type your answer.");
      return;
    }
    setPhase("submitting");
    setError(null);
    try {
      const r = await submitAnswer({ questionId: question.id, transcript, durationS, samples, audio: blob });
      setResults((prev) => ({ ...prev, [question.id]: r }));
      setPhase("feedback");
      refreshProfile();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("answering");
    }
  }

  async function next() {
    if (index + 1 < questions.length) {
      setIndex(index + 1);
      resetAnswer();
      setPhase("answering");
      return;
    }
    try {
      setReport(await getReport());
      setPhase("report");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function retry() {
    resetAnswer();
    setPhase("answering");
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <div className="flex flex-col gap-4">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-lg font-semibold">Mock interview{questions.length > 0 && role ? ` · ${role}` : ""}</h1>
          {phase !== "setup" && phase !== "report" && (
            <span className="text-xs text-slate-500">Readiness = 70% what you say + 30% body language</span>
          )}
        </header>

        {error && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200">
            {error}
          </div>
        )}

        {phase === "setup" && (
          <section className="mx-auto flex w-full max-w-lg flex-col gap-4 card p-6 dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-base font-semibold">Practise a 3-question interview</h2>
            {hasCV(profile) ? (
              <p className="-mt-2 text-sm text-slate-500">Questions are written from the skills and projects in your CV.</p>
            ) : (
              <p className="-mt-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
                <Link to="/upload" className="font-medium underline">
                  Upload your CV
                </Link>{" "}
                first and the questions will be about your own skills and projects. You can also practise without one.
              </p>
            )}
            {profile?.interview && (
              <p className="text-sm text-slate-600">
                Last session ({profile.interview.role}): readiness{" "}
                <strong className="tabular-nums">{Math.round(profile.interview.readiness)}</strong>/100
                {profile.interview.fix_first ? ` · fix first: ${profile.interview.fix_first}` : ""}
              </p>
            )}
            <label className="flex flex-col gap-1 text-sm">
              Target role
              <input
                className="rounded-lg border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="e.g. Data Analyst"
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={cameraOn} onChange={(e) => setCameraOn(e.target.checked)} />
              Use my camera for body-language feedback (video never leaves this device)
            </label>
            <button
              className="btn-primary px-4 py-2.5"
              disabled={!role.trim() || starting}
              onClick={begin}
            >
              {starting ? "Preparing your questions…" : "Start interview"}
            </button>
          </section>
        )}

        {question && (phase === "answering" || phase === "submitting" || phase === "feedback") && (
          <>
            <div className="iv-zone">
            <div className="iv-grid">
              <div className="iv-q flex flex-col gap-4">
                <QuestionCard
                  question={question}
                  index={index}
                  total={questions.length}
                  mode={mode}
                  speechSupported={speech.supported}
                  recording={recording}
                  elapsedS={elapsed}
                  busy={phase !== "answering"}
                  onModeChange={setMode}
                  onStart={startSpeaking}
                  onStop={stopSpeaking}
                />
                <section className="card p-4 dark:border-slate-700 dark:bg-slate-900">
                  <h3 className="mb-2 text-sm font-semibold">{mode === "speak" ? "Live transcript" : "Your answer"}</h3>
                  {scored ? (
                    <LiveTranscript text={scored.transcript} />
                  ) : mode === "speak" ? (
                    <LiveTranscript text={speech.finalText} interim={speech.interim} />
                  ) : (
                    <div className="flex flex-col gap-2">
                      <textarea
                        className="min-h-40 rounded-lg border border-slate-300 bg-transparent p-2 text-sm dark:border-slate-600"
                        value={typed}
                        onChange={(e) => setTyped(e.target.value)}
                        disabled={phase !== "answering"}
                        placeholder="Type your answer as you would say it."
                      />
                      <button
                        className="self-end btn-primary px-4 py-2 text-sm"
                        disabled={phase !== "answering" || !typed.trim()}
                        onClick={() => send(typed, 0, [], null)}
                      >
                        Submit answer
                      </button>
                    </div>
                  )}
                  {speech.reconnecting && (
                    <p className="mt-2 text-xs text-slate-500" aria-live="polite">
                      Live captions lost the connection. Reconnecting… keep talking.
                    </p>
                  )}
                  {speech.error && (
                    <p role="alert" className="mt-2 text-xs text-amber-700 dark:text-amber-400">
                      {speech.error}{" "}
                      {speech.errorKind === "network" && recording && audioRecording
                        ? "Your voice is still being recorded: keep going and submit when you are done, and the recording will be transcribed for scoring."
                        : speech.errorKind === "network"
                          ? "Type your answer instead."
                          : null}
                    </p>
                  )}
                </section>
              </div>

              <div className="flex flex-col gap-2">
                {cameraOn ? (
                  <WebcamPanel vision={vision} />
                ) : (
                  <div className="flex aspect-[4/3] items-center justify-center rounded-xl bg-slate-200 p-6 text-center text-sm text-slate-500 dark:bg-slate-800">
                    Camera off: verbal-only mode. Readiness will be your verbal score.
                  </div>
                )}
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <ToggleButton
                    label="Camera"
                    on={cameraOn}
                    onChange={setCameraOn}
                    title={recording ? "Turning the camera off now skips body language for this answer" : undefined}
                  />
                  <ToggleButton label="Landmarks" on={showLandmarks} onChange={setShowLandmarks} disabled={!cameraOn} />
                </div>
              </div>

              <div className="flex flex-col gap-4">
                {scored ? (
                  <VerbalGauges
                    words={scored.verbal.word_count}
                    fillers={Object.values(scored.verbal.filler_counts).reduce((a, b) => a + b, 0)}
                    elapsedS={scored.verbal.duration_s}
                    spoken={scored.verbal.duration_s > 0}
                    scored
                  />
                ) : (
                  <VerbalGauges words={wordCount(text)} fillers={liveFillers} elapsedS={elapsed} spoken={mode === "speak"} />
                )}
                <StarChecklist live={star} scored={phase === "feedback" ? result?.verbal.star : null} />
                {cameraOn && <NonVerbalGauges live={vision.live} answer={vision.answer} recording={vision.recording} />}
              </div>
            </div>
            </div>

            {phase === "submitting" && (
              <p className="card p-4 text-sm dark:border-slate-700 dark:bg-slate-900" aria-live="polite">
                Analysing your answer: STAR structure, fillers, relevance and body language…
              </p>
            )}

            {phase === "feedback" && result && (
              <>
                <AnswerFeedback result={result} />
                <div className="flex gap-3">
                  <button className="btn-primary px-4 py-2" onClick={next}>
                    {index + 1 < questions.length ? "Next question" : "See my readiness report"}
                  </button>
                  <button className="btn-secondary px-4 py-2" onClick={retry}>
                    Try this question again
                  </button>
                </div>
              </>
            )}
          </>
        )}

        {phase === "report" && report && <ReportView report={report} onRestart={() => setPhase("setup")} />}
      </div>
    </div>
  );
}

function ToggleButton(p: { label: string; on: boolean; onChange(on: boolean): void; disabled?: boolean; title?: string }) {
  return (
    <button
      type="button"
      aria-pressed={p.on}
      title={p.title}
      disabled={p.disabled}
      onClick={() => p.onChange(!p.on)}
      className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-40 ${
        p.on
          ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-200"
          : "border-slate-300 bg-white text-slate-600 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300"
      }`}
    >
      <span className={`relative h-4 w-7 rounded-full transition-colors ${p.on ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-600"}`}>
        <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-white shadow transition-all ${p.on ? "left-3.5" : "left-0.5"}`} />
      </span>
      {p.label} {p.on ? "on" : "off"}
    </button>
  );
}
