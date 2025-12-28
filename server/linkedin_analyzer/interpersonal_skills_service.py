"""
LinkedIn Interpersonal Skills Service

This module handles the generation and management of interpersonal skills analysis for LinkedIn profiles.
It provides functions to extract and analyze user interpersonal skills from LinkedIn profiles.
"""

import logging
import traceback
from typing import Dict, Any, Optional, Callable, List
import json
from server.llm.gateway import openrouter_chat
from server.config.llm_models import get_model

# Get logger
logger = logging.getLogger('server.linkedin_analyzer.interpersonal_skills_service')

def get_linkedin_interpersonal_skills(profile_data: Dict[str, Any], person_name: str, callback: Optional[Callable] = None) -> List[str]:
    """
    Get interpersonal skills for LinkedIn user.
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        callback: Optional status callback function
        
    Returns:
        List of interpersonal skills
    """
    try:
        # Try to generate interpersonal skills analysis
        interpersonal_skills = generate_interpersonal_skills_with_ai(profile_data, person_name)

        # If successfully generated interpersonal skills, return it
        if interpersonal_skills:
            return interpersonal_skills
        else:
            # When no interpersonal skills generated, use default skills
            default_skills = create_default_interpersonal_skills(profile_data, person_name)
            logger.info(f"Created default interpersonal skills for LinkedIn user: {person_name}")
            return default_skills
            
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Failed to get LinkedIn interpersonal skills: {e}")
        logger.error(f"Interpersonal skills error details: {error_trace}")

        # Even if error occurs, create default interpersonal skills
        try:
            default_skills = create_default_interpersonal_skills(profile_data, person_name)
            logger.info(f"Created default interpersonal skills for LinkedIn user after error: {person_name}")
            return default_skills
        except Exception as inner_e:
            logger.error(f"Failed to create default interpersonal skills after error: {inner_e}")
            return []

def generate_interpersonal_skills_with_ai(profile_data: Dict[str, Any], person_name: str) -> Optional[List[str]]:
    """
    Generate LinkedIn interpersonal skills analysis using AI
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        List of interpersonal skills or None
    """
    try:

        # Build analysis prompt
        analysis_prompt = f"""
        Based on the following LinkedIn profile information, analyze the user's interpersonal skills.

        Personal Information:
        - Name: {person_name}
        - Position: {profile_data.get('headline', '')}
        - Location: {profile_data.get('location', '')}
        - About: {profile_data.get('about', '')}

        Work Experience: {json.dumps(profile_data.get('experiences', []), ensure_ascii=False)}
        Education: {json.dumps(profile_data.get('educations', []), ensure_ascii=False)}

        Please identify and return the top interpersonal skills in JSON array format. Focus on:
        - Communication skills
        - Leadership abilities
        - Teamwork and collaboration
        - Emotional intelligence
        - Conflict resolution

        Return only a JSON array of strings, for example: ["Team Leadership", "Communication", "Conflict Resolution"]
        """
        
        skills_data = openrouter_chat(
            task="linkedin_interpersonal_skills",
            messages=[{"role": "user", "content": analysis_prompt}],
            model=get_model("fast", task="linkedin_interpersonal_skills"),
            temperature=0.3,
            max_tokens=600,
            expect_json=True,
        )
        if isinstance(skills_data, list):
            skills_list = skills_data
        elif isinstance(skills_data, dict) and 'interpersonal_skills' in skills_data:
            skills_list = skills_data['interpersonal_skills']
        else:
            skills_list = []
        logger.info(f"Successfully generated interpersonal skills for {person_name}")
        return skills_list
            
    except Exception as e:
        logger.error(f"Error generating interpersonal skills with AI: {e}")
        return None

def create_default_interpersonal_skills(profile_data: Dict[str, Any], person_name: str) -> List[str]:
    """
    Create default interpersonal skills based on profile data
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        List of default interpersonal skills
    """
    try:
        default_skills = []
        
        # Extract skills from headline
        headline = (profile_data.get('headline') or '').lower()
        if 'manager' in headline or 'lead' in headline or 'director' in headline:
            default_skills.extend(['Leadership', 'Team Management', 'Strategic Communication'])
        if 'coordinator' in headline or 'specialist' in headline:
            default_skills.extend(['Collaboration', 'Cross-functional Communication'])
        if 'consultant' in headline or 'advisor' in headline:
            default_skills.extend(['Client Communication', 'Stakeholder Management'])
        
        # Extract skills from about section
        about = (profile_data.get('about') or '').lower()
        if 'team' in about:
            default_skills.append('Teamwork')
        if 'lead' in about or 'manage' in about:
            default_skills.append('Leadership')
        if 'communicate' in about or 'presentation' in about:
            default_skills.append('Communication')
        if 'collaborate' in about or 'partnership' in about:
            default_skills.append('Collaboration')
        if 'mentor' in about or 'coach' in about:
            default_skills.append('Mentoring')
        if 'negotiate' in about or 'deal' in about:
            default_skills.append('Negotiation')
        
        # Add common interpersonal skills
        default_skills.extend(['Communication', 'Teamwork', 'Problem Solving', 'Active Listening'])
        
        # Remove duplicates and return
        return list(set(default_skills))
        
    except Exception as e:
        logger.error(f"Error creating default interpersonal skills: {e}")
        return ['Communication', 'Teamwork', 'Problem Solving', 'Active Listening'] 
