from __future__ import annotations
from server.analyze.meta_utils import ensure_meta

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

import requests

from server.utils.timing import elapsed_ms, now_perf
from server.llm.gateway import openrouter_chat


ProgressFn = Callable[[str, str, Optional[Dict[str, Any]]], None]

# Hardcoded Apify actor IDs (per ops requirement: no env-configurable actor ids).
_APIFY_LINKEDIN_FULL_ACTOR_ID = "2SyF0bVxmgGr8IVCZ"  # dev_fusion/Linkedin-Profile-Scraper
_APIFY_LINKEDIN_LITE_ACTOR_ID = "VhxlqQXRwhW8H5hNV"  # apimaestro/linkedin-profile-detail

# Timeouts for scraping. Keep constants to avoid env sprawl; adjust in code if needed.
_APIFY_LINKEDIN_LITE_PREFILL_TIMEOUT_S = 15.0  # How long we wait for a lite dataset item before aborting.
_APIFY_LINKEDIN_FULL_TIMEOUT_S = 90.0  # Global guard for the full scrape.


def _emit(progress: Optional[ProgressFn], step: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
    if progress:
        progress(step, message, data)


def _canonicalize_linkedin_url(url: str) -> str:
    """
    Normalize LinkedIn URLs for downstream scrapers (some actors are picky about domains/params).

    - Force https
    - Drop query/fragment
    - Normalize regional domains (e.g. ca.linkedin.com -> www.linkedin.com)
    """

    raw = str(url or "").strip()
    if not raw:
        return raw
    if raw.startswith("//"):
        raw = "https:" + raw
    if not re.match(r"^https?://", raw, flags=re.IGNORECASE):
        raw = "https://" + raw
    raw = re.sub(r"^http://", "https://", raw, flags=re.IGNORECASE)

    try:
        parts = urlsplit(raw)
        netloc = parts.netloc.lower()
        if netloc == "linkedin.com":
            netloc = "www.linkedin.com"
        if netloc.endswith(".linkedin.com") and netloc != "www.linkedin.com":
            netloc = "www.linkedin.com"
        cleaned = urlunsplit((parts.scheme, netloc, parts.path, "", ""))
        return cleaned.rstrip("/") if cleaned.endswith("/") else cleaned
    except Exception:
        return raw


def _infer_name_from_linkedin_url(url: str) -> str:
    cleaned = _canonicalize_linkedin_url(url)
    m = re.search(r"linkedin\.com/(?:in|company)/([^/?#]+)", cleaned, flags=re.IGNORECASE)
    if not m:
        return ""
    slug = (m.group(1) or "").strip()
    if not slug:
        return ""
    parts = [p for p in slug.split("-") if p]
    if parts and re.search(r"\d", parts[-1]):
        parts = parts[:-1]
    if not parts:
        return slug
    return " ".join([p[:1].upper() + p[1:] for p in parts if p]).strip()


def _resolve_url_and_name(analyzer, content: str, progress: Optional[ProgressFn]) -> Tuple[str, str]:
    raw = (content or "").strip()
    if not raw:
        raise ValueError("missing linkedin input")

    if "linkedin.com" in raw:
        url = _canonicalize_linkedin_url(raw)
        inferred = _infer_name_from_linkedin_url(url)
        return url, inferred or url

    person_name = raw
    _emit(progress, "searching", f"Searching LinkedIn URL for {person_name}...", None)
    results = analyzer.search_linkedin_url(person_name)
    if not results:
        raise ValueError(f'No LinkedIn profile found for "{person_name}"')
    url = _canonicalize_linkedin_url(str(results[0].get("url") or "").strip())
    if not url:
        raise ValueError(f'No LinkedIn URL found for "{person_name}"')
    return url, person_name


def fetch_linkedin_preview(*, content: str, progress: Optional[ProgressFn] = None) -> Dict[str, Any]:
    """
    Fast-first LinkedIn preview:
      - resolves the profile URL
      - emits a degraded `profile` prefill immediately

    Does NOT perform the long-tail raw scraping step.
    """

    t0 = now_perf()

    raw = str(content or "").strip()
    if "linkedin.com" in raw:
        linkedin_url = _canonicalize_linkedin_url(raw)
        person_name = _infer_name_from_linkedin_url(linkedin_url) or linkedin_url

        # Match LinkedInAnalyzer.generate_linkedin_id() semantics for cache keys.
        if "linkedin.com/in/" in linkedin_url:
            linkedin_id = linkedin_url.split("linkedin.com/in/")[1].split("?")[0].split("/")[0]
        else:
            linkedin_id = f"name:{person_name.lower().replace(' ', '_')}"
    else:
        from server.api.linkedin_analyzer_api import get_linkedin_analyzer  # local import (heavy; only needed for name->url)

        analyzer = get_linkedin_analyzer()
        linkedin_url, person_name = _resolve_url_and_name(analyzer, content, progress)
        linkedin_id = analyzer.generate_linkedin_id(person_name, linkedin_url)

    _emit(progress, "timing.linkedin.resolve", "Resolved LinkedIn identity", {"duration_ms": elapsed_ms(t0)})

    try:
        _emit(
            progress,
            "preview.linkedin.profile",
            "LinkedIn profile preview ready (fetching raw profile in background)",
            {
                "prefill_cards": [
                    {
                        "card": "profile",
                        "data": {
                            "avatar": "",
                            "name": person_name,
                            "about": "",
                            "work_experience": [],
                            "education": [],
                        },
                        "meta": {
                            "partial": True,
                            "degraded": True,
                            "reason": "fetching_raw_profile",
                            "candidate_url": linkedin_url,
                        },
                    }
                ]
            },
        )
    except Exception:
        pass

    apify_full_run_id = ""
    apify_full_dataset_id = ""
    apify_lite_run_id = ""
    apify_lite_dataset_id = ""

    # Kick off Apify runs as early as possible (preview is the first LinkedIn DAG card).
    # The downstream raw_profile card can reuse these run IDs and emit lite prefill faster.
    try:
        from apify_client import ApifyClient

        token = str(os.getenv("APIFY_API_KEY") or "").strip()
        apify_client = ApifyClient(token) if token else None
    except Exception:
        apify_client = None

    if apify_client is not None and isinstance(linkedin_url, str) and linkedin_url.strip():
        # Lite first for fast UI prefill.
        try:
            run = apify_client.actor(_APIFY_LINKEDIN_LITE_ACTOR_ID).start(
                run_input={"username": linkedin_url, "includeEmail": False},
                wait_for_finish=0,
            )
            if isinstance(run, dict):
                apify_lite_run_id = str(run.get("id") or "").strip()
                apify_lite_dataset_id = str(run.get("defaultDatasetId") or "").strip()
        except Exception:
            pass

        try:
            run = apify_client.actor(_APIFY_LINKEDIN_FULL_ACTOR_ID).start(
                run_input={"profileUrls": [linkedin_url]},
                wait_for_finish=0,
            )
            if isinstance(run, dict):
                apify_full_run_id = str(run.get("id") or "").strip()
                apify_full_dataset_id = str(run.get("defaultDatasetId") or "").strip()
        except Exception:
            pass

    return {
        "_linkedin_url": linkedin_url,
        "_linkedin_id": linkedin_id,
        "_apify": {
            "lite": {
                "actor_id": _APIFY_LINKEDIN_LITE_ACTOR_ID,
                "run_id": apify_lite_run_id or None,
                "dataset_id": apify_lite_dataset_id or None,
            },
            "full": {
                "actor_id": _APIFY_LINKEDIN_FULL_ACTOR_ID,
                "run_id": apify_full_run_id or None,
                "dataset_id": apify_full_dataset_id or None,
            },
        },
        "profile_data": {
            "avatar": "",
            "name": person_name,
            "about": "",
            "work_experience": [],
            "education": [],
        },
    }


def fetch_linkedin_raw_profile(
    *,
    content: str,
    progress: Optional[ProgressFn] = None,
    linkedin_url: Optional[str] = None,
    person_name: Optional[str] = None,
    apify_full_run_id: Optional[str] = None,
    apify_full_dataset_id: Optional[str] = None,
    apify_lite_run_id: Optional[str] = None,
    apify_lite_dataset_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch raw LinkedIn profile data and return a partial full_report-like dict.

    The returned object is shaped so that `extract_card_payload("linkedin", report, "profile")`
    works immediately (even before AI enrichments).
    """

    from server.api.linkedin_analyzer_api import get_linkedin_analyzer  # local import (heavy)

    analyzer = get_linkedin_analyzer()
    t0 = now_perf()
    resolved_url = str(linkedin_url or "").strip() if linkedin_url else ""
    resolved_name = str(person_name or "").strip() if person_name else ""
    if not resolved_url:
        resolved_url, resolved_name = _resolve_url_and_name(analyzer, content, progress)
    resolved_url = _canonicalize_linkedin_url(resolved_url)
    if not resolved_name:
        resolved_name = resolved_url if "linkedin.com" in resolved_url else (content or "").strip() or "Unknown"
    _emit(progress, "timing.linkedin.resolve", "Resolved LinkedIn identity", {"duration_ms": elapsed_ms(t0)})
    # Avoid duplicate degraded prefill: resource.linkedin.preview already emits the placeholder.
    # Keep backward-compat for callers that invoke raw_profile directly (no preview artifact).
    upstream_prefilled = bool(str(linkedin_url or "").strip() and str(person_name or "").strip())
    if not upstream_prefilled:
        try:
            _emit(
                progress,
                "preview.linkedin.profile",
                "LinkedIn profile preview ready (fetching raw profile in background)",
                {
                    "prefill_cards": [
                        {
                            "card": "profile",
                            "data": {
                                "avatar": "",
                                "name": resolved_name,
                                "about": "",
                                "work_experience": [],
                                "education": [],
                            },
                            "meta": {
                                "partial": True,
                                "degraded": True,
                                "reason": "fetching_raw_profile",
                                "candidate_url": resolved_url,
                            },
                        }
                    ]
                },
            )
        except Exception:
            pass

    _emit(progress, "fetching", "Fetching LinkedIn profile details...", None)
    t1 = now_perf()

    # Multi-actor strategy (recommended):
    # - Start a full Apify scrape run (required for experiences/educations).
    # - Start a lite Apify scrape run in parallel and emit an upgraded profile prefill
    #   (avatar/headline/about/location) as soon as the lite dataset item becomes available.

    full_actor_id = _APIFY_LINKEDIN_FULL_ACTOR_ID
    lite_actor_id = _APIFY_LINKEDIN_LITE_ACTOR_ID if _APIFY_LINKEDIN_LITE_PREFILL_TIMEOUT_S > 0 else ""
    if lite_actor_id and lite_actor_id == full_actor_id:
        lite_actor_id = ""

    lite_timeout_s = float(max(0.0, min(_APIFY_LINKEDIN_LITE_PREFILL_TIMEOUT_S, 30.0)))
    full_timeout_s = float(max(5.0, min(_APIFY_LINKEDIN_FULL_TIMEOUT_S, 600.0)))

    def _dataset_first_item(dataset_id: str) -> Optional[Dict[str, Any]]:
        if not dataset_id:
            return None
        try:
            dataset = analyzer.apifyclient.dataset(dataset_id)  # type: ignore[union-attr]
            try:
                items = dataset.list_items(limit=1).items
            except Exception:
                items = dataset.list_items().items
            if not items:
                return None
            item0 = items[0]
            return analyzer.convert_datetime_for_json(item0) if hasattr(analyzer, "convert_datetime_for_json") else item0
        except Exception:
            return None

    def _extract_prefill_fields(profile: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(profile, dict):
            return {}
        name = (
            profile.get("fullName")
            or profile.get("name")
            or profile.get("full_name")
            or profile.get("personName")
        )
        avatar = (
            profile.get("profilePicHighQuality")
            or profile.get("profilePic")
            or profile.get("profile_pic")
            or profile.get("profilePicture")
            or profile.get("profilePictureUrl")
        )
        headline = profile.get("headline") or profile.get("occupation") or profile.get("jobTitle")
        about = profile.get("about") or profile.get("summary") or profile.get("bio")
        location = profile.get("addressWithCountry") or profile.get("location") or profile.get("addressWithoutCountry")
        out: Dict[str, Any] = {}
        if isinstance(name, str) and name.strip():
            out["name"] = name.strip()
        if isinstance(avatar, str) and avatar.strip():
            out["avatar"] = avatar.strip()
        if isinstance(headline, str) and headline.strip():
            out["headline"] = headline.strip()
        if isinstance(location, str) and location.strip():
            out["location"] = location.strip()
        if isinstance(about, str) and about.strip():
            out["about"] = about.strip()
        return out

    def _merge_lite_into_full(full_profile: Dict[str, Any], lite_profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(full_profile, dict):
            full_profile = {}
        lite = lite_profile if isinstance(lite_profile, dict) else {}
        if not lite:
            return full_profile

        merged = dict(full_profile)

        def _is_empty(v: Any) -> bool:
            if v is None:
                return True
            if isinstance(v, str) and not v.strip():
                return True
            if isinstance(v, (list, dict)) and not v:
                return True
            return False

        # Prefer full for large lists; only fill scalar UI-critical fields from lite when missing.
        for k in (
            "fullName",
            "headline",
            "occupation",
            "jobTitle",
            "location",
            "addressWithCountry",
            "addressWithoutCountry",
            "companyName",
            "companyIndustry",
            "connections",
            "followers",
            "about",
        ):
            if _is_empty(merged.get(k)) and not _is_empty(lite.get(k)):
                merged[k] = lite.get(k)

        # Avatar: fill profilePic from lite variants if missing.
        if _is_empty(merged.get("profilePic")):
            for k in ("profilePicHighQuality", "profilePic", "profilePictureUrl", "profilePicture"):
                if not _is_empty(lite.get(k)):
                    merged["profilePic"] = lite.get(k)
                    break

        # Cross-actor schema drift guard: map common alternates into the canonical keys we use downstream.
        lite_fields = _extract_prefill_fields(lite)
        if _is_empty(merged.get("fullName")) and not _is_empty(lite_fields.get("name")):
            merged["fullName"] = lite_fields.get("name")
        if _is_empty(merged.get("headline")) and not _is_empty(lite_fields.get("headline")):
            merged["headline"] = lite_fields.get("headline")
        if _is_empty(merged.get("about")) and not _is_empty(lite_fields.get("about")):
            merged["about"] = lite_fields.get("about")
        if _is_empty(merged.get("addressWithCountry")) and not _is_empty(lite_fields.get("location")):
            merged["addressWithCountry"] = lite_fields.get("location")
        if _is_empty(merged.get("profilePic")) and not _is_empty(lite_fields.get("avatar")):
            merged["profilePic"] = lite_fields.get("avatar")

        return merged

    raw_profile: Optional[Dict[str, Any]] = None
    lite_profile: Optional[Dict[str, Any]] = None

    # If Apify client isn't available, fall back to the legacy blocking call.
    apify_client = getattr(analyzer, "apifyclient", None)
    if apify_client is None:
        raw_profile = analyzer.get_linkedin_profile(resolved_url)
    else:
        def _run_input_full(url: str) -> Dict[str, Any]:
            # dev_fusion/Linkedin-Profile-Scraper
            return {"profileUrls": [url]}

        def _run_input_lite(url: str) -> Dict[str, Any]:
            # apimaestro/linkedin-profile-detail
            return {"username": url, "includeEmail": False}

        def _normalize_lite_item(item: Dict[str, Any]) -> Dict[str, Any]:
            # apimaestro returns {"basic_info": {...}, "experience": [...], "education": [...]}
            if lite_actor_id != _APIFY_LINKEDIN_LITE_ACTOR_ID:
                return item
            basic = item.get("basic_info")
            if not isinstance(basic, dict):
                return item

            out: Dict[str, Any] = {}

            full_name = basic.get("fullname") or basic.get("full_name") or basic.get("fullName")
            if isinstance(full_name, str) and full_name.strip():
                out["fullName"] = full_name.strip()

            avatar = basic.get("profile_picture_url") or basic.get("profilePic") or basic.get("profilePicHighQuality")
            if isinstance(avatar, str) and avatar.strip():
                out["profilePic"] = avatar.strip()

            headline = basic.get("headline")
            if isinstance(headline, str) and headline.strip():
                out["headline"] = headline.strip()

            about = basic.get("about")
            if isinstance(about, str) and about.strip():
                out["about"] = about.strip()

            loc = basic.get("location")
            loc_full = ""
            if isinstance(loc, dict):
                loc_full = str(loc.get("full") or loc.get("city") or loc.get("country") or "").strip()
            elif isinstance(loc, str):
                loc_full = loc.strip()
            if loc_full:
                out["addressWithCountry"] = loc_full

            if basic.get("connection_count") is not None:
                out["connections"] = basic.get("connection_count")
            if basic.get("follower_count") is not None:
                out["followers"] = basic.get("follower_count")
            if basic.get("current_company") is not None:
                out["companyName"] = basic.get("current_company")

            return out or item

        run_input_full = _run_input_full(resolved_url)
        run_input_lite = _run_input_lite(resolved_url)
        full_run = None
        lite_run = None

        # Reuse Apify runs started by the preview card (best-effort).
        pref_full_run_id = str(apify_full_run_id or "").strip()
        pref_full_dataset_id = str(apify_full_dataset_id or "").strip()
        if pref_full_run_id and pref_full_dataset_id:
            full_run = {"id": pref_full_run_id, "defaultDatasetId": pref_full_dataset_id}

        pref_lite_run_id = str(apify_lite_run_id or "").strip()
        pref_lite_dataset_id = str(apify_lite_dataset_id or "").strip()
        if pref_lite_dataset_id:
            lite_run = {"id": pref_lite_run_id, "defaultDatasetId": pref_lite_dataset_id}

        if lite_actor_id:
            if not (isinstance(lite_run, dict) and lite_run.get("defaultDatasetId")):
                try:
                    lite_run = apify_client.actor(lite_actor_id).start(run_input=run_input_lite, wait_for_finish=0)
                except Exception:
                    lite_run = None
        if not (isinstance(full_run, dict) and full_run.get("id") and full_run.get("defaultDatasetId")):
            try:
                full_run = apify_client.actor(full_actor_id).start(run_input=run_input_full, wait_for_finish=0)
            except Exception:
                full_run = None

        if not isinstance(full_run, dict) or not full_run.get("id") or not full_run.get("defaultDatasetId"):
            # Fallback: old path (single full call).
            raw_profile = analyzer.get_linkedin_profile(resolved_url)
        else:
            full_run_id = str(full_run.get("id") or "").strip()
            full_dataset_id = str(full_run.get("defaultDatasetId") or "").strip()

            lite_run_id = str((lite_run or {}).get("id") or "").strip() if isinstance(lite_run, dict) else ""
            lite_dataset_id = str((lite_run or {}).get("defaultDatasetId") or "").strip() if isinstance(lite_run, dict) else ""

            lite_emitted = False
            start_poll = now_perf()

            # Poll loop: opportunistically emit lite prefill while waiting for the full run to finish.
            while True:
                elapsed_s = (now_perf() - start_poll)

                if (not lite_emitted) and lite_dataset_id and (elapsed_s <= lite_timeout_s):
                    lite_item_raw = _dataset_first_item(lite_dataset_id)
                    lite_item = _normalize_lite_item(lite_item_raw) if lite_item_raw else None
                    if lite_item:
                        lite_profile = lite_item
                        fields = _extract_prefill_fields(lite_item)
                        if fields:
                            try:
                                data = {
                                    "name": fields.get("name") or resolved_name,
                                    "avatar": fields.get("avatar") or "",
                                    "headline": fields.get("headline") or "",
                                    "location": fields.get("location") or "",
                                    "about": fields.get("about") or "",
                                    "work_experience": [],
                                    "education": [],
                                }
                                _emit(
                                    progress,
                                    "preview.linkedin.profile",
                                    "LinkedIn profile lite preview ready (fetching full profile in background)",
                                    {
                                        "prefill_cards": [
                                            {
                                                "card": "profile",
                                                "data": data,
                                                "meta": {
                                                    "partial": True,
                                                    "degraded": False,
                                                    "reason": "apify_lite_prefill",
                                                    "candidate_url": resolved_url,
                                                    "provider": "apify",
                                                    "actor_id": lite_actor_id,
                                                    "run_id": lite_run_id,
                                                },
                                            }
                                        ]
                                    },
                                )
                            except Exception:
                                pass
                        lite_emitted = True
                        if lite_run_id:
                            try:
                                apify_client.run(lite_run_id).abort(gracefully=True)
                            except Exception:
                                pass

                # If lite times out without yielding anything, abort it best-effort to avoid extra cost.
                if (not lite_emitted) and lite_run_id and (lite_timeout_s > 0) and (elapsed_s > lite_timeout_s):
                    try:
                        apify_client.run(lite_run_id).abort(gracefully=True)
                    except Exception:
                        pass
                    lite_emitted = True  # stop checking

                # Wait for the full run to finish (1s wait to allow frequent lite polling).
                try:
                    run_state = apify_client.run(full_run_id).wait_for_finish(wait_secs=1)
                except Exception:
                    run_state = None

                status = (run_state or {}).get("status") if isinstance(run_state, dict) else None
                if status in ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"):
                    if status != "SUCCEEDED":
                        raise ValueError(f"Apify run failed with status: {status}")
                    break

                # Global timeout guard for the full scrape.
                if elapsed_s >= full_timeout_s:
                    try:
                        apify_client.run(full_run_id).abort(gracefully=True)
                    except Exception:
                        pass
                    raise ValueError("Timed out fetching LinkedIn profile from Apify")

                # Small pacing to avoid tight loops if wait_for_finish returned immediately.
                time.sleep(0.05)

            # Pull the final profile from the full dataset.
            full_item = _dataset_first_item(full_dataset_id)
            if not full_item:
                raise ValueError("No items found in Apify dataset")

            raw_profile = _merge_lite_into_full(full_item, lite_profile)

            # Best-effort: stop lite run if still running.
            if lite_run_id:
                try:
                    apify_client.run(lite_run_id).abort(gracefully=True)
                except Exception:
                    pass

    _emit(progress, "timing.linkedin.raw_profile", "Fetched LinkedIn raw profile", {"duration_ms": elapsed_ms(t1)})
    if not raw_profile:
        raise ValueError("Failed to fetch LinkedIn profile; please verify the URL or try again")

    resolved_name = raw_profile.get("fullName") or resolved_name
    linkedin_id = analyzer.generate_linkedin_id(resolved_name, resolved_url)

    # NOTE: The Apify blob can be large and is not required by the frontend contract.
    # Keep the UI-facing lists in `work_experience`/`education`, and store a pruned raw_profile
    # without duplicating experiences/educations.
    work_experience = raw_profile.get("experiences", []) or []
    education = raw_profile.get("educations", []) or []

    def _prune_for_storage(profile: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(profile, dict) or not profile:
            return {}
        keep_keys = {
            # Identity + UI hints
            "fullName",
            "name",
            "profilePic",
            "profilePicHighQuality",
            "headline",
            "occupation",
            "jobTitle",
            "location",
            "addressWithCountry",
            "addressWithoutCountry",
            "companyName",
            "companyIndustry",
            "connections",
            "followers",
            "about",
            # Useful for LLM compaction (small-ish)
            "skills",
            "languages",
        }
        out: Dict[str, Any] = {}
        for k in keep_keys:
            if profile.get(k) is not None:
                out[k] = profile.get(k)
        # Safety fallback: if the whitelist misses everything, still drop the biggest duplicated lists.
        if not out:
            out = {k: v for k, v in profile.items() if k not in ("experiences", "educations")}
        return out

    raw_profile_store = _prune_for_storage(raw_profile)

    headline = str(raw_profile.get("headline") or raw_profile.get("occupation") or raw_profile.get("jobTitle") or "").strip()
    location = str(raw_profile.get("addressWithCountry") or raw_profile.get("location") or raw_profile.get("addressWithoutCountry") or "").strip()

    report = {
        "_linkedin_url": resolved_url,
        "_linkedin_id": linkedin_id,
        "profile_data": {
            "avatar": raw_profile.get("profilePic") or raw_profile.get("profilePicHighQuality"),
            "name": resolved_name,
            "headline": headline,
            "location": location,
            "about": raw_profile.get("about") or "",
            "work_experience": work_experience,
            "education": education,
            "raw_profile": raw_profile_store,
        },
    }
    return report


def run_linkedin_ai_enrich(*, raw_report: Dict[str, Any], progress: Optional[ProgressFn] = None) -> Dict[str, Any]:
    """
    Run AI enrichments for LinkedIn based on an already fetched raw profile.

    Returns a full_report-like dict compatible with the legacy schema.
    """

    from server.api.linkedin_analyzer_api import get_linkedin_analyzer  # local import (heavy)

    analyzer = get_linkedin_analyzer()
    report_profile = (raw_report or {}).get("profile_data") if isinstance((raw_report or {}).get("profile_data"), dict) else {}
    raw_profile = (report_profile.get("raw_profile") or {}) if isinstance(report_profile.get("raw_profile"), dict) else {}
    if not isinstance(raw_profile, dict) or not raw_profile:
        raise ValueError("missing raw_profile for linkedin ai enrich")

    # raw_profile may be pruned for storage; restore experience/education lists for AI prompts.
    exp = report_profile.get("work_experience") if isinstance(report_profile.get("work_experience"), list) else []
    edu = report_profile.get("education") if isinstance(report_profile.get("education"), list) else []
    if exp and (not isinstance(raw_profile.get("experiences"), list) or not raw_profile.get("experiences")):
        raw_profile = dict(raw_profile)
        raw_profile["experiences"] = exp
    if edu and (not isinstance(raw_profile.get("educations"), list) or not raw_profile.get("educations")):
        raw_profile = dict(raw_profile)
        raw_profile["educations"] = edu

    linkedin_url = str((raw_report or {}).get("_linkedin_url") or "").strip() or None
    person_name = raw_profile.get("fullName") or report_profile.get("name") or ""
    if not person_name:
        person_name = "Unknown"

    linkedin_id = str((raw_report or {}).get("_linkedin_id") or "").strip()
    if not linkedin_id:
        linkedin_id = analyzer.generate_linkedin_id(person_name, linkedin_url or "")

    _emit(progress, "analyzing", "Analyzing LinkedIn profile data...", None)
    analysis_result = analyzer.process_linkedin_data(raw_profile, person_name, linkedin_url, linkedin_id) or {}
    if not isinstance(analysis_result, dict):
        analysis_result = {}

    # Parallel AI tasks (best-effort with fallbacks; matches legacy analyzer behavior)
    tasks = []

    def _task(name: str, fn, args, fallback):
        def run():
            try:
                return name, fn(*args)
            except Exception:
                return name, fallback
        return run

    from server.linkedin_analyzer.role_model_service import get_linkedin_role_model
    from server.linkedin_analyzer.money_service import get_linkedin_money_analysis
    from server.linkedin_analyzer.roast_service import get_linkedin_roast
    from server.linkedin_analyzer.industry_knowledge_service import get_linkedin_industry_knowledge
    from server.linkedin_analyzer.tools_technologies_service import get_linkedin_tools_technologies
    from server.linkedin_analyzer.interpersonal_skills_service import get_linkedin_interpersonal_skills
    from server.linkedin_analyzer.language_service import get_linkedin_languages
    from server.linkedin_analyzer.colleagues_view_service import get_linkedin_colleagues_view, create_default_colleagues_view
    from server.linkedin_analyzer.career_service import get_linkedin_career
    from server.linkedin_analyzer.life_well_being_service import get_linkedin_life_well_being, create_default_life_well_being

    tasks.append(_task("role_model", get_linkedin_role_model, (raw_profile, person_name), None))
    tasks.append(_task("money_analysis", get_linkedin_money_analysis, (raw_profile, person_name), None))
    tasks.append(_task("roast", get_linkedin_roast, (raw_profile, person_name), "No roast available"))
    tasks.append(_task("industry_knowledge", get_linkedin_industry_knowledge, (raw_profile, person_name), []))
    tasks.append(_task("tools_technologies", get_linkedin_tools_technologies, (raw_profile, person_name), []))
    tasks.append(_task("interpersonal_skills", get_linkedin_interpersonal_skills, (raw_profile, person_name), []))
    tasks.append(_task("language", get_linkedin_languages, (raw_profile, person_name), []))
    colleagues_fallback = create_default_colleagues_view(raw_profile, person_name)
    tasks.append(_task("colleagues_view", get_linkedin_colleagues_view, (raw_profile, person_name), colleagues_fallback))
    tasks.append(_task("career", get_linkedin_career, (raw_profile, person_name), {"future_development_potential": "", "development_advice": {"past_evaluation": "", "future_advice": ""}}))
    life_well_being_fallback = create_default_life_well_being(raw_profile, person_name)
    tasks.append(_task("life_well_being", get_linkedin_life_well_being, (raw_profile, person_name), life_well_being_fallback))

    results: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=max(4, len(tasks))) as executor:
        future_to_name = {executor.submit(t): i for i, t in enumerate(tasks)}
        total = max(1, len(future_to_name))
        completed = 0
        for fut in as_completed(future_to_name):
            try:
                name, value = fut.result()
                results[name] = value
            except Exception:
                pass
            completed += 1
            _emit(progress, "ai_step", f"LinkedIn AI step {completed}/{total} completed", {"completed": completed, "total": total})

    personal_tags = analyzer.extract_personal_tags(raw_profile)
    work_summary = analyzer.generate_work_experience_summary(raw_profile.get("experiences", []) or [])
    education_summary = analyzer.generate_education_summary(raw_profile.get("educations", []) or [])

    about_content = raw_profile.get("about")
    if not about_content or not str(about_content).strip():
        about_content = analyzer.generate_ai_about_section(raw_profile, person_name)

    profile_data = analysis_result.get("profile_data") if isinstance(analysis_result.get("profile_data"), dict) else {}
    profile_data.update(
        {
            "role_model": results.get("role_model"),
            "money_analysis": results.get("money_analysis"),
            "roast": results.get("roast"),
            "skills": {
                "industry_knowledge": results.get("industry_knowledge", []),
                "tools_technologies": results.get("tools_technologies", []),
                "interpersonal_skills": results.get("interpersonal_skills", []),
                "language": results.get("language", []),
            },
            "colleagues_view": results.get("colleagues_view"),
            "career": results.get("career"),
            "life_well_being": results.get("life_well_being"),
            "about": about_content,
            "personal_tags": personal_tags,
            "work_experience": raw_profile.get("experiences", []) or [],
            "work_experience_summary": work_summary,
            "education": raw_profile.get("educations", []) or [],
            "education_summary": education_summary,
            "avatar": raw_profile.get("profilePic"),
            "name": raw_profile.get("fullName") or person_name,
            "raw_profile": raw_profile,
        }
    )

    analysis_result["profile_data"] = profile_data
    return analysis_result


def _compact_linkedin_profile_for_llm(raw_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compact raw LinkedIn profile payload for LLM consumption.

    Apify raw profiles can be large; keep only stable, high-signal fields to control token/latency.
    """

    def _take_list(value: Any, *, limit: int) -> list:
        if not isinstance(value, list):
            return []
        return [v for v in value[: max(0, int(limit))] if v is not None]

    def _norm_text(value: Any, *, limit: int = 260) -> str:
        if value is None:
            return ""
        s = str(value).strip()
        if not s:
            return ""
        # Collapse whitespace and hard-trim long descriptions to keep prompts small.
        s = " ".join(s.split())
        if len(s) > int(limit):
            return s[: max(0, int(limit) - 1)].rstrip() + "…"
        return s

    def _compact_experience(exp: Any) -> Dict[str, Any]:
        if not isinstance(exp, dict):
            return {}
        return {
            "title": _norm_text(exp.get("title") or exp.get("position") or exp.get("jobTitle"), limit=80),
            "company": _norm_text(exp.get("companyName") or exp.get("company") or exp.get("companyNameText"), limit=80),
            "dateRange": _norm_text(exp.get("dateRange") or exp.get("date") or exp.get("timePeriod"), limit=60),
            "location": _norm_text(exp.get("location"), limit=80),
            "description": _norm_text(exp.get("description") or exp.get("summary") or exp.get("details"), limit=260),
        }

    def _compact_education(ed: Any) -> Dict[str, Any]:
        if not isinstance(ed, dict):
            return {}
        return {
            "school": _norm_text(ed.get("school") or ed.get("schoolName"), limit=100),
            "degree": _norm_text(ed.get("degree") or ed.get("degreeName"), limit=80),
            "field": _norm_text(ed.get("fieldOfStudy") or ed.get("field"), limit=80),
            "dateRange": _norm_text(ed.get("dateRange") or ed.get("date") or ed.get("timePeriod"), limit=60),
            "description": _norm_text(ed.get("description") or ed.get("activities"), limit=200),
        }

    def _compact_skill(x: Any) -> str:
        if x is None:
            return ""
        if isinstance(x, str):
            return _norm_text(x, limit=40)
        if isinstance(x, dict):
            for k in ("name", "title", "skill"):
                if x.get(k):
                    return _norm_text(x.get(k), limit=40)
        return _norm_text(x, limit=40)

    def _compact_language(x: Any) -> str:
        if x is None:
            return ""
        if isinstance(x, str):
            return _norm_text(x, limit=40)
        if isinstance(x, dict):
            for k in ("name", "title", "language"):
                if x.get(k):
                    return _norm_text(x.get(k), limit=40)
        return _norm_text(x, limit=40)

    profile = raw_profile if isinstance(raw_profile, dict) else {}

    return {
        "fullName": profile.get("fullName") or profile.get("name"),
        "headline": profile.get("headline") or profile.get("occupation") or profile.get("jobTitle"),
        "location": profile.get("addressWithCountry") or profile.get("location"),
        "companyName": profile.get("companyName"),
        "companyIndustry": profile.get("companyIndustry"),
        "connections": profile.get("connections"),
        "followers": profile.get("followers"),
        "about": _norm_text(profile.get("about"), limit=420),
        "experiences": [_compact_experience(e) for e in _take_list(profile.get("experiences"), limit=8)],
        "educations": [_compact_education(e) for e in _take_list(profile.get("educations"), limit=4)],
        "skills": [s for s in (_compact_skill(x) for x in _take_list(profile.get("skills"), limit=30)) if s],
        "languages": [s for s in (_compact_language(x) for x in _take_list(profile.get("languages"), limit=12)) if s],
    }


def run_linkedin_enrich_bundle(*, raw_report: Dict[str, Any], progress: Optional[ProgressFn] = None) -> Dict[str, Any]:
    """
    Upstream-aligned LinkedIn enrich bundle.

    The upstream `LinkedInAnalyzer` runs multiple independent AI calls and returns UI-ready
    blocks (with default fallbacks). This wrapper preserves the unified internal artifact
    shape expected by `/api/analyze` cards.
    """

    # Reuse the upstream analyzer orchestration (multi-call) to keep prompts/fields/calcs aligned.
    full_report = run_linkedin_ai_enrich(raw_report=raw_report, progress=progress)
    profile = full_report.get("profile_data") if isinstance(full_report, dict) else None
    if not isinstance(profile, dict):
        profile = {}

    skills = profile.get("skills") if isinstance(profile.get("skills"), dict) else {}
    career = profile.get("career") if isinstance(profile.get("career"), dict) else {}
    money = profile.get("money_analysis") if isinstance(profile.get("money_analysis"), dict) else {}
    colleagues_view = profile.get("colleagues_view") if isinstance(profile.get("colleagues_view"), dict) else {}
    life_well_being = profile.get("life_well_being") if isinstance(profile.get("life_well_being"), dict) else {}
    role_model = profile.get("role_model") if isinstance(profile.get("role_model"), dict) else {}

    about_s = str(profile.get("about") or "").strip()
    tags = profile.get("personal_tags") if isinstance(profile.get("personal_tags"), list) else []

    work_summary = str(profile.get("work_experience_summary") or "").strip()
    education_summary = str(profile.get("education_summary") or "").strip()
    roast_s = str(profile.get("roast") or "").strip() if isinstance(profile.get("roast"), str) else ""

    return ensure_meta({
        "skills": skills,
        "career": career,
        "work_experience_summary": work_summary,
        "education_summary": education_summary,
        "money": money,
        "money_analysis": money,
        "colleagues_view": colleagues_view,
        "life_well_being": life_well_being,
        "summary": {"about": about_s, "personal_tags": tags},
        "role_model": role_model,
        "roast": roast_s,
    }, source="linkedin_enrich", preserve_empty=True)

