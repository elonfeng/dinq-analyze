from __future__ import annotations

from server.llm.gateway import LLMGateway, RouteSpec, _env_task_policy, _env_task_routes, _parse_route_spec, _parse_routes


def test_parse_route_spec_plain_openrouter() -> None:
    r = _parse_route_spec("google/gemini-2.5-flash")
    assert r is not None
    assert r.provider == "openrouter"
    assert r.model == "google/gemini-2.5-flash"


def test_parse_route_spec_prefixed() -> None:
    r = _parse_route_spec("groq:llama-3.1-8b-instant")
    assert r is not None
    assert r.provider == "groq"
    assert r.model == "llama-3.1-8b-instant"


def test_parse_routes_dedupes() -> None:
    routes = _parse_routes("openrouter:google/gemini-2.5-flash, google/gemini-2.5-flash, groq:llama")
    assert [r.key() for r in routes] == ["openrouter:google/gemini-2.5-flash", "groq:llama"]


def test_resolve_routes_from_env(monkeypatch) -> None:
    gw = LLMGateway()
    monkeypatch.setenv(_env_task_routes("github_enrich_bundle"), "groq:llama-3.1-70b-versatile, openrouter:google/gemini-2.5-flash")
    routes = gw._resolve_routes(task="github_enrich_bundle", model=None)
    assert [r.provider for r in routes] == ["groq", "openrouter"]


def test_policy_default_fallback_for_json() -> None:
    gw = LLMGateway()
    routes = [RouteSpec(provider="openrouter", model="m1"), RouteSpec(provider="openrouter", model="m2")]
    assert gw._resolve_policy(task="t", routes=routes, expect_json=True, stream=False) == "fallback"


def test_policy_override_env(monkeypatch) -> None:
    gw = LLMGateway()
    routes = [RouteSpec(provider="openrouter", model="m1"), RouteSpec(provider="openrouter", model="m2")]
    monkeypatch.setenv(_env_task_policy("t"), "fallback")
    assert gw._resolve_policy(task="t", routes=routes, expect_json=True, stream=False) == "fallback"
