#!/usr/bin/env python3
"""
Quick smoke test for the refactoring changes.

This script tests:
1. meta_utils module functionality
2. Handler registration and retrieval
3. CardHandler base classes work correctly
"""
import sys
import os

# Add dinq to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_meta_utils():
    """Test meta_utils functions."""
    print("Testing meta_utils...")
    from server.analyze.meta_utils import ensure_meta, extract_meta, is_fallback, should_preserve_empty
    
    # Test ensure_meta with dict
    payload = {"field": "value"}
    result = ensure_meta(payload, code="test", fallback=True)
    
    assert "_meta" in result, "ensure_meta should add _meta"
    assert result["_meta"]["code"] == "test"
    assert result["_meta"]["fallback"] is True
    assert result["_meta"]["preserve_empty"] is True
    print("  ✓ ensure_meta works")
    
    # Test extract_meta
    meta = extract_meta(result)
    assert isinstance(meta, dict)
    assert meta["code"] == "test"
    print("  ✓ extract_meta works")
    
    # Test is_fallback
    assert is_fallback(result) is True
    assert is_fallback({"field": "value"}) is False
    print("  ✓ is_fallback works")
    
    # Test should_preserve_empty
    assert should_preserve_empty(result) is True
    print("  ✓ should_preserve_empty works")
    
    print("meta_utils: ALL TESTS PASSED\n")


def test_handlers_base():
    """Test CardHandler base classes."""
    print("Testing handlers.base...")
    from server.analyze.handlers.base import CardResult, ExecutionContext, CardHandler, HandlerRegistry
    
    # Test CardResult
    result = CardResult(data={"test": "value"}, is_fallback=True, meta={"code": "test"})
    result_dict = result.to_dict()
    assert "_meta" in result_dict
    assert result_dict["_meta"]["fallback"] is True
    print("  ✓ CardResult.to_dict() works")
    
    # Test ExecutionContext
    ctx = ExecutionContext(
        job_id="test_job",
        card_id=1,
        user_id="user123",
        source="github",
        card_type="repos"
    )
    ctx.artifacts["resource.github.enrich"] = {"feature_project": {"name": "test"}}
    artifact = ctx.get_artifact("resource.github.enrich")
    assert artifact is not None
    assert artifact["feature_project"]["name"] == "test"
    print("  ✓ ExecutionContext.get_artifact() works")
    
    # Test HandlerRegistry
    registry = HandlerRegistry()
    
    # Create a dummy handler
    class DummyHandler(CardHandler):
        source = "test"
        card_type = "dummy"
        
        def execute(self, ctx):
            return CardResult(data={"dummy": "data"})
        
        def fallback(self, ctx, error=None):
            return CardResult(data={"dummy": "fallback"}, is_fallback=True)
    
    registry.register_class(DummyHandler)
    assert registry.has("test", "dummy")
    handler = registry.get("test", "dummy")
    assert handler is not None
    assert handler.source == "test"
    assert handler.card_type == "dummy"
    print("  ✓ HandlerRegistry works")
    
    print("handlers.base: ALL TESTS PASSED\n")


def test_github_handlers():
    """Test GitHub handlers."""
    print("Testing GitHub handlers...")
    from server.analyze.handlers.github.repos import GitHubReposHandler
    from server.analyze.handlers.base import ExecutionContext
    
    handler = GitHubReposHandler()
    assert handler.source == "github"
    assert handler.card_type == "repos"
    print("  ✓ GitHubReposHandler instantiated")
    
    # Test execute with mock context
    ctx = ExecutionContext(
        job_id="test",
        card_id=1,
        user_id="user",
        source="github",
        card_type="repos",
        artifacts={
            "resource.github.enrich": {
                "feature_project": {"name": "linux"},
                "top_projects": [{"name": "proj1"}],
                "most_valuable_pull_request": {"title": "Fix bug"}
            }
        }
    )
    
    result = handler.execute(ctx)
    assert result.data["feature_project"]["name"] == "linux"
    assert len(result.data["top_projects"]) == 1
    assert result.data["most_valuable_pull_request"]["title"] == "Fix bug"
    print("  ✓ GitHubReposHandler.execute() works")
    
    # Test validation
    assert handler.validate(result.data, ctx) is True
    assert handler.validate({"feature_project": None, "top_projects": []}, ctx) is False
    print("  ✓ GitHubReposHandler.validate() works")
    
    # Test fallback
    fallback_result = handler.fallback(ctx)
    assert fallback_result.is_fallback is True
    assert fallback_result.data["feature_project"] is None
    assert fallback_result.data["top_projects"] == []
    print("  ✓ GitHubReposHandler.fallback() works")
    
    print("GitHub handlers: ALL TESTS PASSED\n")


