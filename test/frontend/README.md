# DINQ Gateway Analyze Playground

This is a lightweight browser playground to test **Gateway** analyze APIs (create / status / SSE stream) and render card-by-card output.

## Run
1) Serve this folder
```
cd dinq/test/frontend
python -m http.server 8000
```

2) Open browser
- http://localhost:8000

## Notes
- Default `API Base` is `http://127.0.0.1:8001` (local Gateway / reverse proxy). You can switch to `https://api.dinq.me` if needed.
- Paste JWT into `Bearer JWT` (without `Bearer ` prefix is OK). Requests are sent with `Authorization: Bearer <jwt>`.
- Create job endpoint: `POST /api/v1/analyze`.
  - `mode=async`: returns `job_id`; then call SSE stream.
  - `mode=sync`: returns cards immediately (no streaming needed).
- SSE stream endpoint: `GET /api/v1/analyze/jobs/{job_id}/stream?after=<seq>`.
  - Supports断线续传：记录 `Last Seq`，重连时带 `after=<last_seq>`.
- Card output uses a unified envelope: `output = { data, stream }`.
  - `data`: final payload for the card (JSON object, string, etc).
  - `stream`: accumulated incremental text for snapshot/UX, keyed by `field -> { format, sections }`.
- `card.delta` payload includes `field/section/format/delta` so the UI can render structured incremental content.
- `card.started` / `card.completed` include `internal=true` for non-UI cards (`resource.*`, `full_report`). This playground hides internal cards by default.
- `Get Status` is a snapshot and includes **accumulated `output.stream`** so the UI can restore partial progress even if SSE is interrupted.
- Turn on **Debug mode** to show raw JSON / stream buffers / event log.
- **Recent Jobs** keeps the last few job_ids in localStorage for quick resume.
- Freeform candidates (模糊输入推荐)：勾选 `options.freeform`，若返回 `needs_confirmation=true`，先选候选再二次 create。
- Use **Save Screenshot** to export card output as PNG.
- Use **Load Mock** to preview GitHub/LinkedIn card templates without calling backend.

## If you hit CORS in browser (recommended local fix)

If your browser shows:
`No 'Access-Control-Allow-Origin' header ... blocked by CORS policy`

Run the built-in dev proxy server (serves static files + proxies `/api/*` to the real gateway):

```bash
cd dinq/test/frontend
python dev_proxy.py --port 8000 --upstream https://api.dinq.me
```

Then open `http://localhost:8000` and set UI `API Base` to `http://localhost:8000`.
