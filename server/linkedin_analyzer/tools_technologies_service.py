"""
Tools & Technologies Service for LinkedIn Analysis

This module provides functions to extract and analyze user's tools and technologies using AI.
"""

import logging
import json
from server.llm.gateway import openrouter_chat
from server.config.llm_models import get_model
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def get_linkedin_tools_technologies(profile_data: Dict[str, Any], person_name: str) -> List[str]:
    """
    Extract and analyze user's tools and technologies from LinkedIn profile
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        List of tools and technologies
    """
    try:
        # Generate tools and technologies with AI
        tools_technologies = generate_tools_technologies_with_ai(profile_data, person_name)
        return tools_technologies
    except Exception as e:
        logger.error(f"Error getting tools and technologies for {person_name}: {e}")
        return create_default_tools_technologies()

def generate_tools_technologies_with_ai(profile_data: Dict[str, Any], person_name: str) -> List[str]:
    """
    Generate tools and technologies analysis using AI
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        List of tools and technologies
    """
    try:
        # Prepare profile summary for AI analysis
        profile_summary = create_profile_summary(profile_data, person_name)
        
        
        prompt = f"""
        Based on the LinkedIn profile data for {person_name}, analyze their tools and technologies expertise.
        
        Profile Summary:
        {profile_summary}
        
        Please identify and return the top tools and technologies in JSON array format. Focus on:
        - Software applications
        - Programming languages
        - Development tools
        - Platforms and frameworks
        - Technical skills
        
        Return only a JSON array of strings, for example: ["Python", "JavaScript", "React", "AWS", "Docker"]
        """
        
        result = openrouter_chat(
            task="linkedin_tools",
            messages=[{"role": "user", "content": prompt}],
            model=get_model("fast", task="linkedin_tools"),
            temperature=0.7,
            max_tokens=500,
            expect_json=True,
        )
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and 'tools' in result:
            return result['tools']
        logger.warning(f"Unexpected tools response: {result}")
        return create_default_tools_technologies()
            
    except Exception as e:
        logger.error(f"Error generating tools and technologies with AI: {e}")
        return create_default_tools_technologies()

def create_profile_summary(profile_data: Dict[str, Any], person_name: str) -> str:
    """
    Create a summary of the LinkedIn profile for AI analysis
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        Profile summary string
    """
    try:
        summary_parts = []
        
        # Basic info
        summary_parts.append(f"Name: {person_name}")
        
        # Headline/Job title
        headline = profile_data.get('headline') or profile_data.get('jobTitle') or ""
        if headline:
            summary_parts.append(f"Headline: {headline}")
        
        # Location
        location = profile_data.get('location') or profile_data.get('addressWithCountry') or ""
        if location:
            summary_parts.append(f"Location: {location}")
        
        # About
        about = profile_data.get('about') or ""
        if about:
            summary_parts.append(f"About: {about}")
        
        # Work experience
        experiences = profile_data.get('experiences', [])
        if experiences:
            summary_parts.append("Work Experience:")
            for exp in experiences[:3]:  # Limit to first 3 experiences
                title = exp.get('title', '')
                company = exp.get('subtitle', '')
                duration = exp.get('caption', '')
                summary_parts.append(f"  - {title} at {company} ({duration})")
        
        # Education
        educations = profile_data.get('educations', [])
        if educations:
            summary_parts.append("Education:")
            for edu in educations[:2]:  # Limit to first 2 educations
                school = edu.get('title', '')
                degree = edu.get('subtitle', '')
                summary_parts.append(f"  - {degree} from {school}")
        
        # Skills
        skills = profile_data.get('skills', [])
        if skills:
            # Handle skills data structure - skills can be list of dicts or list of strings
            skill_names = []
            for skill in skills[:10]:  # Limit to first 10 skills
                if isinstance(skill, dict):
                    skill_name = skill.get('title', '')
                elif isinstance(skill, str):
                    skill_name = skill
                else:
                    continue
                if skill_name:
                    skill_names.append(skill_name)
            
            if skill_names:
                summary_parts.append(f"Skills: {', '.join(skill_names)}")
        
        return "\n".join(summary_parts)
        
    except Exception as e:
        logger.error(f"Error creating profile summary: {e}")
        return f"Name: {person_name}"

def create_default_tools_technologies() -> List[str]:
    """
    Create default tools and technologies
    
    Returns:
        List of default tools and technologies
    """
    return [
        "Microsoft Excel",
        "Microsoft Word",
        "Microsoft PowerPoint",
        "Google Workspace",
        "Slack"
    ] 
