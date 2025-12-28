"""
LinkedIn Roast Service

This module handles the generation of humorous and constructive roasts for LinkedIn profiles.
It provides functions to create witty commentary about users' career paths and profiles.
"""

import logging
import traceback
from typing import Dict, Any, Optional, Callable
import json
from server.llm.gateway import openrouter_chat

# Get logger
logger = logging.getLogger('server.linkedin_analyzer.roast_service')

def get_linkedin_roast(profile_data: Dict[str, Any], person_name: str, callback: Optional[Callable] = None) -> str:
    """
    Get humorous roast for LinkedIn user.
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        callback: Optional status callback function
        
    Returns:
        Humorous roast text
    """
    try:
        # Try to generate roast
        roast = generate_roast_with_ai(profile_data, person_name)

        # If successfully generated roast, return it
        if roast:
            return roast
        else:
            # When no roast generated, use default roast
            default_roast = create_default_roast(profile_data, person_name)
            logger.info(f"Created default roast for LinkedIn user: {person_name}")
            return default_roast
            
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Failed to get LinkedIn roast: {e}")
        logger.error(f"Roast error details: {error_trace}")

        # Even if error occurs, create default roast
        try:
            default_roast = create_default_roast(profile_data, person_name)
            logger.info(f"Created default roast for LinkedIn user after error: {person_name}")
            return default_roast
        except Exception as inner_e:
            logger.error(f"Failed to create default roast after error: {inner_e}")
            return "This LinkedIn user's profile is quite interesting and worth deeper analysis."

def generate_roast_with_ai(profile_data: Dict[str, Any], person_name: str) -> Optional[str]:
    """
    Generate LinkedIn roast using AI

    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name

    Returns:
        Roast text or None
    """
    try:
        # NOTE: Restore origin/main style prompt (no aggressive input compression).
        # Truncate only to prevent token blowups for extremely long profiles.
        max_chars = 2000
        experiences_str = json.dumps(profile_data.get("experiences", []) or [], ensure_ascii=False)
        educations_str = json.dumps(profile_data.get("educations", []) or [], ensure_ascii=False)

        if len(experiences_str) > max_chars:
            logger.info("Truncating experiences from %s to %s chars", len(experiences_str), max_chars)
            experiences_str = experiences_str[:max_chars]
        if len(educations_str) > max_chars:
            logger.info("Truncating educations from %s to %s chars", len(educations_str), max_chars)
            educations_str = educations_str[:max_chars]

        analysis_prompt = f"""
        Based on the following LinkedIn profile information, create a humorous and light-hearted "roast" of this person.

        Personal Information:
        - Name: {person_name}
        - Position: {profile_data.get('headline', '')}
        - Location: {profile_data.get('location', '')}
        - About: {profile_data.get('about', '')}

        Work Experience: {experiences_str}
        Education: {educations_str}

        Please create a funny, light-hearted roast that pokes fun at their professional quirks, job title, or career choices in a good-natured way. Keep it professional and not offensive.

        Return format:
        {{
            "roast": "A humorous roast paragraph (2-3 sentences) that's funny but respectful"
        }}

        Return only the JSON object, no additional text.
        """
        
        obj = openrouter_chat(
            task="linkedin_roast",
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=0.7,
            max_tokens=200,
            expect_json=True,
            stream=False,
            cache=False,
            timeout_seconds=12.0,
        )

        roast_text: Optional[str] = None
        if isinstance(obj, dict):
            v = obj.get("roast")
            if isinstance(v, str) and v.strip():
                roast_text = v.strip()
        elif isinstance(obj, str) and obj.strip():
            raw = obj.strip()
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and isinstance(parsed.get("roast"), str) and parsed["roast"].strip():
                    roast_text = parsed["roast"].strip()
            except Exception:
                roast_text = raw

        if roast_text:
            logger.info("Successfully generated roast for %s", person_name)
            return roast_text

        logger.warning("AI returned empty roast content")
        return None
            
    except Exception as e:
        logger.error(f"Error generating roast with AI: {e}")
        return None

def create_default_roast(profile_data: Dict[str, Any], person_name: str) -> str:
    """
    Create default LinkedIn roast
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        Default roast text
    """
    # Generate default roast based on profile features
    headline = profile_data.get('headline', '')
    experience_count = len(profile_data.get('experiences', []))
    education_count = len(profile_data.get('educations', []))
    
    # Extract insights from about section
    about = (profile_data.get('about') or '').lower()
    if "passionate" in about:
        # Generate different roasts based on different features
        if "CEO" in headline or "Founder" in headline:
            return f"{person_name}'s LinkedIn profile shows they might be the next Steve Jobs, or at least they think so."
        elif experience_count > 10:
            return f"{person_name} has so much work experience that one wonders if they ever sleep, with every job clearly recorded on LinkedIn."
        elif experience_count < 2:
            return f"{person_name}'s LinkedIn profile is still fresh, like a recent graduate full of hope and possibilities."
        elif education_count > 3:
            return f"{person_name}'s educational background is impressive, they might be the only one who lists kindergarten in their education history."
        else:
            return f"{person_name}'s LinkedIn profile is very professional, but might be missing some personality. Consider adding interesting hobbies like 'Professional Coffee Connoisseur'." 
