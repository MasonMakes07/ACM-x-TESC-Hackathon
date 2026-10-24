# Person 3 (Product & Dashboard) — complete plan

Not committed: this is your personal checklist, not a team file.
Last updated 2026-10-24 after comparing with `ClaudsePerson3Handoff.md`, `World_Map_Handoff.md`,
and what is actually on GitHub. The completed prompts A and B are in `person3_prompts_archive.md`.

## 1. The goal

A judge opens EarthWatch and sees **a spinning globe of the whole world** with the dashboard beside
it. They click an event on the globe, see exactly what happened and which sources the Grok agents
used (with links), run an investigation, watch the real agent progress, and understand the
conclusion without reading any code. (plan.md "Definition of done" for Person 3.)

Scope is **worldwide climate change events**, not just El Niño or Peru. El Niño / northern Peru is the
first monitored case only.

## 2. Where everything is right now

| Thing | Where | State |
|---|---|---|
| Person 1 (data) | `origin/main` via `yube-dev` | Landed: worldwide locations, historical data, replay, rainfall/weather sources |
| Person 2 (agents) | `origin/main` via `mason-dev` | Landed: Grok pipeline in `agents/` (Investigator, Regional Impact, Skeptic, Reviser, ledger with source URLs) |
| `origin/main` | `dc08287` | **226 tests pass** (checked in a clean copy) |
| My Person 3 build | local `ALex-Mac-Mini` (HEAD `3b723d5`) | **6 commits are not pushed.** GitHub has `fea4cc5`. 127 of 128 tests pass. |
| Other agent's build | branch `Alex`, commits `c7b15ea` `2ffda55` | **Not on GitHub.** It lives only on whichever device or folder that agent used. |
| Globe + severity work by other agents | `origin/p3-components` (`d4b6bc7`), merged into local `ALex-Mac-Mini` | Pushed by `alexgilbreath11` while I was working |
| World map change | `origin/p3-charts` (`d85e0bb`), merged into local `ALex-Mac-Mini` | Pushed |

The one failing test (`test_selected_region_is_highlighted`) comes from another agent's unfinished
edit to `dashboard/globe.py` (it was changing marker colors to severity colors). It is not committed.

## 3. What Person 3 has built (checked)

