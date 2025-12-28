"""
LinkedIn Life & Well-being Service

This module handles the generation and management of life and well-being recommendations for LinkedIn profiles.
It provides functions to analyze life suggestions and health recommendations.
"""

import logging
import traceback
from typing import Dict, Any, Optional, Callable
import json
from server.llm.gateway import openrouter_chat
from server.config.llm_models import get_model

# Get logger
logger = logging.getLogger('server.linkedin_analyzer.life_well_being_service')

def get_linkedin_life_well_being(profile_data: Dict[str, Any], person_name: str, callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Get life and well-being recommendations for LinkedIn user.
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        callback: Optional status callback function
        
    Returns:
        Dictionary containing life suggestions and health recommendations
    """
    try:
        # Try to generate life and well-being analysis
        life_well_being = generate_life_well_being_with_ai(profile_data, person_name)

        # If successfully generated life and well-being analysis, return it
        if life_well_being:
            return life_well_being
        else:
            # When no life and well-being analysis generated, use default analysis
            default_life_well_being = create_default_life_well_being(profile_data, person_name)
            logger.info(f"Created default life and well-being analysis for LinkedIn user: {person_name}")
            return default_life_well_being
            
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Failed to get LinkedIn life and well-being analysis: {e}")
        logger.error(f"Life and well-being analysis error details: {error_trace}")

        # Even if error occurs, create default life and well-being analysis
        try:
            default_life_well_being = create_default_life_well_being(profile_data, person_name)
            logger.info(f"Created default life and well-being analysis for LinkedIn user after error: {person_name}")
            return default_life_well_being
        except Exception as inner_e:
            logger.error(f"Failed to create default life and well-being analysis after error: {inner_e}")
            return {"life_suggestion": "", "health": ""}

def generate_life_well_being_with_ai(profile_data: Dict[str, Any], person_name: str) -> Optional[Dict[str, Any]]:
    """
    Generate LinkedIn life and well-being analysis using AI
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        Dictionary containing life suggestions and health recommendations or None
    """
    try:

        # Build comprehensive personalized analysis prompt
        analysis_prompt = f"""
        Based on the following LinkedIn profile information, provide HIGHLY PERSONALIZED life and well-being recommendations that are specifically tailored to this individual's career, industry, location, and life stage.

        Personal Information:
        - Name: {person_name}
        - Position: {profile_data.get('headline', '')}
        - Current Company: {profile_data.get('companyName', '')}
        - Industry: {profile_data.get('companyIndustry', '')}
        - Location: {profile_data.get('addressWithCountry', profile_data.get('location', ''))}
        - About: {profile_data.get('about', '')}
        - Company Size: {profile_data.get('companySize', '')}
        - Connections: {profile_data.get('connections', '')}

        Work Experience: {json.dumps(profile_data.get('experiences', []), ensure_ascii=False)}
        Education: {json.dumps(profile_data.get('educations', []), ensure_ascii=False)}
        Skills: {json.dumps(profile_data.get('skills', []), ensure_ascii=False)}

        CRITICAL REQUIREMENTS:
        1. PERSONALIZE based on their specific role, industry, and career stage
        2. Consider their location and cultural context
        3. Analyze their career trajectory and current challenges
        4. Address industry-specific stress factors and opportunities
        5. Provide actionable, relevant advice that feels custom-made for them
        6. Avoid generic advice - make it feel like you know their specific situation

        ANALYSIS APPROACH:
        - If in tech/AI: Address screen time, innovation pressure, rapid change adaptation
        - If in leadership: Focus on delegation, strategic thinking, team management stress
        - If in consulting: Address travel fatigue, client pressure, work-life boundaries
        - If in finance: Consider market stress, long hours, high-pressure environment
        - If in healthcare: Address emotional labor, shift work, patient care stress
        - If in education: Consider academic calendar, student interaction, research pressure
        - If in sales/marketing: Address rejection handling, target pressure, networking fatigue

        Please analyze and return a JSON object with the following structure:

        1. Life Suggestion: PERSONALIZED advice tailored to their specific role, industry, and career stage
        2. Health: Physical and mental health tips addressing their specific work environment and challenges

        EXAMPLES OF PERSONALIZED ADVICE:
        - For a startup founder: "Navigate the emotional rollercoaster of entrepreneurship by building a support network of fellow founders"
        - For a remote developer: "Combat isolation by joining local tech meetups and establishing co-working routines"
        - For a consultant: "Manage travel fatigue by creating portable wellness routines and maintaining home base connections"

        Return format:
        {{
            "life_suggestion": {{
                "advice": "[PERSONALIZED 20-30 word advice that directly addresses their specific role, industry challenges, and career stage. Reference their actual position/company/industry when relevant.]",
                "simplified_advice": "[PERSONALIZED under 10 word advice that directly addresses their specific role, industry challenges, and career stage. Reference their actual position/company/industry when relevant.]",
                "actions": [
                    {{"emoji": "[relevant emoji]", "phrase": "[MAXIMUM 3 WORDS - concise action phrase]"}},
                    {{"emoji": "[relevant emoji]", "phrase": "[MAXIMUM 3 WORDS - concise action phrase]"}},
                    {{"emoji": "[relevant emoji]", "phrase": "[MAXIMUM 3 WORDS - concise action phrase]"}}
                ]
            }},
            "health": {{
                "advice": "[PERSONALIZED 20-30 word health advice that addresses their specific work environment, stress factors, and physical demands. Consider their industry's typical health challenges.]",
                "simplified_advice": "[PERSONALIZED under 10 word health advice that addresses their specific work environment, stress factors, and physical demands. Consider their industry's typical health challenges.]",
                "actions": [
                    {{"emoji": "[relevant emoji]", "phrase": "[MAXIMUM 3 WORDS - concise health action]"}},
                    {{"emoji": "[relevant emoji]", "phrase": "[MAXIMUM 3 WORDS - concise health action]"}},
                    {{"emoji": "[relevant emoji]", "phrase": "[MAXIMUM 3 WORDS - concise health action]"}}
                ]
            }}
        }}

        CRITICAL REQUIREMENT: Each "phrase" field must contain MAXIMUM 3 WORDS. Examples:
        - "Set Boundaries" (2 words) ✓
        - "Daily Exercise" (2 words) ✓
        - "Screen Breaks" (2 words) ✓
        - "Practice Mindfulness" (2 words) ✓
        - "Network Actively" (2 words) ✓
        - "Take Breaks" (2 words) ✓

        FINAL REMINDER: Make this feel like personalized coaching, not generic advice. Reference their actual situation, role, and industry challenges. Keep all action phrases to 3 words maximum.

        Return only the JSON object, no additional text.
        """
        
        life_well_being_data = openrouter_chat(
            task="linkedin_life_well_being",
            messages=[{"role": "user", "content": analysis_prompt}],
            model=get_model("fast", task="linkedin_life_well_being"),
            temperature=0.3,
            max_tokens=800,
            expect_json=True,
        )
        if isinstance(life_well_being_data, dict):
            logger.info(f"Successfully generated life and well-being analysis for {person_name}")
            return life_well_being_data
        return None
            
    except Exception as e:
        logger.error(f"Error generating life and well-being analysis with AI: {e}")
        return None

def create_default_life_well_being(profile_data: Dict[str, Any], person_name: str) -> Dict[str, Any]:
    """
    Create default life and well-being analysis based on profile data

    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name

    Returns:
        Dictionary containing default life and well-being analysis
    """
    try:
        # Extract insights from headline and industry
        headline = (profile_data.get('headline') or '').lower()
        industry = (profile_data.get('companyIndustry') or '').lower()

        # Determine role-specific advice
        if any(word in headline for word in ['manager', 'lead', 'director', 'head']):
            life_advice = "As a leader, establish clear work-life boundaries to prevent burnout while maintaining team effectiveness. Delegate responsibilities and create structured time for strategic thinking and personal development."
            life_actions = [
                {"emoji": "⚖️", "phrase": "Work Balance"},
                {"emoji": "👥", "phrase": "Delegate Tasks"},
                {"emoji": "🎯", "phrase": "Strategic Time"}
            ]
            health_advice = "Leadership roles demand high energy and mental clarity. Prioritize consistent sleep schedules, regular exercise, and stress management techniques to maintain peak performance and decision-making capabilities."
            health_actions = [
                {"emoji": "😴", "phrase": "Sleep Schedule"},
                {"emoji": "🏃", "phrase": "Regular Exercise"},
                {"emoji": "🧘", "phrase": "Stress Management"}
            ]
        elif any(word in headline for word in ['developer', 'engineer', 'programmer']):
            life_advice = "Combat the isolation and intensity of technical work by building social connections, pursuing creative hobbies outside coding, and establishing clear boundaries between work and personal time."
            life_actions = [
                {"emoji": "👥", "phrase": "Social Connect"},
                {"emoji": "🎨", "phrase": "Creative Hobbies"},
                {"emoji": "📱", "phrase": "Tech Boundaries"}
            ]
            health_advice = "Address the physical demands of prolonged screen time and sedentary work. Implement regular eye breaks, ergonomic workspace setup, and movement throughout the day to prevent strain."
            health_actions = [
                {"emoji": "👁️", "phrase": "Eye Breaks"},
                {"emoji": "🪑", "phrase": "Ergonomic Setup"},
                {"emoji": "🚶", "phrase": "Movement Breaks"}
            ]
        elif any(word in headline for word in ['consultant', 'advisor', 'analyst']):
            life_advice = "Manage the demands of client work and travel by creating portable routines, maintaining home base connections, and establishing clear project boundaries to prevent overcommitment."
            life_actions = [
                {"emoji": "🧳", "phrase": "Portable Routines"},
                {"emoji": "🏠", "phrase": "Home Connections"},
                {"emoji": "📋", "phrase": "Project Boundaries"}
            ]
            health_advice = "Address travel fatigue and irregular schedules with consistent self-care practices, healthy eating habits on the road, and maintaining exercise routines regardless of location."
            health_actions = [
                {"emoji": "✈️", "phrase": "Travel Wellness"},
                {"emoji": "🥗", "phrase": "Healthy Eating"},
                {"emoji": "🏋️", "phrase": "Mobile Fitness"}
            ]
        elif any(word in headline for word in ['sales', 'marketing', 'business development']):
            life_advice = "Navigate the pressure of targets and client relationships by building resilience through networking, celebrating small wins, and maintaining perspective on long-term career growth."
            life_actions = [
                {"emoji": "🤝", "phrase": "Network Building"},
                {"emoji": "🎉", "phrase": "Celebrate Wins"},
                {"emoji": "📈", "phrase": "Long Perspective"}
            ]
            health_advice = "Manage the stress of performance metrics and rejection by developing emotional resilience, maintaining regular exercise for stress relief, and practicing mindfulness techniques."
            health_actions = [
                {"emoji": "💪", "phrase": "Build Resilience"},
                {"emoji": "🏃", "phrase": "Stress Relief"},
                {"emoji": "🧘", "phrase": "Mindfulness Practice"}
            ]
        else:
            # Generic professional advice
            life_advice = "Maintain professional growth while preserving personal well-being by setting clear boundaries, pursuing continuous learning, and nurturing relationships both inside and outside work."
            life_actions = [
                {"emoji": "📏", "phrase": "Set Boundaries"},
                {"emoji": "📚", "phrase": "Keep Learning"},
                {"emoji": "❤️", "phrase": "Nurture Relationships"}
            ]
            health_advice = "Establish sustainable daily routines that support both professional performance and personal health through regular exercise, adequate sleep, and stress management practices."
            health_actions = [
                {"emoji": "⏰", "phrase": "Daily Routine"},
                {"emoji": "🏃", "phrase": "Regular Exercise"},
                {"emoji": "😴", "phrase": "Quality Sleep"}
            ]

        return {
            "life_suggestion": {
                "advice": life_advice,
                "actions": life_actions
            },
            "health": {
                "advice": health_advice,
                "actions": health_actions
            }
        }

    except Exception as e:
        logger.error(f"Error creating default life and well-being analysis: {e}")
        return {
            "life_suggestion": {
                "advice": "Prioritize work-life balance by setting clear boundaries. Incorporate hobbies or social activities outside work projects to reduce burnout.",
                "actions": [
                    {"emoji": "📏", "phrase": "Set Boundaries"},
                    {"emoji": "🎨", "phrase": "Pursue Hobbies"},
                    {"emoji": "⛷️", "phrase": "Social Activities"}
                ]
            },
            "health": {
                "advice": "Schedule regular breaks during long work sessions. Engage in daily exercise, and ensure quality sleep for sustained energy.",
                "actions": [
                    {"emoji": "⏰", "phrase": "Regular Breaks"},
                    {"emoji": "🏃", "phrase": "Daily Exercise"},
                    {"emoji": "😴", "phrase": "Quality Sleep"}
                ]
            }
        }
