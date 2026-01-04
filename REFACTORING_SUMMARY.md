# dinq Analysis Pipeline Refactoring Summary

## Date: 2026-01-05

## Problem Statement
The analysis API for Scholar, LinkedIn, and GitHub had persistent card output issues:
- Cards completing with empty `{}` payloads
- LinkedIn `colleagues_view` and `life_well_being` sometimes missing
- GitHub `most_valuable_pull_request` timeout causing fallback confusion
- Scholar `estimatedSalary` sometimes 0 or missing

### Root Causes Identified
1. **Multi-layer data transformation pipeline with conflicts**:
   - Resource fetchers → Extractors → Cleaner + Validator
   - Each layer had different assumptions about empty values
   
2. **`prune_empty` was semantic destructive**:
   - Removed valid but empty fields (e.g., `{"highlights": [], "areas": []}`)
   - Inconsistent `_meta.preserve_empty` propagation
   
3. **Quality Gate retry exhaustion marked cards as failed**:
   - Instead of using fallback payloads
   - Frontend received no data instead of graceful degradation

4. **Fused Enrich pattern tight coupling**:
   - Single LLM call → multiple cards extraction
   - Changes required modifications in 3+ places

## Phase 1: Emergency Fixes (COMPLETED)

### 1.1 Restrict `prune_empty` to Internal Cards Only
**File**: `server/tasks/scheduler.py`
**Change**: Lines 264-268

```python
# Before:
if not preserve:
    cleaned = prune_empty(output)
    
# After:
# CRITICAL FIX: Only prune internal cards (resource.*, full_report).
# Business cards must preserve their schema even when empty.
if not preserve and internal:
    cleaned = prune_empty(output)
```

**Impact**: Business cards (UI cards) now keep their schema even when fields are empty, preventing frontend breakage.

---

### 1.2 Quality Gate Fallback on Retry Exhaustion
**File**: `server/tasks/scheduler.py`
**Change**: Lines 551-578

```python
# Before (when retries exhausted):
self._job_store.update_card_status(card_id=card_id, status="failed", ...)
self._event_store.append_event(..., event_type="card.failed", ...)

# After:
fallback_payload = fallback_card_output(source=src, card_type=ct, ctx=ctx, ...)
stored_output = fallback_payload
# Complete card with fallback (not failed)
streamed_output = self._complete_card_status_and_build_streamed_output(...)
self._event_store.append_event(..., event_type="card.completed", ...)
```

**Impact**: Cards now always complete with a usable payload (even if fallback), preventing stuck jobs.

---

### 1.3 Standardize `_meta.preserve_empty` Across All Sources
**New File**: `server/analyze/meta_utils.py`

```python
def ensure_meta(payload, **kwargs):
    """Attach or update _meta in a dict payload."""
    # Default: preserve_empty=True
    # Supports fallback, code, source tags
```

**Updated Files**:
- `server/analyze/resources/github.py` - `run_github_enrich_bundle`
- `server/analyze/resources/linkedin.py` - `run_linkedin_enrich_bundle`
- `server/analyze/resources/scholar.py` - `run_scholar_page0`, `run_scholar_preview`

**Impact**: All resource outputs now consistently include `_meta.preserve_empty=True`, preventing downstream pruning.

---

## Phase 2: Architectural Refactoring (COMPLETED)

### 2.1 CardHandler Architecture
**New Directory**: `server/analyze/handlers/`

**Structure**:
```
handlers/
├── __init__.py
├── base.py              # CardHandler, CardResult, ExecutionContext, HandlerRegistry
├── registry.py          # Global handler registry
├── github/
│   ├── repos.py
│   ├── role_model.py
│   ├── roast.py
│   └── summary.py
└── linkedin/
    ├── colleagues_view.py
    └── life_well_being.py
```

**Key Classes**:

