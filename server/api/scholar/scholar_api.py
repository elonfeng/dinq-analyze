"""
Scholar Synchronous Analysis API

This module provides a non-streaming API endpoint for scholar analysis.
It uses the same underlying logic as the streaming version but returns results synchronously.
"""

import logging
import time
import json
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify, g
from server.utils.auth import require_verified_user
from server.utils.usage_limiter import UsageLimiter
from server.utils.api_usage_tracker import track_api_call
from account.filter_scholar import filter_user_input
from server.services.scholar.scholar_service import run_scholar_analysis
from server.analyze.api import create_analysis_job, run_sync_job
from server.api.scholar.db_cache import get_scholar_from_cache, save_scholar_to_cache

# Create blueprint
scholar_sync_bp = Blueprint('scholar_sync', __name__)

# Configure logging
logger = logging.getLogger(__name__)

# Initialize usage limiter
usage_limiter = UsageLimiter()

def generate_ai_summary(extracted: Dict[str, Any],research_fields,description,top_tier) -> str:
    """
    Generate AI summary for researcher using GPT-4o-mini

    Args:
        researcher_data: Researcher information
        publication_stats: Publication statistics

    Returns:
        AI generated summary (30-40 characters)
    """
    try:
        from server.llm.gateway import openrouter_chat
        from server.config.llm_models import get_model

        # Create prompt for AI summary
        prompt = f"""
Summarize the researcher's fields, main achievements, and mention top conferences where papers were published (30-40 words).

description: {description},
info: {extracted},
research_fields: {research_fields},
top_tier: {top_tier}

Generate summary:

"""

        summary = openrouter_chat(
            task="scholar.card.summary",
            model=get_model("balanced", task="scholar.card.summary"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=100,
        )
        if summary:
            return str(summary).strip()
        logger.error("AI summary generation failed: empty response")
        return None

    except Exception as e:
        logger.error(f"Error generating AI summary: {e}")
        # Fallback summary
        return "Academic researcher with diverse expertise"

def extract_scholar_data(full_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract required fields from full scholar analysis result

    Args:
        full_result: Complete scholar analysis result

    Returns:
        Extracted data with required fields
    """
    try:
        researcher = full_result.get("researcher", {})
        publication_stats = full_result.get("publication_stats", {})
        research_fields = researcher.get("research_fields")
        description = researcher.get("description")
        top_tier = publication_stats.get("top_tier_publications")
        # Extract required fields
        extracted = {
            "name": researcher.get("name",""),
            "scholar_id": researcher.get("scholar_id",""),
            "total_papers": publication_stats.get("total_papers", 0),
            "top_tier_papers": publication_stats.get("top_tier_papers", 0),
            "total_citations": researcher.get("total_citations", 0),
            "first_author_citations": publication_stats.get("first_author_citations", 0),
            "h_index": researcher.get("h_index", 0)
        }

        summary = generate_ai_summary(extracted,research_fields,description,top_tier)
        extracted["summary"] = summary

        return extracted

    except Exception as e:
        logger.error(f"Error extracting scholar data: {e}")
        return None

@scholar_sync_bp.route('/api/scholar/card/analyze', methods=['POST'])
def analyze_scholar_sync():
    """
    Synchronous scholar analysis API
    
    Request body:
    {
        "query": "Scholar name, Google Scholar ID, or Google Scholar URL"
    }
    
    Returns:
    JSON response with complete analysis results
    """
    try:
        # Get request data
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'code': 400,
                'message': 'Missing query parameter. Please provide a query in the request body as {"query": "scholar_name_or_id"}',
                'data': None
            }), 400

        query = data['query'].strip()
        if not query:
            return jsonify({
                'code': 400,
                'message': 'Query cannot be empty',
                'data': None
            }), 400
        
        # Get user ID
        user_id = getattr(g, 'user_id', None)
        logger.info(f"Scholar sync analysis request - User: {user_id}, Query: {query}")

        
        use_legacy = str(data.get("legacy") or request.args.get("legacy") or "").lower() in ("1", "true", "yes", "on")
        if not use_legacy:
            job_id, _created = create_analysis_job(
                user_id=user_id or "anonymous",
                source="scholar",
                input_payload={"query": query},
                requested_cards=data.get("cards") or None,
                options={},
            )
            payload, status = run_sync_job(job_id, "scholar", data.get("cards") or None)
            return jsonify(payload), status

        # Process the user input to determine if it's a scholar ID, URL, or name
        processed_input, is_name = filter_user_input(query)
        scholar_id = None if is_name else processed_input

        # Check cache first (same logic as streaming version)
        cache_key = scholar_id if scholar_id else query
        logger.info(f"Checking cache for key: {cache_key}")

        cached_result = get_scholar_from_cache(cache_key)
        if cached_result:
            logger.info(f"Found cached result for {cache_key}")

            # Simple cache validation - check if data has essential fields
            if cached_result:

                logger.info(f"Cache validation successful for {cache_key}")

                # Extract required fields from cached result
                extracted_data = extract_scholar_data(cached_result)

                return jsonify({
                    'code': 200,
                    'message': 'Scholar analysis completed successfully',
                    'data': extracted_data
                })
            else:
                logger.info(f"Cache validation failed for {cache_key} - missing essential fields, proceeding with fresh analysis")
        else:
            logger.info(f"No cached result found for {cache_key}")

        # Execute synchronous analysis using the same logic as streaming version
        start_time = time.time()
        
        try:
            from server.config.api_keys import API_KEYS

            api_token = API_KEYS.get("CRAWLBASE_API_TOKEN")
            use_crawlbase = bool(api_token)
            
            if scholar_id:
                logger.info(f"Using scholar ID directly: {scholar_id}")
                result = run_scholar_analysis(
                    scholar_id=scholar_id,
                    use_crawlbase=use_crawlbase,
                    api_token=api_token,
                    use_cache=True,
                    cache_max_age_days=30,
                )
            else:
                logger.info(f"Using query as researcher name: {query}")
                result = run_scholar_analysis(
                    researcher_name=query,
                    use_crawlbase=use_crawlbase,
                    api_token=api_token,
                    use_cache=True,
                    cache_max_age_days=30,
                )
            
            analysis_time = time.time() - start_time
            
            if result is None:
                return jsonify({
                    'code': 404,
                    'message': f'No scholar found for query: {query}'
                }), 404
            logger.info(f"Scholar {query} sync analysis completed in {analysis_time:.2f}s")

            # Extract required fields from analysis result
            extracted_data = extract_scholar_data(result)

            # Return extracted analysis result
            return jsonify({
                'code': 200,
                'message': 'Scholar analysis completed successfully',
                'data': extracted_data
            })
            
        except Exception as analysis_error:
            logger.error(f"Error during scholar analysis: {analysis_error}")

            return jsonify({
                'code': 500,
                'message': f'Error during scholar analysis: {str(analysis_error)}'
            }), 500

    except Exception as e:
        logger.error(f"Scholar sync analysis API error: {e}")

        return jsonify({
            'code': 500,
            'message': f'Internal server error: {str(e)}'
        }), 500
