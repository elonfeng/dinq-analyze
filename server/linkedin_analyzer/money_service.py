"""
LinkedIn Money Service

This module handles the generation and management of salary and career level analysis for LinkedIn profiles.
It provides functions to determine user's career level, earnings, and market positioning.
"""

import logging
import traceback
from typing import Dict, Any, Optional, Callable
import json
from server.llm.gateway import openrouter_chat
from server.config.llm_models import get_model

# Get logger
logger = logging.getLogger('server.linkedin_analyzer.money_service')

def get_linkedin_money_analysis(profile_data: Dict[str, Any], person_name: str, callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Get salary and career level analysis for LinkedIn user.
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        callback: Optional status callback function
        
    Returns:
        Dictionary containing salary and career level information
    """
    try:
        # Get salary analysis
        money_analysis = generate_money_analysis_with_ai(profile_data, person_name)
        
        if money_analysis:
            return money_analysis
        else:
            # If analysis fails, create default analysis
            default_analysis = create_default_money_analysis(profile_data, person_name)
            logger.info(f"Created default money analysis for LinkedIn user: {person_name}")
            return default_analysis
            
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Failed to get LinkedIn money analysis: {e}")
        logger.error(f"Money analysis error details: {error_trace}")

        # Even if error occurs, create default analysis
        try:
            default_analysis = create_default_money_analysis(profile_data, person_name)
            logger.info(f"Created default money analysis for LinkedIn user after error: {person_name}")
            return default_analysis
        except Exception as inner_e:
            logger.error(f"Failed to create default money analysis after error: {inner_e}")
            return None

def generate_money_analysis_with_ai(profile_data: Dict[str, Any], person_name: str) -> Optional[Dict[str, Any]]:
    """
    Generate LinkedIn salary analysis using AI
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        Salary analysis information or None
    """
    try:

        # Build comprehensive analysis prompt based on scholar analysis approach
        analysis_prompt = f"""
        Based on the following LinkedIn profile information, analyze the professional's career level and compensation.

        Personal Information:
        - Name: {person_name}
        - Position: {profile_data.get('headline', '')}
        - Location: {profile_data.get('addressWithCountry', profile_data.get('location', ''))}
        - About: {profile_data.get('about', '')}
        - Current Company: {profile_data.get('companyName', '')}
        - Industry: {profile_data.get('companyIndustry', '')}

        Work Experience: {json.dumps(profile_data.get('experiences', []), ensure_ascii=False)}
        Education: {json.dumps(profile_data.get('educations', []), ensure_ascii=False)}
        Skills: {json.dumps(profile_data.get('skills', []), ensure_ascii=False)}

        CRITICAL INSTRUCTION: You must NEVER return "No data" for any field. Even with limited information, you must always generate reasonable data based on what's available.

        EVALUATION APPROACH: Be EXTREMELY AGGRESSIVE and COMPETITIVE in recognizing top-tier AI/ML/Tech talent value. The current AI talent war has driven compensation 3-5x traditional levels. ALWAYS err on the side of HIGHER compensation - these professionals are in extreme demand and command premium packages.

        Please analyze these aspects:
        1. Years of Experience (YoE) based on work history and career progression
        2. Equivalent level at Google (L5, L6, L7, etc.) and Alibaba (P level = Google L + 2)
           Apply these GENEROUS upgrade criteria:
           - Senior/Staff/Principal roles: minimum L6
           - Director/VP roles: minimum L7
           - C-level/Founder roles: minimum L8
           - AI/ML leadership: +1 level boost
           - 10+ years experience: minimum L6
           - 15+ years experience: minimum L7

        3. Estimated total annual compensation. Use this DYNAMIC CALCULATION FRAMEWORK:

          STEP 1 - DETERMINE BASE COMPENSATION BY ROLE LEVEL:
          - L3/P5 (Junior): $180K-250K base
          - L4/P6 (Mid-level): $280K-380K base
          - L5/P7 (Senior): $400K-550K base
          - L6/P8 (Staff/Manager): $600K-850K base
          - L7/P9 (Principal/Director): $900K-1.3M base
          - L8/P10 (Distinguished/VP): $1.4M-2.2M base
          - L9/P11+ (Fellow/C-level): $2.5M-4M+ base

          STEP 2 - APPLY MULTIPLIERS (compound them):
          Location: SF/NYC (+40%), Seattle/Austin (+25%), Other US (+10%), International (varies)
          Company: FAANG/Top Tech (+50%), Unicorn (+30%), Large Corp (+15%), Startup (equity dependent)
          Industry: AI/ML (+100%), Crypto/Web3 (+80%), Fintech (+60%), SaaS (+40%), Traditional (+0%)
          Experience: 10+ years (+30%), 15+ years (+60%), 20+ years (+100%)
          Hot Skills: LLM/GenAI (+50%), Distributed Systems (+30%), Security (+25%)

          STEP 3 - ROLE-SPECIFIC ADJUSTMENTS:
          IC roles: Use base calculation
          Team Lead: +25% to base
          Manager: +40% to base
          Director: +80% to base
          VP: +150% to base
          C-level: +300% to base

          STEP 4 - MARKET REALITY CHECK:
          - AI talent war has driven compensation 2-3x traditional levels
          - Top AI researchers command $2M-10M+ packages
          - Startup equity can add 50-200% to base compensation
          - International talent often gets US-competitive packages

          CALCULATION EXAMPLES (MINIMUM expectations):
          Senior AI Engineer (L6) at OpenAI in SF with 8 years experience:
          Base: $700K → Location (+40%): $980K → Company (+50%): $1.47M → Industry (+100%): $2.94M → Experience (+30%): $3.82M
          Final range: $3.5M-4.2M (this is MINIMUM - go higher for exceptional talent)

          CEO of AI startup in SF: Start at $4M base, apply multipliers → $8M-15M+ range
          VP at FAANG with AI focus: Start at $2M base, apply multipliers → $5M-8M range
          Staff Engineer at top AI company: Start at $1M base, apply multipliers → $3M-5M range

          CRITICAL: These are STARTING POINTS - exceptional professionals should get HIGHER ranges.
          AVOID OUTPUTTING IDENTICAL RANGES - Add 15-25% variation based on specific profile details.
          WHEN IN DOUBT, GO HIGHER - the AI talent market is extremely competitive.

        4. Detailed justification emphasizing competitive advantages and market value

        Return in JSON format:
        {{
            "years_of_experience": {{
                "years": [number],
                "start_year": [year],
                "calculation_basis": "[brief explanation]"
            }},
            "level_us": "L[X]",
            "level_cn": "P[X+2]",
            "estimated_salary": "salary range in USD without commas, e.g., '2000000-3000000'",
            "explanation": "[50-70 words emphasizing COMPETITIVE ADVANTAGES, market scarcity, and why this professional commands PREMIUM compensation in current market. Be generous and highlight exceptional value.]"
        }}

        FINAL REMINDER: Be AGGRESSIVE in valuation - reflect reality that exceptional tech professionals are highly sought-after. All responses MUST contain actual content.

        Please provide all text responses in English only.
        """
        
        money_data = openrouter_chat(
            task="linkedin_money",
            messages=[{"role": "user", "content": analysis_prompt}],
            model=get_model("reasoning_fast", task="linkedin_money"),
            temperature=0.3,
            max_tokens=600,
            expect_json=True,
        )
        if isinstance(money_data, dict):
            logger.info(f"Successfully generated money analysis for {person_name}")
            return money_data
        logger.error("Failed to parse money analysis JSON")
        return None
            
    except Exception as e:
        logger.error(f"Error generating money analysis with AI: {e}")
        return None

def create_default_money_analysis(profile_data: Dict[str, Any], person_name: str) -> Dict[str, Any]:
    """
    Create default salary analysis
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        Default salary analysis dictionary
    """
    try:
        # Extract insights from profile for better default analysis
        headline = (profile_data.get('headline') or '').lower()
        experiences = profile_data.get('experiences', [])
        current_company = profile_data.get('companyName', 'their company')

        # Calculate experience years
        experience_years = len(experiences) * 2  # Rough estimate

        # Dynamic salary calculation - use target ranges and add variation
        import random

        # Define target salary ranges (min, max) for each role level
        if any(word in headline for word in ['ceo', 'founder', 'chief', 'president']):
            level_us = "L8"
            level_cn = "P10"
            target_min, target_max = 3000000, 5000000  # 3-5M range
            justification = f"C-level executive with strategic leadership responsibilities commanding premium compensation in competitive market."
        elif any(word in headline for word in ['vp', 'vice president', 'director']):
            level_us = "L7"
            level_cn = "P9"
            target_min, target_max = 2000000, 3000000  # 2-3M range
            justification = f"Senior leadership role with significant organizational impact and market-competitive compensation."
        elif any(word in headline for word in ['senior', 'staff', 'principal', 'lead']):
            level_us = "L6"
            level_cn = "P8"
            target_min, target_max = 1500000, 2200000  # 1.5-2.2M range
            justification = f"Senior technical role with specialized expertise commanding premium in current talent market."
        elif any(word in headline for word in ['manager', 'head']):
            level_us = "L6"
            level_cn = "P8"
            target_min, target_max = 1200000, 1800000  # 1.2-1.8M range
            justification = f"Management position with team leadership responsibilities in competitive professional market."
        elif any(word in headline for word in ['engineer', 'developer', 'scientist', 'analyst']):
            level_us = "L5"
            level_cn = "P7"
            target_min, target_max = 1000000, 1500000  # 1.0-1.5M range
            justification = f"Technical professional with specialized skills in high-demand market segment."
        else:
            level_us = "L5"
            level_cn = "P7"
            target_min, target_max = 800000, 1200000  # 800K-1.2M range
            justification = f"Professional with valuable expertise in competitive market environment."

        # Apply modifiers to the target range
        # Experience modifier
        exp_modifier = 1.0 + (max(experience_years, 2) * 0.05)  # 5% per year of experience

        # Industry modifier
        industry = profile_data.get('companyIndustry', '').lower()
        if any(word in industry for word in ['ai', 'artificial intelligence', 'machine learning', 'data']):
            industry_modifier = 1.3  # 30% boost for AI
        elif any(word in industry for word in ['technology', 'software', 'tech']):
            industry_modifier = 1.2  # 20% boost for tech
        elif any(word in industry for word in ['finance', 'fintech', 'banking']):
            industry_modifier = 1.15  # 15% boost for finance
        elif any(word in industry for word in ['consulting', 'strategy']):
            industry_modifier = 1.1  # 10% boost for consulting
        else:
            industry_modifier = 1.0  # No modifier for other industries

        # Apply modifiers to target range
        modified_min = int(target_min * exp_modifier * industry_modifier)
        modified_max = int(target_max * exp_modifier * industry_modifier)

        # Add randomization within the modified range to avoid fixed amounts
        range_variation = random.uniform(0.85, 1.15)  # ±15% variation
        final_min = int(modified_min * range_variation)
        final_max = int(modified_max * range_variation)

        # Ensure min < max
        if final_min > final_max:
            final_min, final_max = final_max, final_min

        earnings = f"{final_min}-{final_max}"

        return {
            "years_of_experience": {
                "years": max(experience_years, 5),
                "start_year": 2024 - max(experience_years, 5),
                "calculation_basis": "Estimated based on work experience and career progression"
            },
            "level_us": level_us,
            "level_cn": level_cn,
            "earnings": earnings,
            "justification": justification
        }
        
    except Exception as e:
        logger.error(f"Error creating default money analysis: {e}")

        # Generate randomized fallback salary to avoid fixed amounts
        import random
        base_fallback = random.randint(800000, 1200000)  # Higher fallback range
        min_salary = int(base_fallback * 0.9)
        max_salary = int(base_fallback * 1.4)

        return {
            "years_of_experience": {
                "years": 5,
                "start_year": 2019,
                "calculation_basis": "Default estimate based on professional profile"
            },
            "level_us": "L5",
            "level_cn": "P7",
            "earnings": f"{min_salary}-{max_salary}",
            "justification": f"Professional with valuable expertise in competitive market environment."
        }
