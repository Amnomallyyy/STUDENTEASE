# CareerLens frontend (M2)

Vite + React 18 + TypeScript + Tailwind. One shared profile (Zustand, persisted to local storage) feeds every
screen; every number on screen comes from the FastAPI backend (`docs/api.md`).

## Run

```bash
npm i
npm run dev        # http://localhost:5173, expects the backend at http://localhost:8000
npm test -- --run  # vitest (CI runs the same)
npm run build      # type-check + production build into dist/
```

`VITE_API_URL` (see `.env.example`) points the app at another backend, e.g. the Render URL in the Vercel
dashboard. The backend must list the frontend origin in `CORS_ORIGINS`.

## Screens

| Route | File | What it shows |
|---|---|---|
| `/upload` | `pages/Upload.tsx` | CV dropzone (PDF/DOCX/TXT ≤ 5 MB), target role, student / job-seeker mode, location (Geolocation API or Karachi / Lahore / Islamabad), progress steps. `POST /profile/cv`, then straight to the Career Map |
| `/dashboard` | `pages/Dashboard.tsx` | One tile per module (role match, jobs you fit nearby, CV integrity, interview readiness), the market headline, extracted skills / projects / experience |
| `/career` | `pages/CareerMap.tsx` | Three columns: gap panel (match meter, keyword-vs-embedding toggle, have / partial / missing chips with "N of 20 jobs" counts, category radar, adjacent roles) \| Leaflet map with clustered pins coloured by match % + filters (radius 5/10/25 km, min match, keyword, match-vs-distance ranking slider) + ranked list + job detail with ticks and crosses and "Prepare me for this job" \| 4-week roadmap with tick-off progress that re-prioritises when a job is pinned |
| `/analyzer` | `pages/Analyzer.tsx` | GitHub username + LinkedIn export (file or pasted text) → `POST /analyzer/run`; CV / LinkedIn / GitHub evidence board (green in every source, blue in some, amber in one only → click opens the anomaly card), grouped anomaly cards with fixes, integrity score |
| `/interview` | `pages/Interview.tsx` | Route placeholder for M3 / M4 (shows the last report's numbers if present) |
| `/built-with` | `pages/BuiltWith.tsx` | `GET /built-with` and `GET /health`: every model, API, dataset and library with its licence; fairness and privacy notes |

The chat panel (`components/chat/`) sits on the right edge of every screen. It streams `POST /chat` server-sent
events (`hooks/useChatStream.ts`); the `open_map`, `open_career_map` and `open_interview` events are applied by
`components/layout/Shell.tsx` (filters set, screen opened) and shown as "open in module" chips on the answer.

## State

- `store/profile.ts` mirrors the backend `Profile` (`types/profile.ts` is generated from the Pydantic models with
  `python -m backend.schemas.generate_ts`; `types/api.ts` hand-mirrors the analyzer / jobs-map models).
- `store/session.ts` holds UI state: selected role, map filters, pinned job, roadmap tick-offs, chat transcript.
- The server keeps the profile in memory only. If it restarts, `GET /profile` comes back empty and the Shell shows a
  "re-upload your CV" banner. **Delete my data** calls `DELETE /profile` and clears both stores.

## How the Analyzer feeds the Career Map

`POST /analyzer/run` rewrites the shared profile: every CV skill is tagged with the sources that back it, the
skills the CV omits (LinkedIn skills, GitHub languages that are at least 20 % of the code) are appended, and the
target-role gap is recomputed with `evidenced_pct`. The Career Map then shows a tick or a dashed "CV only" badge on
every matched chip (`SkillChips`), an "Evidenced by GitHub and LinkedIn: N%" inner ring and line under the headline,
and a CV-only chip opens `/analyzer?claim=<skill>` at that skill's anomaly. The Analyzer shows the role impact of
each finding (`lib/roleImpact.ts`: share of the role's weight the skill carries) and a card with the refreshed match.
Before the Analyzer has run, the Career Map and dashboard say so and link to it.

## Rules the UI states (same as the README)

Pins and meters: green ≥ 75 %, amber 50-74 %, red < 50 %. Job ranking: `0.7 × match % + 0.3 × nearness` by default
(slider). Keyword-only matching (`lib/keywordMatch.ts`) counts a required skill only on an exact normalised name,
which is what the toggle contrasts with the embedding matcher. Roadmap progress is stored in this browser only.

## Deploy

`vercel.json` (framework Vite, SPA rewrite). Set `VITE_API_URL` to the backend URL in the Vercel project and add the
Vercel domain to the backend's `CORS_ORIGINS`.
