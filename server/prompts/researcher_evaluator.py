"""
Researcher Evaluator

This module provides functions to generate critical evaluations of researcher profiles using LLM APIs via OpenRouter.
Supports multiple models including:
- OpenAI GPT-3.5 Turbo (fast)
- OpenAI GPT-4 (powerful)
- Anthropic Claude Haiku (balanced)
- Anthropic Claude Sonnet

All models are accessed through OpenRouter's unified API, simplifying the integration.
"""

import json
import logging
from server.llm.gateway import openrouter_chat
from server.config.llm_models import get_model

# Configure logging
logger = logging.getLogger(__name__)

# Default model selection (speed-first)
DEFAULT_MODEL = get_model("fast", task="researcher_evaluation")

# Available models through OpenRouter (aliases)
AVAILABLE_MODELS = {
    # Speed-first Gemini
    "fast": get_model("fast", task="researcher_evaluation"),
    "balanced": get_model("balanced", task="researcher_evaluation"),
    "flash-preview": get_model("flash_preview", task="researcher_evaluation"),

    # Grok
    "reasoning-fast": get_model("reasoning_fast", task="researcher_evaluation"),
    "code-fast": get_model("code_fast", task="researcher_evaluation"),

    # Backward-compatible aliases
    "powerful": get_model("balanced", task="researcher_evaluation"),

    # Legacy models (still supported if explicitly requested)
    "gpt-4": "openai/gpt-4o",
    "claude-haiku": "anthropic/claude-3-haiku-20240307",
    "claude-sonnet": "anthropic/claude-3-sonnet-20240229",
}