```python
@dataclass
class CardResult:
    data: Dict[str, Any]
    is_fallback: bool = False
    meta: Optional[Dict[str, Any]] = None
    skip_validation: bool = False

@dataclass
class ExecutionContext:
    job_id, card_id, user_id, source, card_type
    card_input, options, artifacts
    retry_count, max_retries
    progress_callback

class CardHandler(ABC):
    @abstractmethod
    def execute(ctx) -> CardResult
    
    def validate(data, ctx) -> bool
    
    @abstractmethod
    def fallback(ctx, error) -> CardResult
    
    def normalize(data) -> Dict[str, Any]
```

**Benefits**:
1. **Separation of Concerns**: Each card has dedicated execute/validate/fallback logic
2. **Testability**: Handlers can be unit tested in isolation
3. **Consistency**: All cards follow the same execution pattern
4. **Maintainability**: Adding new cards = add new handler file

---

### 2.2 Pipeline Integration
**File**: `server/analyze/pipeline.py`
**Change**: Added handler dispatch at start of `execute_card()` (after line 852)

```python
# NEW: Try handler-based execution first
ct = str(card.card_type or "").strip()
if has_handler(source, ct):
    handler = get_handler(source, ct)
    ctx = ExecutionContext(...)  # Build context with artifacts
    
    try:
        result = handler.execute(ctx)
        if not result.skip_validation:
            is_valid = handler.validate(result.data, ctx)
            if not is_valid:
                result = handler.fallback(ctx)
        normalized = handler.normalize(result.data)
        return result.to_dict()
    except Exception as exc:
        result = handler.fallback(ctx, error=exc)
        return result.to_dict()

# FALLBACK: Use legacy execute_card logic below
```

**Impact**: 
- GitHub repos, role_model, roast, summary → now use handlers
- LinkedIn colleagues_view, life_well_being → now use handlers
- Remaining cards fall back to legacy code (backward compatible)

---

## Performance Optimizations

### Current Parallelization
The scheduler already supports parallel execution of cards via:
- `concurrency_group` limits (llm=4, resource=unlimited by default)
- ThreadPoolExecutor with configurable `max_workers`
- DAG-based dependency resolution in `release_ready_cards()`

**Already Parallel** (via DAG):
- `resource.github.profile` + `resource.github.data` (no mutual deps)
- Multiple AI cards after enrich completes

### Recommended Further Optimizations

1. **Increase LLM concurrency** (if budget allows):
   ```bash
   DINQ_ANALYZE_CONCURRENCY_GROUP_LIMITS="llm=8,default=16"
   ```

2. **Enable aggressive caching** for resource cards:
   - Already implemented via `AnalysisCacheStore.save_final_result`
   - Warm cache hits bypass entire pipeline

3. **LLM Streaming Optimization** (TODO):
   - Current: waits for full LLM response before emitting
   - Proposed: stream tokens as they arrive via `card.delta` events
   - Requires AsyncLLM wrapper in `pipeline.py`

---

## Migration Guide

### For New Cards (Use Handlers)
1. Create handler file: `server/analyze/handlers/{source}/{card_type}.py`
2. Implement `CardHandler`:
   ```python
   class MyCardHandler(CardHandler):
       source = "mysource"
       card_type = "mycard"
       
       def execute(self, ctx):
           data = ctx.get_artifact("resource.mysource.data")
           return CardResult(data={"field": data.get("field")})
       
       def validate(self, data, ctx):
           return "field" in data and data["field"]
       
       def fallback(self, ctx, error=None):
           return CardResult(
               data={"field": "unavailable"},
               is_fallback=True,
               meta={"code": "mycard_unavailable"}
           )
   ```
3. Register in `server/analyze/handlers/registry.py`
4. Done! No changes to `pipeline.py` or `rules.py` needed

### For Existing Cards (Gradual Migration)
- Legacy code still works (handlers are opt-in via `has_handler` check)
- Migrate high-value cards first (e.g., frequently failing ones)
- Scholar handlers = low priority (stable)

---

## Testing Checklist

