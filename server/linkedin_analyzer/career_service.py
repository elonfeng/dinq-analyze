"""
LinkedIn Career Service

This module handles the generation and management of career analysis for LinkedIn profiles.
It provides functions to analyze career development potential and advice.
"""

import logging
import traceback
from typing import Dict, Any, Optional, Callable
import json
from server.llm.gateway import openrouter_chat
from server.config.llm_models import get_model

# Get logger
logger = logging.getLogger('server.linkedin_analyzer.career_service')

def get_linkedin_career(profile_data: Dict[str, Any], person_name: str, callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Get career analysis for LinkedIn user.
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        callback: Optional status callback function
        
    Returns:
        Dictionary containing career analysis
    """
    try:
        # Try to generate career analysis
        career = generate_career_with_ai(profile_data, person_name)

        # If successfully generated career analysis, return it
        if career:
            return career
        else:
            # When no career analysis generated, use default analysis
            default_career = create_default_career(profile_data, person_name)
            logger.info(f"Created default career analysis for LinkedIn user: {person_name}")
            return default_career
            
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Failed to get LinkedIn career analysis: {e}")
        logger.error(f"Career analysis error details: {error_trace}")

        # Even if error occurs, create default career analysis
        try:
            default_career = create_default_career(profile_data, person_name)
            logger.info(f"Created default career analysis for LinkedIn user after error: {person_name}")
            return default_career
        except Exception as inner_e:
            logger.error(f"Failed to create default career analysis after error: {inner_e}")
            return {"future_development_potential": "", "development_advice": {"past_evaluation": "", "future_advice": ""}}

def generate_career_with_ai(profile_data: Dict[str, Any], person_name: str) -> Optional[Dict[str, Any]]:
    """
    Generate LinkedIn career analysis using AI
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        Dictionary containing career analysis or None
    """
    try:

        # Build analysis prompt based on the Career screenshot content
        analysis_prompt = f"""
        Based on the following LinkedIn profile information, provide a comprehensive career analysis.

        Personal Information:
        - Name: {person_name}
        - Position: {profile_data.get('headline', '')}
        - Location: {profile_data.get('location', '')}
        - About: {profile_data.get('about', '')}

        Work Experience: {json.dumps(profile_data.get('experiences', []), ensure_ascii=False)}
        Education: {json.dumps(profile_data.get('educations', []), ensure_ascii=False)}

        Please analyze and return a JSON object with the following structure:

        1. Future Development Potential: A concise assessment of career advancement potential
        2. Simplified Future Development Potential: Simplified Future Development Potential under 10 words
        3. Development Advice: An object containing:
           - Past Evaluation: Assessment of past career achievements and growth
           - Simplified Past Evaluation: Simplified Past Evaluation under 10 words
           - Future Advice: Specific recommendations for career development

        Return format:
        {{
            "future_development_potential": "With expertise in [field] and [skills], poised to advance as [potential role] in [industry] or [alternative path].",
            "simplified_future_development_potential": "Simplified Future Development Potential under 10 words",
            "development_advice": {{
                "past_evaluation": "Specialized in [past achievements], driving [key accomplishments] and demonstrating [key skills].",
                "simplified_past_evaluation": "Simplified Past Evaluation under 10 words",
                "future_advice": "Strengthen [specific skill]; expand into [development area]. Leverage [opportunity] to enhance [outcome]."
            }}
        }}

        Return only the JSON object, no additional text.
        """
        
        career_data = openrouter_chat(
            task="linkedin_career",
            messages=[{"role": "user", "content": analysis_prompt}],
            model=get_model("fast", task="linkedin_career"),
            temperature=0.3,
            max_tokens=800,
            expect_json=True,
        )
        if isinstance(career_data, dict):
            logger.info(f"Successfully generated career analysis for {person_name}")
            return career_data
        return None
            
    except Exception as e:
        logger.error(f"Error generating career analysis with AI: {e}")
        return None

def create_default_career(profile_data: Dict[str, Any], person_name: str) -> Dict[str, Any]:
    """
    Create default career analysis based on profile data
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        Dictionary containing default career analysis
    """
    try:
        # Extract career insights from headline
        headline = (profile_data.get('headline') or '').lower()
        if 'senior' in headline or 'lead' in headline or 'manager' in headline:
            potential = "High potential for senior leadership roles"
        elif 'director' in headline or 'head' in headline:
            potential = "Executive leadership potential"
        elif 'engineer' in headline or 'developer' in headline:
            potential = "Strong technical career progression"
        else:
            potential = "Good potential for career growth"
        
        # Extract insights from work experience
        industry = "professional"  # Default industry
        experiences = profile_data.get('experiences', [])
        for exp in experiences:
            # Check both 'company' and 'subtitle' fields for company name
            company = (exp.get('company') or exp.get('subtitle') or '').lower()
            if any(keyword in company for keyword in ['tech', 'software', 'ai', 'machine learning']):
                industry = "technology"
                break
            elif any(keyword in company for keyword in ['bank', 'finance', 'investment']):
                industry = "finance"
                break
            elif any(keyword in company for keyword in ['health', 'medical', 'pharma']):
                industry = "healthcare"
                break
            elif any(keyword in company for keyword in ['consulting', 'advisory']):
                industry = "consulting"
                break
        
        # Determine career level and potential
        if 'manager' in headline or 'lead' in headline or 'director' in headline:
            future_potential = f"With expertise in leadership and team management, poised to advance as Senior Manager or Director in {industry} firms."
            past_evaluation = "Demonstrated strong leadership capabilities and team management skills."
            future_advice = "Strengthen strategic planning mindset; expand into organizational development or global management. Leverage industry trends to enhance leadership impact."
        elif 'developer' in headline or 'engineer' in headline:
            future_potential = f"With technical expertise and problem-solving skills, poised to advance as Senior Developer or Tech Lead in {industry} companies."
            past_evaluation = "Specialized in software development and technical problem-solving."
            future_advice = "Strengthen system design skills; expand into architecture or technical leadership. Leverage emerging technologies to enhance technical expertise."
        elif 'analyst' in headline:
            future_potential = f"With analytical thinking and data-driven approach, poised to advance as Senior Analyst or Data Scientist in {industry} organizations."
            past_evaluation = "Specialized in data analysis and business intelligence."
            future_advice = "Strengthen statistical modeling skills; expand into machine learning or business intelligence. Leverage data insights to enhance decision-making impact."
        else:
            future_potential = f"With professional experience and career progression, poised to advance in {industry} or related industries."
            past_evaluation = "Demonstrated consistent career growth and professional development."
            future_advice = "Strengthen specialized skills; expand into new areas of expertise. Leverage industry knowledge to enhance career opportunities."
        
        return {
            "future_development_potential": future_potential,
            "development_advice": {
                "past_evaluation": past_evaluation,
                "future_advice": future_advice
            }
        }
        
    except Exception as e:
        logger.error(f"Error creating default career analysis: {e}")
        return {
            "future_development_potential": "With professional experience and skills, poised to advance in current industry or related fields.",
            "development_advice": {
                "past_evaluation": "Demonstrated consistent career growth and professional development.",
                "future_advice": "Strengthen specialized skills; expand into new areas of expertise. Leverage industry knowledge to enhance career opportunities."
            }
        }

def get_industry_from_profile(profile_data: Dict[str, Any]) -> str:
    """
    Extract industry information from profile data
    
    Args:
        profile_data: LinkedIn profile data
        
    Returns:
        Industry string
    """
    try:
        # Try to extract industry from experience
        experience = profile_data.get('experiences', [])
        if experience:
            # Look for common industry keywords in company names or descriptions
            for exp in experience:
                company = exp.get('company', '').lower()
                if any(keyword in company for keyword in ['tech', 'software', 'ai', 'machine learning']):
                    return "technology"
                elif any(keyword in company for keyword in ['bank', 'finance', 'investment']):
                    return "finance"
                elif any(keyword in company for keyword in ['health', 'medical', 'pharma']):
                    return "healthcare"
                elif any(keyword in company for keyword in ['consulting', 'advisory']):
                    return "consulting"
        
        # Default to technology if no specific industry found
        return "technology"
        
    except Exception as e:
        logger.error(f"Error extracting industry from profile: {e}")
        return "technology" 