def format_researcher_data_for_critique(researcher_data):
    """
    Format researcher data for the LLM critique prompt.
    Returns a comprehensive summary of the researcher's profile with detailed metrics.
    """
    if not isinstance(researcher_data, dict):
        return "No researcher data available."

    researcher = researcher_data.get('researcher', {})
    pub_stats = researcher_data.get('publication_stats', {})
    coauthor_stats = researcher_data.get('coauthor_stats', {})
    most_cited_paper = pub_stats.get('most_cited_paper', {})
    most_frequent_collaborator = researcher_data.get('most_frequent_collaborator', {})
    rating = researcher_data.get('rating', {})

    output = []
    # Basic Information
    output.append(f"## Researcher Basic Information")
    output.append(f"Name: {researcher.get('name', 'Unknown')}")
    output.append(f"Affiliation: {researcher.get('affiliation', 'Unknown')}")
    output.append(f"H-index: {researcher.get('h_index', 'N/A')}")
    output.append(f"Total Citations: {researcher.get('total_citations', 'N/A')}")
    output.append(f"Research Fields: {', '.join(researcher.get('research_fields', []))}")

    # Publication Statistics
    output.append(f"\n## Publication Statistics")
    output.append(f"Total Papers: {pub_stats.get('total_papers', 'N/A')}")
    output.append(f"First-author Papers: {pub_stats.get('first_author_papers', 'N/A')} ({pub_stats.get('first_author_percentage', 'N/A')}%)")
    output.append(f"Corresponding Author Papers: {pub_stats.get('last_author_papers', 'N/A')} ({pub_stats.get('last_author_percentage', 'N/A')}%)")
    output.append(f"Top-tier Conference/Journal Papers: {pub_stats.get('top_tier_papers', 'N/A')} ({pub_stats.get('top_tier_percentage', 'N/A')}%)")

    # Citation Statistics
    citation_stats = pub_stats.get('citation_stats', {})
    if citation_stats:
        output.append(f"Average Citations per Paper: {citation_stats.get('avg_citations', 'N/A')}")
        output.append(f"Citation Median: {citation_stats.get('median_citations', 'N/A')}")

    # Citation Velocity
    if 'citation_velocity' in pub_stats:
        output.append(f"Citation Growth Rate: {pub_stats.get('citation_velocity', 'N/A')}")

    # Most Influential Paper
    if most_cited_paper:
        output.append(f"\n## Most Influential Paper")
        output.append(f"Title: {most_cited_paper.get('title', 'N/A')}")
        output.append(f"Publication Year: {most_cited_paper.get('year', 'N/A')}")
        output.append(f"Venue: {most_cited_paper.get('venue', 'N/A')}")
        output.append(f"Citations: {most_cited_paper.get('citations', 'N/A')}")

    # Conference Distribution
    if pub_stats.get('conference_distribution'):
        output.append(f"\n## Main Publication Venues")
        conf_items = list(pub_stats.get('conference_distribution', {}).items())
        for i, (conf, count) in enumerate(conf_items):
            if i >= 8:  # Show top 8
                break
            output.append(f"- {conf}: {count} papers")

    # Collaboration Information
    if coauthor_stats:
        output.append(f"\n## Collaboration Network")
        output.append(f"Total Collaborators: {coauthor_stats.get('total_coauthors', 'N/A')}")
        output.append(f"Collaboration Index: {coauthor_stats.get('collaboration_index', 'N/A')}")

    # Most Frequent Collaborator
    if most_frequent_collaborator and most_frequent_collaborator.get('full_name') != 'No frequent collaborator found':
        output.append(f"\n## Main Collaborator")
        output.append(f"Name: {most_frequent_collaborator.get('full_name', 'N/A')}")
        output.append(f"Affiliation: {most_frequent_collaborator.get('affiliation', 'N/A')}")
        output.append(f"Co-authored Papers: {most_frequent_collaborator.get('coauthored_papers', 'N/A')}")
        best_collab_paper = most_frequent_collaborator.get('best_paper', {})
        if best_collab_paper:
            output.append(f"Best Collaboration Paper: {best_collab_paper.get('title', 'N/A')}")
            output.append(f"Published in: {best_collab_paper.get('venue', 'N/A')}")
            output.append(f"Citations: {best_collab_paper.get('citations', 'N/A')}")

    # Research Style
    style = researcher_data.get('research_style', {})
    if style:
        output.append(f"\n## Research Style")
        output.append(f"Depth vs Breadth: {style.get('depth_vs_breadth', 'N/A')}")
        output.append(f"Theory vs Practice: {style.get('theory_vs_practice', 'N/A')}")
        output.append(f"Individual vs Team: {style.get('individual_vs_team', 'N/A')}")

    # Researcher Rating
    if rating:
        output.append(f"\n## Researcher Rating")
        output.append(f"Overall Rating: {rating.get('overall_rating', 'N/A')}/10")
        output.append(f"Impact: {rating.get('impact_rating', 'N/A')}/10")
        output.append(f"Productivity: {rating.get('productivity_rating', 'N/A')}/10")
        output.append(f"Innovation: {rating.get('innovation_rating', 'N/A')}/10")

    # Annual Publication Trends
    if pub_stats.get('year_distribution'):
        output.append(f"\n## Annual Publication Trends")
        output.append("Papers in the last five years:")
        year_dist = pub_stats.get('year_distribution', {})
        # Get data for the last 5 years
        recent_years = sorted(year_dist.keys(), reverse=True)[:5]
        for year in recent_years:
            output.append(f"- {year}: {year_dist.get(year, 0)} papers")

    return "\n".join(output)


def _compact_roast_context(source_data):
    """
    Build a compact context payload for the roast prompt.

    The previous markdown formatter can be very verbose and increases LLM latency.
    For the roast (<=35 words), we only need a few high-signal metrics.
    """

    if not isinstance(source_data, dict):
        return {}

    researcher = source_data.get("researcher") if isinstance(source_data.get("researcher"), dict) else {}
    pub_stats = source_data.get("publication_stats") if isinstance(source_data.get("publication_stats"), dict) else {}
    coauthor_stats = source_data.get("coauthor_stats") if isinstance(source_data.get("coauthor_stats"), dict) else {}
    most_cited = pub_stats.get("most_cited_paper") if isinstance(pub_stats.get("most_cited_paper"), dict) else {}

    fields = researcher.get("research_fields") or []
    if isinstance(fields, str):
        fields = [fields]
    if not isinstance(fields, list):
        fields = []

    conf_dist = pub_stats.get("conference_distribution") if isinstance(pub_stats.get("conference_distribution"), dict) else {}
    top_venues = []
    try:
        top_venues = sorted([(str(k), int(v)) for k, v in conf_dist.items()], key=lambda x: x[1], reverse=True)[:6]
    except Exception:
        top_venues = []

    return {
        "name": researcher.get("name"),
        "affiliation": researcher.get("affiliation"),
        "fields": [str(x) for x in fields[:8] if str(x).strip()],
        "metrics": {
            "h_index": researcher.get("h_index"),
            "total_citations": researcher.get("total_citations"),
            "citations_5y": researcher.get("citations_5y"),
            "total_papers": pub_stats.get("total_papers"),
            "top_tier_papers": pub_stats.get("top_tier_papers") or pub_stats.get("top_tier_publications"),
            "total_collaborators": coauthor_stats.get("total_coauthors"),
        },
        "most_cited_paper": {
            "title": most_cited.get("title"),
            "year": most_cited.get("year"),
            "citations": most_cited.get("citations"),
            "venue": most_cited.get("venue"),
        },
        "top_venues": top_venues,
    }