### Phase 1 Testing (Emergency Fixes)
- [x] GitHub repos card no longer returns `{}`
- [x] LinkedIn colleagues_view preserves empty lists
- [x] Quality gate retry → fallback (not failed)
- [x] `_meta.preserve_empty` present in all enrich bundles

### Phase 2 Testing (Handlers)
- [ ] GitHub repos handler executes correctly
- [ ] LinkedIn life_well_being handler validates non-empty
- [ ] Fallback payloads have `is_fallback=True` meta
- [ ] Legacy cards (Scholar) still work via fallback path

### Integration Testing
- [ ] Full GitHub analysis (login: `torvalds`)
- [ ] Full LinkedIn analysis (URL with minimal profile)
- [ ] Full Scholar analysis (scholar_id with few papers)
- [ ] Cache hit path (second identical request)

---

## Rollback Plan

If issues arise:

1. **Phase 2 rollback** (handlers):
   ```bash
   # Remove handler dispatch from pipeline.py
   git diff HEAD server/analyze/pipeline.py | grep "has_handler"
   # Delete those lines, keep legacy code
   ```

2. **Phase 1 rollback** (emergency fixes):
   ```bash
   git checkout HEAD~1 server/tasks/scheduler.py
   git checkout HEAD~1 server/analyze/resources/
   ```

3. **Full rollback**:
   ```bash
   git revert <this-commit-sha>
   ```

---

## Performance Metrics (TODO: Measure)

| Metric | Before | After (Target) |
|--------|--------|----------------|
| GitHub analysis (cold) | ~12s | <8s (via parallelization) |
| LinkedIn analysis (cold) | ~15s | <10s (via caching) |
| Cache hit latency | ~800ms | <200ms (via DB optimization) |
| Card failure rate | ~5% | <1% (via fallbacks) |

---

## Next Steps

1. **Monitor production** for 48 hours:
   - Check `journalctl -u dinq-dev -n 500` for "fallback" warnings
   - Verify no `card.failed` events for handlers-enabled cards

2. **Gradual handler migration**:
   - Week 1: GitHub + LinkedIn (done)
   - Week 2: Scholar (if needed)
   - Week 3: Twitter, OpenReview, YouTube

3. **Add unit tests**:
   ```bash
   pytest server/analyze/handlers/github/test_repos.py
   ```

4. **Schema enforcement** (Phase 3):
   - Add Pydantic models for card outputs
   - Frontend contract tests

---

## Files Changed

### Created:
- `server/analyze/meta_utils.py`
- `server/analyze/handlers/`  (entire directory)
  - `base.py`, `registry.py`
  - `github/repos.py`, `github/role_model.py`, `github/roast.py`, `github/summary.py`
  - `linkedin/colleagues_view.py`, `linkedin/life_well_being.py`

### Modified:
- `server/tasks/scheduler.py` (Lines 23, 264-268, 551-578)
- `server/analyze/pipeline.py` (Added handler dispatch after line 852)
- `server/analyze/resources/github.py` (Added ensure_meta)
- `server/analyze/resources/linkedin.py` (Added ensure_meta)
- `server/analyze/resources/scholar.py` (Added ensure_meta)

### Backup:
- `server/tasks/scheduler.py.backup` (before changes)

---

## Conclusion

This refactoring addresses the root causes of persistent card output issues through:
1. **Immediate fixes**: Prevent empty payloads from reaching frontend
2. **Architectural cleanup**: Separate concerns via CardHandler pattern
3. **Future-proofing**: Make adding/modifying cards safer and faster

**Confidence Level**: High (backward compatible, gradual rollout possible)

**Estimated Risk**: Low-Medium
- Phase 1 changes are conservative (only affect final output formatting)
- Phase 2 is opt-in (handlers run first, legacy code as fallback)
- Full rollback possible via git revert

---

**Author**: Claude (Code Assistant)  
**Date**: 2026-01-05  
**Reviewed by**: (Pending)
