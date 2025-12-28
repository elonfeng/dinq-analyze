"""
LinkedIn Language Service

This module handles the generation and management of language analysis for LinkedIn profiles.
It provides functions to extract and analyze user language skills from LinkedIn profiles.
"""

import logging
import traceback
from typing import Dict, Any, Optional, Callable, List
import json
from server.llm.gateway import openrouter_chat
from server.config.llm_models import get_model

# Get logger
logger = logging.getLogger('server.linkedin_analyzer.language_service')

def get_linkedin_languages(profile_data: Dict[str, Any], person_name: str, callback: Optional[Callable] = None) -> List[str]:
    """
    Get languages for LinkedIn user.
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        callback: Optional status callback function
        
    Returns:
        List of languages
    """
    try:
        # Try to generate language analysis
        languages = generate_languages_with_ai(profile_data, person_name)

        # If successfully generated languages, return it
        if languages:
            return languages
        else:
            # When no languages generated, use default languages
            default_languages = create_default_languages(profile_data, person_name)
            logger.info(f"Created default languages for LinkedIn user: {person_name}")
            return default_languages
            
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Failed to get LinkedIn languages: {e}")
        logger.error(f"Languages error details: {error_trace}")

        # Even if error occurs, create default languages
        try:
            default_languages = create_default_languages(profile_data, person_name)
            logger.info(f"Created default languages for LinkedIn user after error: {person_name}")
            return default_languages
        except Exception as inner_e:
            logger.error(f"Failed to create default languages after error: {inner_e}")
            return []

def generate_languages_with_ai(profile_data: Dict[str, Any], person_name: str) -> Optional[List[str]]:
    """
    Generate LinkedIn language analysis using AI
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        List of languages or None
    """
    try:

        # Build analysis prompt safely without complex JSON in f-string
        name = person_name or "Unknown"
        headline = profile_data.get('headline', '')
        location = profile_data.get('location', '') or profile_data.get('addressWithCountry', '')
        about = profile_data.get('about', '')

        # Simplify experience and education info to avoid JSON formatting issues
        experiences = profile_data.get('experiences', [])
        exp_summary = ""
        if experiences:
            for i, exp in enumerate(experiences[:3]):  # Only first 3
                title = exp.get('title', '')
                company = exp.get('subtitle', '').split('·')[0].strip() if exp.get('subtitle') else ''
                exp_summary += f"- {title} at {company}\n"

        educations = profile_data.get('educations', [])
        edu_summary = ""
        if educations:
            for i, edu in enumerate(educations[:2]):  # Only first 2
                degree = edu.get('subtitle', '')
                school = edu.get('title', '')
                edu_summary += f"- {degree} from {school}\n"

        analysis_prompt = f"""Based on the following LinkedIn profile information, analyze the user's language skills.

Personal Information:
- Name: {name}
- Position: {headline}
- Location: {location}
- About: {about}

Work Experience:
{exp_summary}

Education:
{edu_summary}

Please identify and return the user's language skills based on their profile information. Consider:
- Location and geographic indicators
- Company locations and international experience
- Education background and institutions
- Name patterns and cultural indicators
- Content language in about section and experiences

Return a JSON object with a "languages" array. Example: {{"languages": ["English", "Chinese"]}}
Always include at least one language. If unclear, default to English."""
        
        languages_data = openrouter_chat(
            task="linkedin_languages",
            messages=[{"role": "user", "content": analysis_prompt}],
            model=get_model("fast", task="linkedin_languages"),
            temperature=0.3,
            max_tokens=600,
            expect_json=True,
        )
        if isinstance(languages_data, list):
            languages_list = languages_data
        elif isinstance(languages_data, dict) and 'languages' in languages_data:
            languages_list = languages_data['languages']
        else:
            languages_list = ['English']
        if not languages_list:
            languages_list = ['English']
        logger.info(f"Successfully generated languages for {person_name}: {languages_list}")
        return languages_list
            
    except Exception as e:
        logger.error(f"Error generating languages with AI: {e}")
        return None

def create_default_languages(profile_data: Dict[str, Any], person_name: str) -> List[str]:
    """
    Create default languages based on profile data analysis

    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name

    Returns:
        List of default languages
    """
    try:
        languages = set()

        # Always include English as it's the most common business language
        languages.add('English')

        # Analyze location for language hints
        location = profile_data.get('location', '') or profile_data.get('addressWithCountry', '')
        if location:
            location_lower = location.lower()

            # Chinese regions
            if any(region in location_lower for region in ['china', 'beijing', 'shanghai', 'guangzhou', 'shenzhen', 'hong kong', 'taiwan', 'singapore']):
                languages.add('Chinese')

            # Spanish regions
            elif any(region in location_lower for region in ['spain', 'mexico', 'argentina', 'colombia', 'chile', 'peru']):
                languages.add('Spanish')

            # French regions
            elif any(region in location_lower for region in ['france', 'canada', 'quebec', 'belgium']):
                languages.add('French')

            # German regions
            elif any(region in location_lower for region in ['germany', 'austria', 'switzerland']):
                languages.add('German')

            # Japanese
            elif 'japan' in location_lower:
                languages.add('Japanese')

            # Korean
            elif 'korea' in location_lower:
                languages.add('Korean')

            # Portuguese
            elif any(region in location_lower for region in ['brazil', 'portugal']):
                languages.add('Portuguese')

        # Analyze name patterns for additional language hints
        if person_name:
            name_lower = person_name.lower()

            # Chinese name patterns (common surnames)
            if any(surname in name_lower for surname in ['wang', 'li', 'zhang', 'liu', 'chen', 'yang', 'huang', 'zhao', 'wu', 'zhou']):
                languages.add('Chinese')

            # Japanese name patterns
            elif any(pattern in name_lower for pattern in ['takeshi', 'hiroshi', 'yuki', 'akira', 'kenji', 'satoshi']):
                languages.add('Japanese')

            # Korean name patterns
            elif any(pattern in name_lower for pattern in ['kim', 'park', 'lee', 'choi', 'jung']):
                languages.add('Korean')

        # Analyze company information
        company_name = profile_data.get('companyName', '')
        if company_name:
            company_lower = company_name.lower()

            # Chinese companies
            if any(company in company_lower for company in ['tencent', 'alibaba', 'baidu', 'bytedance', 'huawei', 'xiaomi']):
                languages.add('Chinese')

            # Japanese companies
            elif any(company in company_lower for company in ['sony', 'toyota', 'nintendo', 'softbank', 'rakuten']):
                languages.add('Japanese')

        # Analyze education for language hints
        educations = profile_data.get('educations', [])
        for edu in educations:
            school_name = edu.get('title', '').lower()

            # Chinese universities
            if any(uni in school_name for uni in ['tsinghua', 'peking', 'fudan', 'shanghai jiao tong', 'zhejiang']):
                languages.add('Chinese')

            # European universities
            elif any(uni in school_name for uni in ['sorbonne', 'eth zurich', 'tu munich']):
                if 'sorbonne' in school_name:
                    languages.add('French')
                elif any(german in school_name for german in ['eth zurich', 'tu munich']):
                    languages.add('German')

        # Convert to list and ensure we have at least English
        result = list(languages) if languages else ['English']

        logger.info(f"Generated default languages for {person_name}: {result}")
        return result

    except Exception as e:
        logger.error(f"Error creating default languages: {e}")
        return ['English']