def generate_critical_evaluation(source_data, model=None):
    """
    Generate a critical evaluation of the researcher using LLM APIs.

    Args:
        source_data (dict): The researcher data to evaluate
        model (str, optional): The model to use. Options: "gpt-3.5-turbo", "claude-3-haiku-20240307"
                              If None, uses DEFAULT_MODEL

    Returns:
        str: A string containing the evaluation
    """
    try:
        # Keep the prompt compact for lower latency + better streaming UX.
        ctx = _compact_roast_context(source_data)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a witty roaster who delivers playful, humorous burns about researchers.\n"
                    "Write fluent English.\n\n"
                    "STRICT OUTPUT RULES:\n"
                    "- Maximum 35 words\n"
                    "- Single paragraph (no bullets)\n"
                    "- Cheeky, not cruel; no hate/offensive content\n"
                    "- Use the provided context only; do not invent facts\n"
                ),
            },
            {
                "role": "user",
                "content": "Roast this researcher based on the following JSON context:\n\n" + json.dumps(ctx, ensure_ascii=False),
            }
        ]

        openrouter_model = None
        if model is None:
            # Use gateway task routing (may include multi-provider hedge).
            openrouter_model = None
        elif model in AVAILABLE_MODELS:
            openrouter_model = AVAILABLE_MODELS[model]
        else:
            # Allow callers to pass a direct provider/model route spec.
            openrouter_model = model

        logger.info(f"Using model: {openrouter_model or '<task-routing>'} via LLM gateway")

        try:
            logger.info(f"Calling LLM gateway with model {openrouter_model or '<task-routing>'} for evaluation...")
            evaluation = openrouter_chat(
                task="researcher_evaluation",
                messages=messages,
                model=openrouter_model,
                temperature=0.7,
                max_tokens=120,
                cache=False,
                timeout_seconds=12.0,
            )
            if (not evaluation) and (openrouter_model is not None) and (openrouter_model != AVAILABLE_MODELS["fast"]):
                logger.warning(f"Falling back to {AVAILABLE_MODELS['fast']}")
                evaluation = openrouter_chat(
                    task="researcher_evaluation",
                    messages=messages,
                    model=AVAILABLE_MODELS["fast"],
                    temperature=0.7,
                    max_tokens=200,
                    cache=False,
                    timeout_seconds=12.0,
                )
            evaluation = (evaluation or "").strip()

            # Match origin/main behavior: only truncate if extremely long.
            words = evaluation.split()
            word_count = len(words)
            logger.info(f"Generated evaluation with {word_count} words")

            if word_count > 550:
                logger.warning(f"Evaluation too long ({word_count} words), truncating to ~500 words")
                truncated_words = words[:500]
                truncated_text = ' '.join(truncated_words)

                sentence_endings = ['.', '!', '?']
                last_ending = max([truncated_text.rfind(ending) for ending in sentence_endings])

                if last_ending > len(truncated_text) * 0.8:
                    evaluation = truncated_text[:last_ending+1] + '...'
                else:
                    evaluation = truncated_text + '...'

            logger.info(f"Final evaluation length: {len(evaluation.split())} words")

            if evaluation:
                logger.info("Successfully generated critical evaluation: %s...", evaluation[:50])
                return evaluation
            raise ValueError("empty_evaluation")
        except Exception as e:
            logger.error(f"Error in LLM API call: {e}")
            return "No roast available."
    except Exception as e:
        logger.error(f"Error in generate_critical_evaluation: {e}")
        return "No roast available."
 
