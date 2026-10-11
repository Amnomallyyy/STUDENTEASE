# CareerLens: 5-minute presentation script (word for word)

Roles: one **presenter** speaks, one **driver** clicks. Demo persona: `demo/demo_cv.pdf` (Sara Ahmed, final-year CS,
target Data Analyst, Karachi), GitHub username `careerlens-demo`, `demo/linkedin_export.pdf`. Numbers below are
what the demo CV produces today; if the live job search returns different postings, read the numbers off the screen.

Before walking on: both servers running, **Delete my data** pressed, demo files open in a folder, camera and mic
allowed, the upload page showing in the browser.

---

## 0:00 - Opening (slide: title)

> Every year thousands of graduates apply for jobs blind. They do not know which of their skills actually match
> the roles near them, they cannot prove the claims on their CV, and they walk into interviews without ever having
> practised one.
>
> CareerLens fixes that with one upload. You give it your CV, and in two minutes you know exactly what to fix, where
> to apply, and how to answer. Let me show you.

*Driver: switch to the browser on the upload page.*

---

## 0:30 - Upload (screen: Upload CV)

> This is the only thing the user ever enters: a CV, a target role and a place. Sara here is a final-year computer
> science student in Karachi who wants a Data Analyst job.

*Driver: drop `demo_cv.pdf`, pick Data Analyst, click Karachi, click Analyse my CV.*

> While it reads the CV: personal details are stripped before anything reaches an AI model. No name, no email, no
> photo. Only skills, projects and experience leave the browser. There are no accounts and no database; each
> browser tab is its own session, and "Delete my data" wipes everything.

---

## 1:00 - Career Map (screen: Career Map)

*Driver: the Career Map has opened. Point at the meter.*

> One CV, and every module reads from it. The meter says Sara matches 70 percent of the Data Analyst role. That is
> not a guess: every skill the extractor found is compared with the role's weighted skill list using embeddings,
> so "PostgreSQL" still counts as "SQL".

*Driver: point at the headline under the meter.*

> This line is the part we are proudest of. "13 of 19 nearby jobs ask for SQL, learn that first." Those 19 jobs are
> not a dataset we typed up. They are live postings pulled this minute from LinkedIn, Indeed, Glassdoor and
> Pakistani job boards for the role and the city the user chose.

*Driver: scroll to the map, click the top job in the ranked list.*

> Each pin is a real posting, coloured by how well Sara fits it. Click one and you get its requirements with ticks
> and crosses, where it was listed, when it was posted, and an "Apply" button that opens the original advert.

*Driver: click "Prepare me for this job". Scroll right to the roadmap.*

> And when she pins a job, the four-week roadmap on the right re-orders itself around that job's gaps, using only
> free, whitelisted resources. The plan comes from the local market, not a generic template.

---

## 2:00 - CV Analyzer (screen: CV Analyzer)

*Driver: open CV Analyzer, type `careerlens-demo`, drop `linkedin_export.pdf`, click Run the evidence check.*

> A match score is only as honest as the CV. So now we check the CV against proof. GitHub through its official
> API, LinkedIn only through the user's own data export, and any portfolio files they attach. Nothing is scraped.

*Driver: the evidence board appears. Point at the three columns, then the amber chips.*

> Green skills appear in every source. Amber ones appear in only one. Three claims fail: "Expert in Docker" is
> mentioned once with no project behind it. Kubernetes appears nowhere outside the CV. And JavaScript is a third of
> her GitHub code but is not on the CV at all, a missed strength.

*Driver: click the Docker chip.*

> Every finding says why a recruiter will care and gives a concrete fix. The integrity score is the share of CV
> claims backed by at least one external source.

*Driver: click "Open the Career Map" on the role-impact card.*

> And it flows back. The Career Map now shows which matched skills are evidenced, and the match splits into what
> the CV claims and what the evidence supports. Here, every matched skill is backed, so the evidenced match is also
> 70 percent.

---

## 3:00 - Mock Interview (screen: Mock Interview)

*Driver: open Mock Interview, keep the camera box ticked, click Start interview, allow camera and microphone.*

> The last gap is the interview itself. CareerLens writes three questions from Sara's own CV and projects, then
> listens and watches.

*Driver: answer question one live, about 45 seconds, rehearsed, with two deliberate "um"s and one glance away.*

> Fillers and pace are counted by code, not by a model. The STAR check has to quote the transcript for each
> element, so it cannot invent a Result that was never said. Body language is geometry on face and pose landmarks,
> computed in the browser. The video never leaves this laptop.

*Driver: point at the report: STAR ticks, filler count, the eye-contact dip, the readiness dial, the rewritten answer.*

> The report names the exact moment she looked away, scores readiness, and rewrites her answer in proper STAR form.

---

## 4:15 - Assistant (chat panel)

*Driver: open the Assistant, type "What should I do first?"*

> The assistant answers only from her profile. It names the top market gap, and when it talks about jobs it opens
> the map itself with the right filters.

---

## 4:30 - Close (slide: closing)

> What we built: one shared profile, four modules, every number on screen traceable to a source. The language model
> runs on Groq through a swappable adapter, embeddings run locally, jobs come from the JSearch API, and the whole
> thing runs with no accounts and no database.
>
> Who it is for: final-year students and job seekers, free, with skills-only matching so no name, gender, age or
> university ever reaches the model. The adoption path is a university placement office putting it in front of a
> whole cohort.
>
> Upload your CV, and in two minutes know exactly what to fix, where to apply, and how to answer. Thank you.

---

## If something breaks

- **Upload hangs or shows an AI error:** Groq throttles for a few seconds at busy times; the app waits and retries
  on its own. If it fails twice, press Delete my data and upload again; the demo CV answers from the offline cache.
- **Map shows "sample listings":** the job API key is missing from `.env`. The demo still works; say "sample
  listings" instead of "live postings" and move on.
- **Camera refused:** untick "Use my camera" and answer by text; the STAR and filler analysis still run.
- **Laptop dies:** the screen recording.

## Likely questions, short answers

- **Where do the jobs come from?** The JSearch API, which aggregates LinkedIn, Indeed, Glassdoor and regional
  boards. Each card shows the board and links to the original posting. We never scrape LinkedIn.
- **Which model?** Groq-hosted gpt-oss through an OpenAI-compatible adapter; any provider is one environment
  variable away. Embeddings are all-MiniLM-L6-v2 running locally. Vision is MediaPipe in the browser.
- **How do you stop the model inventing skills?** Every extracted skill must quote the CV, and a deterministic pass
  over a 200-skill vocabulary adds anything the model skipped. Job requirements use the same vocabulary.
- **Privacy?** Personal details stripped before any model call, one profile per browser tab in memory only, no
  database, video processed locally, Delete my data clears everything.
- **What was pre-built?** Role, resource and sample job datasets, demo files and CI, dated in DISCLOSURES.md. The
  screens, the live job search, the evidence pipeline, the interview pipeline and the integration were built during
  the event.
