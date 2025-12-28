import logging
from server.llm.gateway import openrouter_chat
from server.config.llm_models import get_model


logger = logging.getLogger('server.services.scholar.paper_summary')

def summarize_paper_of_year(paper_info):
    """Generate a concise summary for the latest year's spotlight paper."""
    if not paper_info:
        return ''

    title = paper_info.get('title') or ''
    if not title:
        return ''

    year = paper_info.get('year', '')
    venue = paper_info.get('venue', '')
    citations = paper_info.get('citations', 0)

    content_lines = [
        f"Title: {title}".strip(),
        f"Year: {year}".strip() if year else '',
        f"Venue: {venue}".strip() if venue else '',
        f"Citations: {citations}".strip() if citations else ''
    ]
    context = '\n'.join(line for line in content_lines if line)

    messages = [
        {
            "role": "system",
            "content": (
                "You craft concise, energetic academic highlights. "
                "Summaries must stay under 40 words, avoid bullet points, and focus on why the paper stood out that year."
            )
        },
        {
            "role": "user",
            "content": (
                "Summarize the following paper in one short paragraph. "
                "Highlight its key contribution or impact and keep the tone confident:\n\n"
                f"{context}"
            )
        }
    ]

    try:
        summary = openrouter_chat(
            task="paper_summary",
            messages=messages,
            model=get_model("fast", task="paper_summary"),
            temperature=0.6,
            max_tokens=180,
        )
        return (summary or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to summarize paper of year: %s", exc)
        return ''
