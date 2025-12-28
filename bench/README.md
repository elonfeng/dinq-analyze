# Analyze Bench (local sqlite)

This folder is **committed** so the team can share the same benchmark harness. Local runtime artifacts (sqlite DB, logs,
raw SSE/snapshots) are written under `.local/bench/` (gitignored).

## Quick start

From `dinq/`:

```bash
bash bench/run.sh
```

That will:
- start a local server on `127.0.0.1:8091` (sqlite DB),
- run the default sample set,
- save raw SSE + snapshot JSON + a summarized report under `.local/bench/output/<timestamp>/`.

By default it uses a **fresh sqlite DB per run** (so results are repeatable and won't conflict with any other local instance).

## Customize samples

Edit `bench/samples.json` and rerun.

## Advanced

Run the Python runner directly:

```bash
python bench/run_bench.py --help
```

## LLM bench (OpenRouter + Groq)

This bench calls provider APIs directly (no gateway), to compare **latency + JSON stability** for key tasks.

From `dinq/`:

```bash
python bench/run_llm_bench.py --n 8
```

Outputs are written to `.local/bench/llm/<timestamp>/` (gitignored):
- `report.json`: raw measurements
- `report.md`: per-task leaderboard
- `recommendations.env`: task-level env overrides to paste into `.env.production`