- [x] Four-tab dashboard: Overview, Climate Explorer, Investigation, Regional Briefing
- [x] Spinning world globe as the main view, dashboard on the right
- [x] Click a globe marker to open that event (tested in a real browser)
- [x] Event panel: what happened, last agent update time, every source the agents cited with an Open source link
- [x] Sources without a URL are labelled "no link", never given an invented one
- [x] Sample data is always labelled (banners and a "SAMPLE sources" warning)
- [x] Investigation button streams real progress events; results are kept per anomaly
- [x] Charts: SST line chart with replay slider, threshold lines, highlighted anomaly, empty state
- [x] Dark theme, accessible severity colors and alert pulses (other agents' work)
- [x] Error states: failed data, chart source or agents show a message, never a stack trace
- [x] Tests for all of the above

## 4. Comparison: my build vs the other agent's handoff

| Feature | My build (`ALex-Mac-Mini`) | Handoff build (`Alex`) | Decision |
|---|---|---|---|
| Main visual | 3D globe, click to select | Flat world map (OpenStreetMap), no globe | **Keep mine** (the globe is what you asked for) |
| Tabs | Overview / Climate Explorer / Investigation / Regional Briefing | Overview / Climate Explorer / Investigation / Regional Impact | Keep mine. Optionally rename Briefing to "Regional Impact" to match plan.md |
| Sources with links | Prominent panel beside the globe | Expandable evidence list inside Investigation | **Keep mine** (your latest requirement) |
| Guided demo ("Run guided demo": resets filters, picks the strongest anomaly, runs it) | **Missing** | Yes | **Take theirs.** This is the repeatable demonstration mode plan.md asks for |
| Overview bar chart of all anomalies vs the ±0.5 neutral band | Missing (status strip and cards only) | Yes (`anomaly_comparison_chart`, `ENSO_THRESHOLD`) | **Take theirs**, add next to my cards |
| Region filter | One region dropdown plus anomaly dropdown | Region multiselect plus historical period | Keep mine; add multiselect only if there's time |
| Replay | "Show data up to" slider | Historical period selector | Equivalent. Keep mine |
| Region validation in `translator.py` | Still the two-region allow-list | Pattern `^[A-Za-z0-9 +._-]{1,64}$` so any region passes | **Take theirs.** Mine blocks every non-Niño region, which breaks the worldwide goal |
| Run button lookup in tests | By position (`button[0]`), fragile | By label `Run Investigation` | **Take theirs**, because new buttons will break mine |
| Map context markers | Only registered coordinates; unplotted events are listed | 7 ocean regions plus ENSO-affected areas from general knowledge, uncited | **Verify or remove** theirs before the demo. The plan forbids uncited claims |
| Tests | 128 in my branch | 51 | Mine are a superset |

Also on `main` now: a **"Worldwide locations" explorer** (`dashboard/global_explorer.py`, added to
`app.py` by teammates) with country and city search, Load climate data, and its own Run Investigation.
My branch and `main` conflict in exactly one file, `app.py`. `translator.py` merges cleanly.

## 5. Risks to deal with first

1. **Several agents are editing the same folder.** Commits and file edits from other agents are
   appearing on my branch. Keep one agent per working folder (use `git worktree` or a separate clone).
2. **The `Alex` branch is not on GitHub.** Until it is pushed, its features cannot be merged.
3. **Two globes exist.** Mine (`dashboard/globe.py`, click to select) and a second one in
   `dashboard/components.py` (`climate_globe`, with pause/reset/zoom controls). Pick one, or move the
   best controls (pause rotation, world view, reduced motion) into mine.
4. **`app.py` conflict with `main`.** Resolve once, in one place, by whoever owns integration (me).
5. **Real data is not yet confirmed in my UI.** The globe only knows regions listed in `dashboard/maps.py`
   (`REGION_BOXES`). `main`'s worldwide locations have latitude and longitude in `data/locations.py`;
   the globe needs to read those.
6. **Real Grok run unverified.** Needs `XAI_API_KEY` and `XAI_MODEL` in `.env`. I haven't confirmed
   every cited source comes back with a URL.
7. **Wording:** `README.md` line 5 and `sample_data/assessment.json` still say Peru. Shared files, so
   agree changes with the team first.

## 6. Next steps, in order

### Step 1 — Get the other agent's work onto GitHub (you, 2 minutes)
Paste **Prompt C** (below) into the agent that wrote the handoff. It only pushes its branch; it changes
nothing else.

### Step 2 — Protect what exists (me)
Tell me **"push my branch"**. I will wait for the other agent to finish its `globe.py` edit, run the full suite, then push
`ALex-Mac-Mini` so nothing is lost.

### Step 3 — Integrate with `main` (me)
Tell me **"merge main"**. I will merge `origin/main`, resolve the single `app.py` conflict (keeping both the
globe view and the worldwide explorer), and make the globe plot `main`'s worldwide locations.

### Step 4 — Port the handoff's best features (me, after Step 1)
Tell me **"port the handoff"**. I will bring over: the guided demo, the Overview comparison chart, global
region validation in `translator.py`, and label-based test lookup. I will drop or verify the uncited map markers.

### Step 5 — Decide the globe (you, one answer)
Tell me which globe to keep, or **"merge the best of both"**. Default if you say nothing: mine, with the other
globe's pause, world-view and reduced-motion controls added.

### Step 6 — Real run (you + me)
Put your Grok key in `.env` (copy `.env.example`), then tell me **"run it for real"**. I will run an investigation
and check that the SAMPLE banners are gone and every source has a link. Anything missing goes to Person 2.

### Step 7 — Ship
Tell me **"open the PR"**. I rebase on `main`, run the tests, push and open the pull request. Post the link in the team chat.

### Step 8 — Demo, deploy, present
- Ask me for the 2-minute demo script and rehearse it three times.
- Deploy (Streamlit Community Cloud is the quickest). Add the Grok key as a secret, not in the repo.
- Final presentation: plan.md section 16 has the 3-minute outline.
- Prepare a fallback: cached historical data and the sample investigation if the live API fails, clearly labelled.

## 7. plan.md checklist for Person 3 (honest status)

| Item | Status |
|---|---|
| Working dashboard | Done |
| Climate anomaly charts | Done (rainfall chart still missing; Person 1's rainfall data is now on `main`) |
| Investigation trigger and real backend integration | Wired; not yet confirmed against the real Grok agents |
| Visible investigation progress | Done (shows whatever events the backend sends) |
| Evidence and regional assessment views | Done, plus a sources panel with links |
| Informative error states | Done |
| Repeatable demonstration mode | **Not done in my build.** The handoff has it (Step 4) |
| Successful deployment and final rehearsal | Not started |
| Final presentation | Not started |

## 8. Prompt C — paste into the agent that wrote the handoff

```
You are the coding agent that wrote ClaudsePerson3Handoff.md for "Person 3 (dashboard)" on the
EarthWatch hackathon repo (git@github.com:MasonMakes07/ACM-x-TESC-Hackathon.git).

Your branch `Alex` (commits c7b15ea and 2ffda55) exists only on this machine. Another agent needs to
merge it, so push it. Do exactly this and nothing else:

1. In your working copy run: git status && git log --oneline -3 && git branch --show-current
   Make sure the branch is `Alex` and the working tree is clean. If there are uncommitted Person 3
   changes, commit only those files with `git add <file>` (never `git add .`).
2. Run: pytest -q     (report the result line; do not fix unrelated failures)
3. Run: git push -u origin Alex
   If SSH fails use: gh auth login   and retry.
4. Do NOT merge, rebase, open a PR, or push to any other branch. Do not edit any file.

Reply with: the branch name, the pushed commit hashes, the pytest result line, and the exact path of
your working copy. Also list, in at most 5 bullets, every feature in your branch that is NOT in the handoff
document (anything you added after writing it).
```
