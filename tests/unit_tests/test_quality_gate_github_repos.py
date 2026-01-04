from __future__ import annotations

from server.analyze.quality_gate import GateContext, validate_card_output


def _ctx(*, pr_total: int, repo_total: int = 1) -> GateContext:
    return GateContext(
        source="github",
        card_type="repos",
        full_report=None,
        artifacts={
            "resource.github.data": {
                "overview": {"repositories": repo_total},
                "user": {
                    "repositories": {"totalCount": repo_total},
                    "pullRequests": {"totalCount": pr_total},
                },
            }
        },
    )


def test_github_repos_allows_missing_mvp_pr_by_default() -> None:
    decision = validate_card_output(
        source="github",
        card_type="repos",
        data={
            "feature_project": None,
            "top_projects": [{"repository": {"name": "r"}}],
            "most_valuable_pull_request": None,
        },
        ctx=_ctx(pr_total=7, repo_total=2),
    )
    assert decision.action == "accept"
    assert isinstance(decision.normalized, dict)
    assert decision.normalized.get("most_valuable_pull_request") is None
    meta = decision.normalized.get("_meta")
    assert isinstance(meta, dict)
    assert meta.get("code") == "missing_mvp_pr"
    assert meta.get("missing") == ["most_valuable_pull_request"]


def test_github_repos_still_requires_any_repo_summary() -> None:
    decision = validate_card_output(
        source="github",
        card_type="repos",
        data={
            "feature_project": None,
            "top_projects": [],
            "most_valuable_pull_request": None,
        },
        ctx=_ctx(pr_total=0, repo_total=2),
    )
    assert decision.action == "retry"
    assert decision.issue is not None
    assert decision.issue.code == "missing_repos"
