# Release method

A release is any production deploy of the site. Follow this every time, in order,
and tick the steps in the release's log entry below. **A step may be skipped only
if the log says so and says why.**

Howard approves each production deploy (step 9). Test deploys need no approval.

## Principles

1. **State a number once.** If prose needn't carry a number, remove it. If it must,
   a test ties it to one source (`docs/release-facts.json`, `web/data`).
2. **Measure what is served.** The record of a release is read from the live site,
   after the deploy, not from the build.
3. **Explain every difference.** A release changes only what we meant to change;
   `diff_payload.py` is how we know.
4. **Facts describe what is live.** `README.md`'s numbers and
   `docs/release-facts.json` change after the deploy, in their own commit, made
   straight away: until then they describe the previous build.

## Checklist

### Build

1. **Clean start.** `git status`: know what is in this release and what is not.
   Drive mounted (`/Volumes/Expansion`).
2. **Data, if this release refreshes it.** `python -m ehd.fetch --templates --refresh`,
   then `python -m ehd.harvest`. New source: pin its contents and checksum in code,
   as `ehd/zenodo.py` does, and state its licence in the viewer and the README.
3. **Build.** `python -m ehd.emit`, `python -m ehd.basemap` (emit does not build it).
4. **Hand-written counts.** Update the `web/index.html` head: count, span, source
   names. `pytest` pins the count and span against the build, not the source names.

### Check

5. **Tests.** `.venv/bin/python -m pytest tests/`: all pass.
6. **Independent readers.** `python -m ehd.validate`: 100% agreement, 0 disagreements,
   0 invariant failures, 0 series only dplR finds. Note the counts for step 12.
   If corpus metadata moved, also `python -m ehd.sweep`.
7. **What changed.** `python scripts/diff_payload.py`. Explain each line in the log:
   logs lost, logs added by site, site records changed, year range, stats.
8. **Test deploy, and look at it.**
   `npx wrangler@4.124.0 pages deploy web/ --project-name ehd --branch test`, then
   `python scripts/verify_deploy.py --origin https://test.ehd-612.pages.dev`
   (some checks are production-only). In a browser, on that URL:
   - timeline loads; counts in the footer match the build; no console errors;
   - open a ring-width curve **from each source new or changed in this release**;
   - PANGAEA bar shows restricted status, no curve;
   - map opens, click a merged circle, "Show on timeline" works;
   - light and dark; a phone, if the UI changed.

### Deploy

9. **Howard approves.** Show him the diff summary and test results.
10. **Commit, then deploy.** Commit the sources so the deployed commit exists. Then
    `npx wrangler@4.124.0 pages deploy web/ --project-name ehd --branch main`.
11. **Verify production.** `python scripts/verify_deploy.py`. A failure straight after
    a deploy can be stale edge copies: rerun once, and log the failure regardless.

### Record

12. **Record the facts.** `python scripts/release_facts.py --write`. In
    `docs/release-facts.json`, update `validation` from step 6 if it was rerun.
13. **Update the README.** `pytest tests/test_readme.py` names every sentence that is
    now wrong; correct them. Then reread the whole README for what the test cannot
    see: scope, sources, licences, how to run it.
14. **Update the other docs.** `HANDOFF.md` status line and deployment; retire any
    "built locally" note. `docs/data-survey.md`, if a source changed status. Any talk
    or draft mail that quotes numbers. `web/og.jpg` and its alt text if the map's look
    changed (recipe in `HANDOFF.md`, Link previews).
15. **Confirm.** `python scripts/release_facts.py --check`, and `pytest` again.
16. **Log it, commit it, push it.** Add the entry below; commit; `git push`.
17. **Refine this method** (below).

## Refining this method

At step 17, ask: what went wrong, or nearly, that no step would have caught? What
step was skipped, or felt useless? Change this file in the same commit, and say why
in the log.

- Prefer a check that fails on its own to a step someone must remember.
- A defect that reached production gets a check that would have caught it.
- A step that never catches anything and costs real time may be removed, with the
  reason logged.

## Log

Newest first. Earlier entries predate this method: they are from `HANDOFF.md`, and
were not run against this checklist.

| Date | Deployment | Commit | Logs | First load (bytes) | Notes |
|---|---|---|---:|---:|---|
| 2026-11-02 | `51308fa7` | `1d3c04d` | 123,910 | 1,263,649 | 540 Zenodo oaks. Diff: 540 added, 0 lost, 1 site added, 0 site records changed. Test deploy `fbfd69e7` 80/80; Howard checked it in a browser; production 92/92. Step 6 (dplR) not rerun: ITRDB input unchanged since the 2026-11-01 run, and dplR cannot read the oak file's repeated IDs as separate series; the oaks were checked by an independent scanner instead. Step 14: `og.jpg` not recaptured (the oaks add one point inside an existing merged circle). |
| 2026-11-01 | none | | 123,370 | 1,258,954 | No deploy: records the live 2026-10-24 build when this method began. dplR rerun: 100.0000% on 76,397, 12,349 ours only, 0 invariant failures. |
| 2026-10-24 | `79b358e0` | `6e4daf7` | 123,370 | 1,258,673 | Expanded Europe + Hohenheim. First `verify_deploy` failed 3 checks on stale edge copies; rerun passed 92/92. |
| 2026-10-22 | `235d0882` | `c113dc5` | 73,390 | 655,918 | Previous deploy. |

### Method changes

- **2026-11-02.** Small first-load files vary between measurements with no source
  change: `style.css` went from 2,941 to 2,944 bytes as served, unchanged in git,
  presumably edge compression. So `release_facts.py --check` compares the payload
  only, and the README's first-load figure is a dated measurement, not a constant.
  This probably also explains the 281 bytes noted below.

- **2026-11-01, method created.** Why: the README still said 73,390 logs eight days
  after 123,370 went live, and described the corpus as ITRDB only. Nothing tied it to
  the build. First facts recorded the same day from the live site: 123,370 logs, first
  load 1,258,954 bytes. That is 281 bytes above the deploy-day figure with `logs.bin`
  and `index.json` unchanged, so it lies in the page, `app.js` and `style.css`. Cause
  not checked; the injected analytics script is one candidate.
