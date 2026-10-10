// Placeholder route for the mock interviewer. The three-zone screen (QuestionCard, LiveTranscript, VerbalGauges,
// StarChecklist, ReportView, AnswerDiff) is owned by M3 and the webcam centre (WebcamPanel, NonVerbalGauges) by
// M4; this page keeps the route, the chatbot's open_interview action and the dashboard tile working until then.
import { Link, useSearchParams } from "react-router-dom";
import { Mic } from "lucide-react";
import { hasCV, useProfileStore } from "../store/profile";

export default function Interview() {
  const [params] = useSearchParams();
  const profile = useProfileStore((s) => s.profile);
  const role = params.get("role") ?? profile?.target_role ?? null;
  const report = profile?.interview ?? null;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-2xl font-bold tracking-tight">Mock interview</h1>
      <p className="mt-1 text-slate-600">
        Three role-specific behavioural questions, typed or spoken, scored on STAR structure, fillers and pace, with
        body-language metrics computed in your browser. Readiness = 0.70 × verbal + 0.30 × non-verbal.
      </p>

      <div className="card mt-6 flex gap-4 p-5">
        <Mic className="h-8 w-8 shrink-0 text-brand-600" aria-hidden />
        <div className="text-sm text-slate-700">
          <p>
            {role ? (
              <>
                Target role for this session: <strong>{role}</strong>.
              </>
            ) : (
              "Pick a target role on the Career Map first."
            )}
          </p>
          <p className="mt-2 text-slate-500">
            The interview screen is being built by the interview (M3) and vision (M4) members on top of
            <code className="mx-1 rounded bg-slate-100 px-1">POST /interview/start</code>,
            <code className="mx-1 rounded bg-slate-100 px-1">POST /interview/answer</code> and
            <code className="mx-1 rounded bg-slate-100 px-1">GET /interview/report</code>. This route, the dashboard
            tile and the assistant's "start interview" action already point here.
          </p>
          {!hasCV(profile) && (
            <Link to="/upload" className="btn-primary mt-4">
              Upload a CV first
            </Link>
          )}
        </div>
      </div>

      {report && (
        <div className="card mt-6 p-5">
          <h2 className="text-sm font-semibold">Last session · {report.role}</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg bg-slate-50 p-3">
              <p className="text-xs uppercase text-slate-500">Readiness</p>
              <p className="text-2xl font-bold">{Math.round(report.readiness)}</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <p className="text-xs uppercase text-slate-500">Verbal ({Math.round(report.verbal_weight * 100)}%)</p>
              <p className="text-2xl font-bold">{Math.round(report.verbal_score)}</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <p className="text-xs uppercase text-slate-500">Non-verbal ({Math.round(report.non_verbal_weight * 100)}%)</p>
              <p className="text-2xl font-bold">{report.non_verbal_score === null ? "n/a" : Math.round(report.non_verbal_score)}</p>
            </div>
          </div>
          {report.fix_first && (
            <p className="mt-3 text-sm text-slate-700">
              <span className="font-medium">Fix first:</span> {report.fix_first}
            </p>
          )}
        </div>
      )}

      <p className="mt-6 text-xs text-slate-400">
        Body-language metrics are geometric (head angle, shoulder tilt, wrist velocity), never emotion or identity
        claims; video never leaves your browser. It coaches habits, it does not judge people.
      </p>
    </div>
  );
}
