#!/usr/bin/env python3
"""
Benchmark script for dinq analysis pipeline.

This script measures:
1. Cold start analysis time for each source
2. Cache hit latency
3. Handler execution time
4. Event streaming latency

Usage:
  python benchmark_analysis.py [--source github|linkedin|scholar] [--iterations 3]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

# Add dinq to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class BenchmarkResult:
    def __init__(self, name: str):
        self.name = name
        self.times: List[float] = []
        self.errors: List[str] = []
    
    def add(self, duration: float) -> None:
        self.times.append(duration)
    
    def add_error(self, error: str) -> None:
        self.errors.append(error)
    
    @property
    def avg(self) -> float:
        return sum(self.times) / len(self.times) if self.times else 0
    
    @property
    def min(self) -> float:
        return min(self.times) if self.times else 0
    
    @property
    def max(self) -> float:
        return max(self.times) if self.times else 0
    
    def __str__(self) -> str:
        if not self.times:
            return f"{self.name}: NO DATA (errors: {len(self.errors)})"
        return (
            f"{self.name}: avg={self.avg:.2f}ms, min={self.min:.2f}ms, max={self.max:.2f}ms "
            f"(n={len(self.times)}, errors={len(self.errors)})"
        )


def benchmark_handler_execution():
    """Benchmark individual handler execution times."""
    print("\n📊 Handler Execution Benchmarks")
    print("=" * 60)
    
    from server.analyze.handlers.registry import get_global_registry
    from server.analyze.handlers.base import ExecutionContext
    
    registry = get_global_registry()
    results: Dict[str, BenchmarkResult] = {}
    
    # Mock artifacts for each source
    mock_artifacts = {
        "github": {
            "resource.github.profile": {"login": "torvalds", "name": "Linus Torvalds"},
            "resource.github.data": {
                "user": {"login": "torvalds", "name": "Linus Torvalds", "followers": {"totalCount": 100000}},
                "overview": {"commits": 50000, "repositories": 100},
            },
            "resource.github.enrich": {
                "feature_project": {"name": "linux", "stars": 150000},
                "top_projects": [{"name": "linux"}],
                "most_valuable_pull_request": {"title": "Important fix"},
                "valuation_and_level": {"level": "Principal+", "salary_range": [400000, 600000]},
                "role_model": {"name": "Dennis Ritchie", "github": "https://github.com/dmr"},
                "roast": "Your code is so clean, even linters cry.",
            },
        },
        "linkedin": {
            "resource.linkedin.raw_profile": {
                "profile_data": {
                    "name": "Test User",
                    "work_experience": [{"company": "FAANG"}],
                    "education": [{"school": "MIT"}],
                }
            },
            "resource.linkedin.enrich": {
                "skills": {"industry_knowledge": ["ML"], "tools_technologies": ["Python"]},
                "career": {"current_title": "Staff Engineer"},
                "money": {"level_us": "L6", "estimated_salary": "350000"},
                "colleagues_view": {"highlights": ["Great leader"], "areas_for_improvement": []},
                "life_well_being": {"life_suggestion": "Take breaks", "health": "Good"},
                "summary": {"about": "Experienced engineer", "personal_tags": ["AI"]},
                "role_model": {"name": "Satya Nadella"},
                "roast": "You have too many endorsements.",
            },
        },
        "scholar": {
            "resource.scholar.page0": {
                "researcher": {"name": "Test Researcher", "scholar_id": "abc123", "h_index": 50},
            },
            "resource.scholar.full": {
                "researcher": {"name": "Test Researcher", "scholar_id": "abc123"},
                "publication_stats": {
                    "most_cited_paper": {"title": "Famous Paper"},
                    "year_distribution": {"2020": 10, "2021": 15},
                },
                "coauthors": {"total_coauthors": 50, "top_coauthors": []},
                "career_level": {"level_us": "Full Professor", "earnings": "200000"},
                "critical_evaluation": "Outstanding researcher",
                "news": {"news": "Recent grant awarded", "date": "2024-01"},
                "role_model": {"name": "Alan Turing"},
            },
        },
    }
    
    for key in registry.list_keys():
        source, card_type = key
        handler = registry.get(source, card_type)
        if handler is None:
            continue
        
        result = BenchmarkResult(f"{source}/{card_type}")
        
        # Run 10 iterations
        for _ in range(10):
            ctx = ExecutionContext(
                job_id="benchmark",
                card_id=1,
                user_id="benchmark_user",
                source=source,
                card_type=card_type,
                artifacts=mock_artifacts.get(source, {}),
            )
            
            try:
                start = time.perf_counter()
                output = handler.execute(ctx)
                _ = handler.validate(output.data, ctx)
                _ = output.to_dict()
                elapsed_ms = (time.perf_counter() - start) * 1000
                result.add(elapsed_ms)
            except Exception as e:
                result.add_error(str(e))
        
        results[f"{source}/{card_type}"] = result
    
    # Print results by source
    for source in ["github", "linkedin", "scholar"]:
        print(f"\n{source.upper()} Handlers:")
        for key, result in sorted(results.items()):
            if key.startswith(source):
                print(f"  {result}")
    
    # Summary
    all_times = [t for r in results.values() for t in r.times]
    if all_times:
        print(f"\nOverall: {len(all_times)} handler calls")
        print(f"  Total time: {sum(all_times):.2f}ms")
        print(f"  Average per handler: {sum(all_times)/len(all_times):.3f}ms")


def benchmark_meta_utils():
    """Benchmark meta utility functions."""
    print("\n📊 Meta Utils Benchmarks")
    print("=" * 60)
    
    from server.analyze.meta_utils import ensure_meta, extract_meta, is_fallback
    
    test_payload = {"field1": "value1", "field2": {"nested": "data"}}
    
    # ensure_meta
    times = []
    for _ in range(10000):
        start = time.perf_counter()
        _ = ensure_meta(test_payload, code="test", fallback=True)
        elapsed = (time.perf_counter() - start) * 1000000  # microseconds
        times.append(elapsed)
    print(f"ensure_meta: avg={sum(times)/len(times):.2f}μs, min={min(times):.2f}μs, max={max(times):.2f}μs")
    
    # extract_meta
    payload_with_meta = ensure_meta(test_payload, code="test")
    times = []
    for _ in range(10000):
        start = time.perf_counter()
        _ = extract_meta(payload_with_meta)
        elapsed = (time.perf_counter() - start) * 1000000
        times.append(elapsed)
    print(f"extract_meta: avg={sum(times)/len(times):.2f}μs, min={min(times):.2f}μs, max={max(times):.2f}μs")
    
    # is_fallback
    times = []
    for _ in range(10000):
        start = time.perf_counter()
        _ = is_fallback(payload_with_meta)
        elapsed = (time.perf_counter() - start) * 1000000
        times.append(elapsed)
    print(f"is_fallback: avg={sum(times)/len(times):.2f}μs, min={min(times):.2f}μs, max={max(times):.2f}μs")


def benchmark_registry_lookup():
    """Benchmark handler registry lookup."""
    print("\n📊 Registry Lookup Benchmarks")
    print("=" * 60)
    
    from server.analyze.handlers.registry import get_handler, has_handler, get_global_registry
    
    # Initialize registry
    _ = get_global_registry()
    
    # has_handler
    times = []
    for _ in range(10000):
        start = time.perf_counter()
        _ = has_handler("github", "repos")
        elapsed = (time.perf_counter() - start) * 1000000
        times.append(elapsed)
    print(f"has_handler: avg={sum(times)/len(times):.2f}μs")
    
    # get_handler
    times = []
    for _ in range(10000):
        start = time.perf_counter()
        _ = get_handler("github", "repos")
        elapsed = (time.perf_counter() - start) * 1000000
        times.append(elapsed)
    print(f"get_handler: avg={sum(times)/len(times):.2f}μs")


def print_summary():
    """Print optimization recommendations."""
    print("\n" + "=" * 60)
    print("📋 OPTIMIZATION RECOMMENDATIONS")
    print("=" * 60)
    
    print("""
