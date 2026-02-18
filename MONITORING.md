# Monitoring the Headway Pipeline

Post-deployment checklist for verifying the headway collection and analysis pipeline after the Feb 17, 2026 algorithm upgrade and data cleanup.

## Daily (30 seconds)

Check that the automated pipeline ran successfully:

```bash
gh run list --workflow=update-headways.yml --limit 3
```

If a run failed, check logs:

```bash
gh run view <run-id> --log
```

The most likely failure mode is a D1 query timeout as data grows.

Check the Worker is still collecting:

```bash
curl -s https://bus-check-collector.sbahamon1.workers.dev/health
```

## What to watch in the numbers

- **Route count stays at 20.** If a route drops off, something's wrong with collection or detection for that route.
- **Adherence stabilizes.** With limited data, individual routes can swing a lot day-to-day. Over a week they should settle. Wild swings might indicate a poorly-positioned reference point.
- **Route 34 (67% at launch).** Notable outlier — watch whether it stays low or converges upward. Could be genuinely bad performance or a reference point issue.
- **Headway counts grow proportionally.** At launch, most routes had 100-180 headways. After a week, expect roughly 5-7x that.

## After ~1 week (Feb 24)

~100+ hours of data across weekdays and a weekend.

- Compare weekday vs weekend adherence — weekends have a later service window start (9 AM vs 6 AM), so patterns may differ.
- Check if any routes have suspiciously few headways relative to others. Could indicate the reference point (midpoint of pdist range) isn't well-positioned for that route.

## After ~2 weeks (Mar 2)

The callout on the headway page will automatically switch from "Preliminary data" (yellow warning) to "Continuously updated" (info box) once `total_hours >= 336` (14 days x 24 hours). That threshold is set in `build_collection_stats` in `scripts/update_headways.py`.

At that point:
- Results are robust enough for real conclusions.
- Re-execute notebook 02 with the accumulated data: `uv pip install -e . && uv run --no-sync jupyter execute notebooks/02_headway_exploration.ipynb --inplace`
- Consider writing up findings for the headway page or a blog post.

## Baseline numbers (Feb 17, 2026 — 20 hours of data)

| Route | Phase | Adherence | Headways |
|-------|-------|-----------|----------|
| #77 Belmont | 3 | 97% | 179 |
| #79 79th | 1 | 96% | 171 |
| #20 Madison | 2 | 96% | 141 |
| #63 63rd | 1 | 94% | 134 |
| #72 North | 4 | 94% | 133 |
| #12 Roosevelt | 4 | 94% | 125 |
| #J14 Jeffery Jump | 1 | 93% | 116 |
| #66 Chicago | 2 | 93% | 164 |
| #53 Pulaski | 3 | 93% | 125 |
| #55 Garfield | 3 | 93% | 114 |
| #54 Cicero | 1 | 91% | 100 |
| #82 Kimball/Homan | 3 | 91% | 130 |
| #60 Blue Island/26th | 1 | 90% | 118 |
| #4 Cottage Grove | 2 | 89% | 122 |
| #49 Western | 2 | 89% | 120 |
| #47 47th | 1 | 88% | 105 |
| #95 95th | 1 | 88% | 102 |
| #81 Lawrence | 4 | 87% | 107 |
| #9 Ashland | 4 | 83% | 121 |
| #34 South Michigan | 1 | 67% | 51 |
| **Average** | | **90.3%** | |

## Useful commands

```bash
# Live Worker logs
cd worker && npx wrangler tail

# Manually trigger the daily pipeline
gh workflow run update-headways.yml

# Watch a workflow run
gh run watch <run-id>

# Check D1 data volume (requires Cloudflare credentials)
# The daily workflow logs print this at the start of each run
```