def test_linkedin_handlers():
    """Test LinkedIn handlers."""
    print("Testing LinkedIn handlers...")
    from server.analyze.handlers.linkedin.colleagues_view import LinkedInColleaguesViewHandler
    from server.analyze.handlers.base import ExecutionContext
    
    handler = LinkedInColleaguesViewHandler()
    assert handler.source == "linkedin"
    assert handler.card_type == "colleagues_view"
    print("  ✓ LinkedInColleaguesViewHandler instantiated")
    
    # Test execute
    ctx = ExecutionContext(
        job_id="test",
        card_id=1,
        user_id="user",
        source="linkedin",
        card_type="colleagues_view",
        artifacts={
            "resource.linkedin.enrich": {
                "colleagues_view": {
                    "highlights": ["Great communicator"],
                    "areas_for_improvement": ["Time management"]
                }
            }
        }
    )
    
    result = handler.execute(ctx)
    assert len(result.data["highlights"]) == 1
    assert len(result.data["areas_for_improvement"]) == 1
    print("  ✓ LinkedInColleaguesViewHandler.execute() works")
    
    # Test validation
    assert handler.validate(result.data, ctx) is True
    assert handler.validate({"highlights": [], "areas_for_improvement": []}, ctx) is False
    print("  ✓ LinkedInColleaguesViewHandler.validate() works")
    
    print("LinkedIn handlers: ALL TESTS PASSED\n")


def test_handler_registry():
    """Test global handler registry."""
    print("Testing global handler registry...")
    from server.analyze.handlers.registry import get_global_registry, get_handler, has_handler
    
    registry = get_global_registry()
    assert registry is not None
    print("  ✓ Global registry initialized")
    
    # Check GitHub handlers are registered
    assert has_handler("github", "repos")
    assert has_handler("github", "role_model")
    assert has_handler("github", "roast")
    assert has_handler("github", "summary")
    print("  ✓ GitHub handlers registered")
    
    # Check LinkedIn handlers are registered
    assert has_handler("linkedin", "colleagues_view")
    assert has_handler("linkedin", "life_well_being")
    print("  ✓ LinkedIn handlers registered")
    
    # Get a handler
    repos_handler = get_handler("github", "repos")
    assert repos_handler is not None
    assert repos_handler.card_type == "repos"
    print("  ✓ get_handler() works")
    
    print("Handler registry: ALL TESTS PASSED\n")


if __name__ == "__main__":
    print("="*60)
    print("dinq Refactoring Smoke Tests")
    print("="*60 + "\n")
    
    tests = [
        test_meta_utils,
        test_handlers_base,
        test_github_handlers,
        test_linkedin_handlers,
        test_handler_registry,
    ]
    
    failed = []
    for test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"  ✗ FAILED: {e}\n")
            failed.append((test_func.__name__, e))
    
    print("="*60)
    if not failed:
        print("✓ ALL TESTS PASSED!")
        print("="*60)
        sys.exit(0)
    else:
        print(f"✗ {len(failed)} TEST(S) FAILED:")
        for name, error in failed:
            print(f"  - {name}: {error}")
        print("="*60)
        sys.exit(1)