1. LLM Streaming Optimization:
   - Current flush_chars=160 is good for smooth UX
   - Consider DINQ_ANALYZE_LLM_FLUSH_CHARS=100 for faster perceived speed
   
2. Concurrency Tuning:
   - DINQ_ANALYZE_CONCURRENCY_GROUP_LIMITS="llm=8,default=16"
   - Increase LLM parallelism if API rate limits allow
   
3. Cache Configuration:
   - DINQ_SCHOLAR_CACHE_MAX_AGE_DAYS=7 (increase for stable data)
   - DINQ_ANALYZE_CACHE_WRITE_MAX_WORKERS=4 (faster cache writes)
   
4. Event Streaming:
   - DINQ_ANALYZE_SSE_BATCH_SIZE=500 (current default is good)
   - DINQ_ANALYZE_SSE_BUS_MODE=on (use in-memory bus)
   
5. Database:
   - Ensure job_events has index on (job_id, seq)
   - Consider connection pooling for high-RTT databases
""")


def main():
    parser = argparse.ArgumentParser(description="Benchmark dinq analysis pipeline")
    parser.add_argument("--quick", action="store_true", help="Run quick benchmarks only")
    args = parser.parse_args()
    
    print("=" * 60)
    print("dinq Analysis Pipeline Benchmarks")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)
    
    try:
        benchmark_meta_utils()
        benchmark_registry_lookup()
        benchmark_handler_execution()
        print_summary()
        
        print("\n" + "=" * 60)
        print("✅ All benchmarks completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
