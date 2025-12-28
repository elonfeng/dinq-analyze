"""
LinkedIn Colleagues View Service

This module handles the generation and management of colleagues view analysis for LinkedIn profiles.
It provides functions to simulate how colleagues might view the user based on their profile.
"""

import logging
import traceback
from typing import Dict, Any, Optional, Callable, List
import json
from server.llm.gateway import openrouter_chat
from server.config.llm_models import get_model

# Get logger
logger = logging.getLogger('server.linkedin_analyzer.colleagues_view_service')

def get_linkedin_colleagues_view(profile_data: Dict[str, Any], person_name: str, callback: Optional[Callable] = None) -> Dict[str, List[str]]:
    """
    Get colleagues view for LinkedIn user.
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        callback: Optional status callback function
        
    Returns:
        Dictionary containing highlights and areas for improvement
    """
    try:
        # Try to generate colleagues view analysis
        colleagues_view = generate_colleagues_view_with_ai(profile_data, person_name)

        # If successfully generated colleagues view, return it
        if colleagues_view:
            return colleagues_view
        else:
            # When no colleagues view generated, use default view
            default_view = create_default_colleagues_view(profile_data, person_name)
            logger.info(f"Created default colleagues view for LinkedIn user: {person_name}")
            return default_view
            
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Failed to get LinkedIn colleagues view: {e}")
        logger.error(f"Colleagues view error details: {error_trace}")

        # Even if error occurs, create default colleagues view
        try:
            default_view = create_default_colleagues_view(profile_data, person_name)
            logger.info(f"Created default colleagues view for LinkedIn user after error: {person_name}")
            return default_view
        except Exception as inner_e:
            logger.error(f"Failed to create default colleagues view after error: {inner_e}")
            return {"highlights": [], "areas_for_improvement": []}

def generate_colleagues_view_with_ai(profile_data: Dict[str, Any], person_name: str) -> Optional[Dict[str, List[str]]]:
    """
    Generate LinkedIn colleagues view analysis using AI
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        Dictionary containing highlights and areas for improvement or None
    """
    try:

        # Build analysis prompt
        analysis_prompt = f"""
        Based on the following LinkedIn profile information, simulate how colleagues might view this person.

        Personal Information:
        - Name: {person_name}
        - Position: {profile_data.get('headline', '')}
        - Location: {profile_data.get('location', '')}
        - About: {profile_data.get('about', '')}

        Work Experience: {json.dumps(profile_data.get('experiences', []), ensure_ascii=False)}
        Education: {json.dumps(profile_data.get('educations', []), ensure_ascii=False)}

        Please analyze from a colleague's perspective and return a JSON object with two arrays:

        1. Highlights: Positive aspects and strengths that colleagues would notice
        2. Areas for improvement: Constructive feedback and areas where colleagues might suggest growth

        Return format:
        {{
            "highlights": [
                "highlight1",
                "highlight2",
                "highlight3"
            ],
            "areas_for_improvement": [
                "area1",
                "area2",
                "area3"
            ]
        }}

        Return only the JSON object, no additional text.
        """
        
        colleagues_view_data = openrouter_chat(
            task="linkedin_colleagues_view",
            messages=[{"role": "user", "content": analysis_prompt}],
            model=get_model("fast", task="linkedin_colleagues_view"),
            temperature=0.3,
            max_tokens=800,
            expect_json=True,
        )
        if isinstance(colleagues_view_data, dict):
            logger.info(f"Successfully generated colleagues view for {person_name}")
            return colleagues_view_data
        return None
            
    except Exception as e:
        logger.error(f"Error generating colleagues view with AI: {e}")
        return None

def create_default_colleagues_view(profile_data: Dict[str, Any], person_name: str) -> Dict[str, List[str]]:
    """
    Create default colleagues view based on profile data
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        Dictionary containing default highlights and areas for improvement
    """
    try:
        highlights = []
        areas_for_improvement = []
        
        # Extract insights from headline
        headline = (profile_data.get('headline') or '').lower()
        if 'manager' in headline or 'lead' in headline or 'director' in headline:
            highlights.extend(['Strong leadership presence', 'Clear career progression'])
        if 'coordinator' in headline or 'specialist' in headline:
            highlights.extend(['Specialized expertise', 'Detail-oriented approach'])
        if 'consultant' in headline or 'advisor' in headline:
            highlights.extend(['Client-focused mindset', 'Strategic thinking'])
        
        # Extract insights from about section
        about = (profile_data.get('about') or '').lower()
        if 'team' in about:
            highlights.append("Team collaboration skills")
        if 'lead' in about or 'manage' in about:
            highlights.append("Leadership experience")
        if 'innovate' in about or 'creative' in about:
            highlights.append("Innovative thinking")
        if 'communicate' in about:
            highlights.append("Strong communication skills")
        
        # Add common areas for improvement
        areas_for_improvement.extend([
            "Could benefit from more cross-functional experience",
            "Consider expanding industry knowledge",
            "Opportunity to develop more strategic thinking"
        ])
        
        # Add common highlights if none found
        if not highlights:
            highlights.extend([
                "Professional experience",
                "Educational background",
                "Career progression"
            ])
        
        return {
            "highlights": highlights,
            "areas_for_improvement": areas_for_improvement
        }
        
    except Exception as e:
        logger.error(f"Error creating default colleagues view: {e}")
        return {
            "highlights": ["Professional experience", "Educational background"],
            "areas_for_improvement": ["Could benefit from more cross-functional experience"]
        } 
