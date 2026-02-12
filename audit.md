# bus-check project audit

Scope: quick technical + analysis audit focused on answering the question **“Have CTA Frequent Network routes gained ridership *share* since launch?”** and improving the project enough to make that answer reliable.

> Per your request, this audit **drops** prior recommendations #1, #5, and #6.

---

## 1) Main gap: the project doesn’t directly measure **ridership share**

Your current analysis is closer to **route-level ridership changes** (e.g., YoY deltas) and/or early DiD scaffolding. That’s useful, but it’s not the same as:

- “What % of total CTA bus ridership is on Frequent Network routes?”
- “Did that % increase after the Frequent Network launched (and expanded in phases)?”

### Recommendation
Add a dedicated notebook/module that produces:

- **Monthly (or weekly) total bus rides (all routes)**
- **Monthly (or weekly) rides on Frequent Network routes**, split by:
  - Phase 1 routes (launch 2025-03-23)
  - Phases 1–3 routes (if your dataset window ends before Phase 4)
  - Full 20 routes once post-data exists
- **Share metrics**:
  - `share_phase1 = rides(phase1) / rides(all_routes)`
  - `share_phase123 = rides(phase1–3) / rides(all_routes)`
- Visuals:
  - share time series with vertical lines at **phase start dates**
- Summary table:
  - pre/post deltas using 3- and 6-month windows
  - same-window prior year comparison as a robustness check

This can usually be done efficiently via the Socrata/SODA API using server-side aggregations (group by month), rather than downloading all raw rows.

---

## 2) Treat the rollout as **phased** and route-specific

Frequent Network wasn’t a single, simultaneous treatment; it rolled out in phases.

### Recommendation
Support at least one of these treatment designs:

- **Event-time alignment by phase**: analyze Phase 1 routes around 2025-03-23, Phase 2 around its start date, etc.
- **Stacked DiD / staggered adoption**: each treated route gets its own treatment date; avoid using “already treated” routes as controls.

Even if you keep it simple, your share plots and pre/post windows should be computed per phase to avoid mixing treatment timing.

---

## 3) Control for day-type and seasonality (at minimum)

Bus ridership has strong weekly and seasonal patterns.

### Recommendation
For share and level comparisons:

- aggregate by **month** (often the simplest)
- or aggregate by week but include **day-type weighting** (weekday/Sat/Sun/holiday) if available
- use **YoY same-month** comparisons as a lightweight seasonality control

---

## 4) Make outputs reproducible and “one command”

Right now, it’s easy for results to drift depending on how/when someone runs pieces of the workflow.

### Recommendation
Add a small “runner” entry point that:

- pulls the needed ridership data slice
- computes shares
- saves:
  - `outputs/share_timeseries.csv`
  - `outputs/share_summary.md`
  - and optionally a PNG chart

This doesn’t need orchestration tooling—just a deterministic script so you can re-run the sanity check quickly.

---

## 5) Testing: keep tests runnable with the declared dependencies

At least one test dependency boundary is leaky (tests import a library that is not installed by default).

### Recommendation
- Ensure test-only dependencies are declared under a dev/optional dependency group.
- Document the exact install command in README (e.g., `uv sync --group dev` / `uv pip install -e .[dev]`, depending on your tooling).

This keeps future changes from breaking test collection unexpectedly.

---

## 6) Data quality checks for the ridership dataset

Before interpreting share changes, it’s worth confirming you aren’t seeing artifacts:

### Recommendation
Add lightweight checks:

- missing months / unexpected gaps in the time series
- route name/code changes over time (route ID stability)
- outlier detection (spikes/zeros) and how you handle them
- confirm denominator (all routes) matches expectations for the period

---

## 7) “Answer-ready” deliverable format

If this is meant as a quick policy/advocacy sanity check, you’ll get the most value from a short, consistent output.

### Recommendation
Add a final markdown report that includes:

- a single headline figure: **share change pre vs post** (by phase)
- one chart: share over time
- a short interpretation section:
  - likely drivers (frequency increase vs broader demand)
  - limitations (data window, confounders)

---

## Suggested next steps (minimal)

1. Implement the ridership share notebook (monthly aggregation + share).
2. Add vertical phase markers and compute pre/post deltas.
3. Save outputs to `outputs/` with a single runner script.

That should get you to a defensible “yes/no/how much” answer with minimal extra engineering.
