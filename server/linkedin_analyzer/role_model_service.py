"""
LinkedIn Role Model Service

This module handles the generation and management of role models for LinkedIn profiles.
It provides functions to find appropriate role models based on career path and experience.
"""

import logging
import traceback
from typing import Dict, Any, Optional, Callable, List
import json
from server.llm.gateway import openrouter_chat
from server.config.llm_models import get_model

# Get logger
logger = logging.getLogger('server.linkedin_analyzer.role_model_service')

def get_linkedin_role_model(profile_data: Dict[str, Any], person_name: str, callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Get role model for LinkedIn user based on LinkedIn celebrities CSV and AI analysis.

    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        callback: Optional status callback function

    Returns:
        Dictionary containing role model information with is_celebrity flag
    """
    try:
        # Step 1: Use AI to determine if this person is already a notable figure/celebrity
        is_celebrity_result = check_if_celebrity_with_ai(profile_data, person_name)
        is_celebrity = is_celebrity_result.get('is_celebrity', False)
        celebrity_reasoning = is_celebrity_result.get('reasoning', '')

        logger.info(f"AI celebrity check for {person_name}: {is_celebrity} - {celebrity_reasoning}")

        # Step 2: If they are a celebrity, use enhanced self role model
        if is_celebrity:
            self_role_model = create_enhanced_self_role_model(profile_data, person_name, celebrity_reasoning)
            self_role_model['is_celebrity'] = True
            self_role_model['celebrity_reasoning'] = celebrity_reasoning
            logger.info(f"User {person_name} is a celebrity - using enhanced self as role model")
            return self_role_model

        # Step 3: Try to find a matching role model from LinkedIn celebrities
        role_model = find_linkedin_celebrity_role_model(profile_data, person_name)

        # Step 4: Return found role model or use self as role model
        if role_model:
            role_model['is_celebrity'] = False
            role_model['celebrity_reasoning'] = celebrity_reasoning
            logger.info(f"Found LinkedIn celebrity role model: {role_model.get('name', 'Unknown')}")
            return role_model
        else:
            # Step 5: When no external role model found, use user's own information
            # This follows the same logic as scholar analysis - you are your own role model!
            self_role_model = create_self_role_model(profile_data, person_name)
            self_role_model['is_celebrity'] = False
            self_role_model['celebrity_reasoning'] = celebrity_reasoning
            logger.info(f"No external role model found, created self role model: {self_role_model.get('name', 'Unknown')}")
            return self_role_model

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Failed to get LinkedIn role model: {e}")
        logger.error(f"Role model error details: {error_trace}")

        # Even if error occurs, create self role model
        try:
            self_role_model = create_self_role_model(profile_data, person_name)
            logger.info(f"Created self role model for LinkedIn user after error: {self_role_model.get('name', 'Unknown')}")
            return self_role_model
        except Exception as inner_e:
            logger.error(f"Failed to create self role model after error: {inner_e}")
            return None

def check_if_celebrity_with_ai(profile_data: Dict[str, Any], person_name: str) -> Dict[str, Any]:
    """
    Use AI to determine if this person is already a notable figure/celebrity.

    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name

    Returns:
        Dictionary with is_celebrity (bool) and reasoning (str)
    """
    try:
        import json

        # Build comprehensive profile summary for AI analysis
        profile_summary = f"""
        Name: {person_name}
        Position: {profile_data.get('headline', '')}
        Current Company: {profile_data.get('companyName', '')}
        Industry: {profile_data.get('companyIndustry', '')}
        Location: {profile_data.get('addressWithCountry', profile_data.get('location', ''))}
        Connections: {profile_data.get('connections', 0)}
        Followers: {profile_data.get('followers', 0)}
        About: {profile_data.get('about', '')}

        Work Experience: {json.dumps(profile_data.get('experiences', []), ensure_ascii=False)}
        Education: {json.dumps(profile_data.get('educations', []), ensure_ascii=False)}
        """

        analysis_prompt = f"""
        Based on the following LinkedIn profile, determine if this person is already a notable figure, celebrity, or industry leader who should be considered their own role model.

        Profile Information:
        {profile_summary}

        Consider these factors:
        1. Industry recognition and leadership position
        2. Company prominence and role significance
        3. Public profile indicators (high connections/followers)
        4. Notable achievements mentioned in their profile
        5. Whether they are likely to be recognized in their field
        6. Executive/founder status at known companies

        A person should be considered a "celebrity/notable figure" if they:
        - Are C-level executives at well-known companies
        - Have founded successful companies
        - Have exceptionally high social media following (>50K followers)
        - Hold prominent positions that would make them industry leaders
        - Are likely to be recognized figures in their professional field

        Return a JSON object with:
        {{
            "is_celebrity": true/false,
            "reasoning": "Brief explanation (30-50 words) of why they are or aren't considered a notable figure, focusing on their achievements, position, and industry recognition."
        }}

        Return only the JSON object, no additional text.
        """

        result = openrouter_chat(
            task="linkedin_celebrity_check",
            messages=[{"role": "user", "content": analysis_prompt}],
            model=get_model("fast", task="linkedin_celebrity_check"),
            temperature=0.3,
            max_tokens=300,
            expect_json=True,
        )
        if isinstance(result, dict):
            logger.info(f"AI celebrity check result for {person_name}: {result}")
            return result
        return {"is_celebrity": False, "reasoning": "Unable to determine celebrity status"}

    except Exception as e:
        logger.error(f"Error in AI celebrity check: {e}")
        # Fallback to simple heuristic check
        return fallback_celebrity_check(profile_data, person_name)

def fallback_celebrity_check(profile_data: Dict[str, Any], person_name: str) -> Dict[str, Any]:
    """
    Fallback celebrity check using simple heuristics.

    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name

    Returns:
        Dictionary with is_celebrity and reasoning
    """
    try:
        connections = profile_data.get('connections', 0)
        followers = profile_data.get('followers', 0)
        headline = profile_data.get('headline', '').lower()

        # Simple heuristic checks
        is_celebrity = (
            connections > 50000 or
            followers > 100000 or
            any(word in headline for word in ['ceo', 'founder', 'chief executive', 'president']) and
            profile_data.get('companyName', '').lower() in ['google', 'microsoft', 'apple', 'amazon', 'meta', 'tesla', 'openai']
        )

        if is_celebrity:
            reasoning = "High-profile executive or public figure with significant social media presence"
        else:
            reasoning = "Professional profile without clear celebrity indicators"

        return {"is_celebrity": is_celebrity, "reasoning": reasoning}

    except Exception as e:
        logger.error(f"Error in fallback celebrity check: {e}")
        return {"is_celebrity": False, "reasoning": "Unable to determine status"}

def is_already_celebrity(profile_data: Dict[str, Any], person_name: str) -> bool:
    """
    Check if the person is already a celebrity/notable figure who should be their own role model.

    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name

    Returns:
        True if person is already a celebrity, False otherwise
    """
    try:
        # Import LinkedIn talents handler to check against celebrity list
        from server.api.linkedin_talents_handler import read_talents_from_csv, process_talent_data

        # Read LinkedIn celebrities data
        celebrities = read_talents_from_csv()
        processed_celebrities = [process_talent_data(celeb) for celeb in celebrities]

        # Check if person name matches any celebrity
        person_name_lower = person_name.lower().strip()
        for celebrity in processed_celebrities:
            celebrity_name = celebrity.get('name', '').lower().strip()
            if celebrity_name and person_name_lower == celebrity_name:
                logger.info(f"Found {person_name} in celebrity list")
                return True

        # Additional checks for high-profile indicators
        connections = profile_data.get('connections', 0)
        followers = profile_data.get('followers', 0)
        headline = profile_data.get('headline', '').lower()
        about = profile_data.get('about', '').lower()

        # Check for high-profile indicators
        high_profile_indicators = [
            connections > 10000,  # Very high connections
            followers > 50000,    # High follower count
            any(word in headline for word in ['founder', 'ceo', 'chief', 'president', 'vp']),
            any(word in about for word in ['ted talk', 'keynote', 'bestselling', 'award-winning', 'recognized']),
            profile_data.get('companyName', '').lower() in ['google', 'microsoft', 'apple', 'amazon', 'meta', 'tesla', 'openai', 'anthropic']
        ]

        # If multiple high-profile indicators, consider them a celebrity
        if sum(high_profile_indicators) >= 2:
            logger.info(f"{person_name} has multiple high-profile indicators - treating as celebrity")
            return True

        return False

    except Exception as e:
        logger.error(f"Error checking if {person_name} is celebrity: {e}")
        return False

def find_linkedin_celebrity_role_model(profile_data: Dict[str, Any], person_name: str) -> Dict[str, Any]:
    """
    Find a matching role model from LinkedIn celebrities using AI analysis.

    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name

    Returns:
        Dictionary containing role model information or None if no match found
    """
    try:
        # First try AI-powered matching
        ai_role_model = find_celebrity_with_ai(profile_data, person_name)
        if ai_role_model:
            logger.info(f"Found AI-matched celebrity role model: {ai_role_model.get('name', 'Unknown')}")
            return ai_role_model

        # Fallback to rule-based matching if AI fails
        logger.info("AI matching failed, falling back to rule-based matching")
        return find_celebrity_with_rules(profile_data, person_name)

    except Exception as e:
        logger.error(f"Error finding LinkedIn celebrity role model: {e}")
        return None

def find_celebrity_with_ai(profile_data: Dict[str, Any], person_name: str) -> Optional[Dict[str, Any]]:
    """
    Use AI to find the best matching celebrity role model.

    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name

    Returns:
        Role model dictionary or None if no match found
    """
    try:
        from server.api.linkedin_talents_handler import read_talents_from_csv, process_talent_data

        # Read celebrity data
        celebrities = read_talents_from_csv()
        processed_celebrities = [process_talent_data(celeb) for celeb in celebrities]

        # Build user profile summary
        user_headline = profile_data.get('headline', '')
        user_experiences = profile_data.get('experiences', [])
        user_skills = profile_data.get('skills', [])
        user_about = profile_data.get('about', '')
        user_industry = profile_data.get('companyIndustry', '')

        # Create user profile text
        user_profile_text = f"""
        Headline: {user_headline}
        Industry: {user_industry}
        About: {user_about}...
        Recent Experience: {user_experiences[0].get('title', '') if user_experiences else 'N/A'}
        Key Skills: {', '.join([skill.get('title', '') for skill in user_skills[:5]])}
        """

        # Create celebrities list for AI
        celebrities_text = ""
        for i, celeb in enumerate(processed_celebrities):
            celebrities_text += f"""
        {i+1}. {celeb.get('name', 'Unknown')}
           Company: {celeb.get('company', 'Unknown')}
           Title: {celeb.get('title', 'Unknown')}
           Achievement: {celeb.get('remark', 'Professional leader')}
        """

        # AI prompt for role model matching
        prompt = f"""
        You are an expert career advisor. Based on the user's professional profile, find the MOST SIMILAR role model from the provided list of successful professionals.

        USER PROFILE:
        {user_profile_text}

        AVAILABLE ROLE MODELS:
        {celebrities_text}

        ANALYSIS CRITERIA:
        1. Industry/Field similarity (same or related industries)
        2. Career stage and role level compatibility
        3. Skills and expertise overlap
        4. Professional trajectory alignment
        5. Inspirational value for the user's career growth

        INSTRUCTIONS:
        - Analyze the user's profile deeply
        - Compare with each role model's background
        - Select the ONE best match that would be most inspiring and relevant
        - If no good match exists (similarity < 70%), return "NO_MATCH"

        Return ONLY the exact name from the list (e.g., "Andrew Ng") or "NO_MATCH".
        """

        ai_choice = openrouter_chat(
            task="linkedin_role_model_select",
            messages=[{"role": "user", "content": prompt}],
            model=get_model("fast", task="linkedin_role_model_select"),
            temperature=0.3,
            max_tokens=50,
        )
        if not ai_choice:
            logger.error("AI API returned empty content")
            return None

        ai_choice = str(ai_choice).strip()
        if ai_choice == "NO_MATCH":
            logger.info("AI determined no good role model match exists")
            return None

        for celebrity in processed_celebrities:
            if celebrity.get('name', '').lower() == ai_choice.lower():
                user_company = ""
                user_title = ""
                if user_experiences:
                    user_company = user_experiences[0].get('subtitle', '')
                    user_title = user_experiences[0].get('title', '')
                role_model = convert_celebrity_to_role_model(celebrity, user_company, user_title)
                return role_model

        logger.warning(f"AI selected '{ai_choice}' but name not found in celebrity list")
        return None

    except Exception as e:
        logger.error(f"Error in AI celebrity matching: {e}")
        return None

def find_celebrity_with_rules(profile_data: Dict[str, Any], person_name: str) -> Optional[Dict[str, Any]]:
    """
    Fallback rule-based celebrity matching (original logic).

    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name

    Returns:
        Role model dictionary or None if no match found
    """
    try:
        from server.api.linkedin_talents_handler import read_talents_from_csv, process_talent_data

        # Read LinkedIn celebrities data
        celebrities = read_talents_from_csv()
        processed_celebrities = [process_talent_data(celeb) for celeb in celebrities]

        def _s(v: Any) -> str:
            return str(v).strip() if isinstance(v, str) else ""

        # Extract user's profile information for matching (support multiple scraper schemas).
        user_experiences = profile_data.get('experiences', [])
        if not isinstance(user_experiences, list):
            user_experiences = []
        raw_skills = profile_data.get('skills', [])

        user_headline = _s(profile_data.get('headline')) or _s(profile_data.get('occupation')) or _s(profile_data.get('jobTitle'))

        # Normalize skills for calculate_similarity_score (expects list[dict]).
        user_skills: List[Dict[str, Any]] = []
        if isinstance(raw_skills, list):
            for s in raw_skills:
                if isinstance(s, dict):
                    user_skills.append(s)
                elif isinstance(s, str) and s.strip():
                    user_skills.append({"title": s.strip()})

        def _extract_first_exp_field(keys: List[str]) -> str:
            if not user_experiences:
                return ""
            e0 = user_experiences[0]
            if not isinstance(e0, dict):
                return ""
            for k in keys:
                v = e0.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return ""

        user_company = _s(profile_data.get('companyName')) or _s(profile_data.get('company')) or _extract_first_exp_field(
            ['companyName', 'company', 'subtitle', 'companyNameText', 'company_name']
        )
        user_title = _s(profile_data.get('jobTitle')) or _s(profile_data.get('headline')) or _s(profile_data.get('occupation')) or _extract_first_exp_field(
            ['position', 'title', 'jobTitle']
        )

        # Score each celebrity based on similarity.
        scored_celebrities = []
        for celebrity in processed_celebrities:
            if str(celebrity.get('name', '') or '').strip().lower() == str(person_name or '').strip().lower():
                continue
            score = calculate_similarity_score(
                user_company, user_title, user_headline, user_skills,
                celebrity
            )
            scored_celebrities.append((celebrity, score))

        if scored_celebrities:
            scored_celebrities.sort(
                key=lambda x: (
                    float(x[1]),
                    int((x[0] or {}).get('salary_numeric', 0) or 0),
                ),
                reverse=True,
            )
            top_score = float(scored_celebrities[0][1])

            # Require a minimum similarity to avoid nonsense matches.
            # Lower than the historical 15 because different scrapers may omit company/title fields.
            if top_score < 10.0:
                return None

            # Prefer "more successful" candidates among similarly-scored matches.
            pool = [(c, s) for c, s in scored_celebrities if float(s) >= top_score - 10.0]
            pool.sort(
                key=lambda x: (
                    float(x[1]),
                    int((x[0] or {}).get('salary_numeric', 0) or 0),
                ),
                reverse=True,
            )
            best_match = pool[0][0]
            return convert_celebrity_to_role_model(best_match, user_company, user_title)

        return None

    except Exception as e:
        logger.error(f"Error in rule-based celebrity matching: {e}")
        return None

# Removed find_linkedin_celebrity_role_model_relaxed function - no longer needed
# We now use self as role model when no external match is found

def calculate_similarity_score(user_company: str, user_title: str, user_headline: str,
                             user_skills: List[Dict], celebrity: Dict[str, str]) -> float:
    """
    Calculate similarity score between user and celebrity.

    Args:
        user_company: User's current company
        user_title: User's current title
        user_headline: User's headline
        user_skills: User's skills list
        celebrity: Celebrity data dictionary

    Returns:
        Similarity score (0-100)
    """
    score = 0.0

    celebrity_company = celebrity.get('company', '').lower()
    celebrity_title = celebrity.get('title', '').lower()

    # Company similarity (30% weight)
    if user_company and celebrity_company:
        if user_company.lower() in celebrity_company or celebrity_company in user_company.lower():
            score += 30
        elif any(word in celebrity_company for word in user_company.lower().split() if len(word) > 3):
            score += 15

    # Title similarity (40% weight)
    if user_title and celebrity_title:
        user_title_words = set(user_title.lower().split())
        celebrity_title_words = set(celebrity_title.lower().split())

        # Check for exact title matches
        if user_title.lower() == celebrity_title:
            score += 40
        elif any(word in celebrity_title for word in ['ceo', 'founder', 'chief'] if word in user_title.lower()):
            score += 35
        elif any(word in celebrity_title for word in ['director', 'manager', 'lead'] if word in user_title.lower()):
            score += 25
        elif len(user_title_words.intersection(celebrity_title_words)) > 0:
            score += 15

    # Industry/Field similarity (20% weight) - IMPROVED LOGIC
    tech_keywords = ['ai', 'artificial intelligence', 'machine learning', 'deep learning',
                    'data science', 'software', 'technology', 'engineering', 'developer', 'programmer']
    business_keywords = ['marketing', 'sales', 'business', 'finance', 'consulting', 'strategy',
                        'operations', 'hr', 'human resources', 'accounting']
    creative_keywords = ['design', 'creative', 'content', 'media', 'social media', 'writing',
                        'copywriting', 'brand', 'advertising']

    user_text = f"{user_headline} {user_title}".lower()
    celebrity_text = f"{celebrity.get('remark', '')} {celebrity_title}".lower()

    user_tech_score = sum(1 for keyword in tech_keywords if keyword in user_text)
    user_business_score = sum(1 for keyword in business_keywords if keyword in user_text)
    user_creative_score = sum(1 for keyword in creative_keywords if keyword in user_text)

    celebrity_tech_score = sum(1 for keyword in tech_keywords if keyword in celebrity_text)
    celebrity_business_score = sum(1 for keyword in business_keywords if keyword in celebrity_text)
    celebrity_creative_score = sum(1 for keyword in creative_keywords if keyword in celebrity_text)

    # Only give points if both user and celebrity are in the SAME field
    if user_tech_score > 0 and celebrity_tech_score > 0:
        score += 20
    elif user_business_score > 0 and celebrity_business_score > 0:
        score += 20
    elif user_creative_score > 0 and celebrity_creative_score > 0:
        score += 20
    # PENALTY for field mismatch - reduce cross-field matching
    elif (user_tech_score > 0 and celebrity_tech_score == 0) or \
         (user_business_score > 0 and celebrity_business_score == 0) or \
         (user_creative_score > 0 and celebrity_creative_score == 0):
        score -= 5  # Penalty for field mismatch

    # Skills similarity (10% weight)
    if user_skills:
        user_skill_names = [skill.get('title', '').lower() for skill in user_skills[:10]]
        celebrity_remark = celebrity.get('remark', '').lower()

        skill_matches = sum(1 for skill in user_skill_names if skill and skill in celebrity_remark)
        if skill_matches > 0:
            score += min(10, skill_matches * 2)

    return score

def convert_celebrity_to_role_model(celebrity: Dict[str, str], user_company: str, user_title: str) -> Dict[str, Any]:
    """
    Convert celebrity data to role model format.

    Args:
        celebrity: Celebrity data dictionary
        user_company: User's company for similarity reason
        user_title: User's title for similarity reason

    Returns:
        Role model dictionary in standard format
    """
    # Generate similarity reason
    similarity_reason = generate_similarity_reason(celebrity, user_company, user_title)

    # Create achievement description
    achievement = create_achievement_description(celebrity)

    role_model = {
        "name": celebrity.get('name', ''),
        "institution": celebrity.get('company', ''),
        "position": celebrity.get('title', ''),
        "photo_url": celebrity.get('photo_url', ''),
        "achievement": achievement,
        "similarity_reason": similarity_reason
    }

    return role_model

def generate_similarity_reason(celebrity: Dict[str, str], user_company: str, user_title: str) -> str:
    """
    Generate similarity reason between user and celebrity.

    Args:
        celebrity: Celebrity data
        user_company: User's company
        user_title: User's title

    Returns:
        Similarity reason string
    """
    reasons = []

    celebrity_company = celebrity.get('company', '')
    celebrity_title = celebrity.get('title', '')

    # Company similarity
    if user_company and celebrity_company:
        if user_company.lower() in celebrity_company.lower() or celebrity_company.lower() in user_company.lower():
            reasons.append(f"both work in similar companies ({celebrity_company})")
        elif any(word in celebrity_company.lower() for word in user_company.lower().split() if len(word) > 3):
            reasons.append(f"both work in the technology industry")

    # Title similarity
    if user_title and celebrity_title:
        if any(word in celebrity_title.lower() for word in ['ceo', 'founder', 'chief'] if word in user_title.lower()):
            reasons.append("both hold executive leadership positions")
        elif any(word in celebrity_title.lower() for word in ['director', 'manager', 'lead'] if word in user_title.lower()):
            reasons.append("both have management and leadership responsibilities")
        elif any(word in user_title.lower().split() for word in celebrity_title.lower().split() if len(word) > 3):
            reasons.append("both work in similar professional roles")

    # Default reasons if no specific matches
    if not reasons:
        if 'ai' in celebrity.get('remark', '').lower() or 'artificial intelligence' in celebrity.get('remark', '').lower():
            reasons.append("both are involved in the AI and technology sector")
        else:
            reasons.append("both are successful professionals in the technology industry")

    # Combine reasons
    if len(reasons) == 1:
        return f"You share career similarities with {celebrity.get('name', 'this role model')} as {reasons[0]}."
    elif len(reasons) == 2:
        return f"You share career similarities with {celebrity.get('name', 'this role model')} as {reasons[0]} and {reasons[1]}."
    else:
        return f"You share career similarities with {celebrity.get('name', 'this role model')} as {', '.join(reasons[:-1])}, and {reasons[-1]}."

def create_achievement_description(celebrity: Dict[str, str]) -> str:
    """
    Create achievement description for celebrity.

    Args:
        celebrity: Celebrity data

    Returns:
        Achievement description string
    """
    name = celebrity.get('name', '')
    company = celebrity.get('company', '')
    title = celebrity.get('title', '')
    salary = celebrity.get('salary_display', '')
    remark = celebrity.get('remark', '')

    # Create a comprehensive achievement description
    achievement_parts = []

    if title and company:
        achievement_parts.append(f"{title} at {company}")

    if salary and salary != 'Not disclosed':
        achievement_parts.append(f"estimated net worth: {salary}")

    if remark and remark.strip():
        # Clean up remark and add it
        clean_remark = remark.strip()
        if not clean_remark.endswith('.'):
            clean_remark += '.'
        achievement_parts.append(clean_remark)

    if achievement_parts:
        return '; '.join(achievement_parts)
    else:
        return f"Successful professional in the technology industry"

def convert_linkedin_to_report(profile_data: Dict[str, Any], person_name: str) -> Dict[str, Any]:
    """
    Convert LinkedIn profile data to report format for Scholar analysis
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        Report format dictionary
    """
    try:
        # Extract basic information
        headline = profile_data.get('headline') or profile_data.get('jobTitle') or ""
        location = profile_data.get('location') or profile_data.get('addressWithCountry') or ""
        about = profile_data.get('about') or ""
        experiences = profile_data.get('experiences', [])
        educations = profile_data.get('educations', [])
        skills = profile_data.get('skills', [])
        
        # Create researcher info
        researcher = {
            "name": person_name,
            "affiliation": extract_company_from_experiences(experiences),
            "h_index": 0,  # LinkedIn doesn't have h-index
            "total_citations": 0,  # LinkedIn doesn't have citations
            "research_fields": [skill.get('title', '') for skill in skills[:10] if skill.get('title')] if skills else []  # Extract skill titles as research fields
        }
        
        # Validate research_fields to ensure they are strings
        if researcher["research_fields"]:
            researcher["research_fields"] = [str(field) for field in researcher["research_fields"] if field]
        
        # Create publication stats (simulated for LinkedIn)
        publication_stats = {
            "total_papers": len(experiences),
            "first_author_papers": len([exp for exp in experiences if (exp.get('title') or '').lower().find('senior') == -1]),
            "last_author_papers": len([exp for exp in experiences if (exp.get('title') or '').lower().find('senior') != -1]),
            "top_tier_papers": len([exp for exp in experiences if is_top_tier_company(exp.get('subtitle', ''))]),
            "first_author_percentage": 0,
            "last_author_percentage": 0,
            "top_tier_percentage": 0
        }
        
        # Calculate percentages
        if publication_stats["total_papers"] > 0:
            publication_stats["first_author_percentage"] = (publication_stats["first_author_papers"] / publication_stats["total_papers"]) * 100
            publication_stats["last_author_percentage"] = (publication_stats["last_author_papers"] / publication_stats["total_papers"]) * 100
            publication_stats["top_tier_percentage"] = (publication_stats["top_tier_papers"] / publication_stats["total_papers"]) * 100
        
        # Create most cited paper (simulated)
        most_cited_paper = None
        if experiences:
            most_recent = experiences[0]  # Most recent experience
            most_cited_paper = {
                "title": most_recent.get('title', ''),
                "year": extract_year_from_duration(most_recent.get('caption', '')),
                "venue": most_recent.get('subtitle', ''),
                "citations": 100  # Simulated citation count
            }
            publication_stats["most_cited_paper"] = most_cited_paper
        
        # Create report
        report = {
            "researcher": researcher,
            "publication_stats": publication_stats
        }
        
        return report
        
    except Exception as e:
        logger.error(f"Error converting LinkedIn to report: {e}")
        return {
            "researcher": {
                "name": person_name,
                "affiliation": "",
                "h_index": 0,
                "total_citations": 0,
                "research_fields": []
            },
            "publication_stats": {
                "total_papers": 0,
                "first_author_papers": 0,
                "last_author_papers": 0,
                "top_tier_papers": 0,
                "first_author_percentage": 0,
                "last_author_percentage": 0,
                "top_tier_percentage": 0
            }
        }

def extract_company_from_experiences(experiences: list) -> str:
    """Extract current company from experiences (best-effort across scraper schemas)."""
    if not isinstance(experiences, list) or not experiences:
        return ""
    first = experiences[0]
    if isinstance(first, dict):
        for k in ("companyName", "company", "subtitle", "companyNameText", "company_name", "title"):
            v = first.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""

def is_top_tier_company(company: str) -> bool:
    """Check if company is top tier"""
    if not company:
        return False
    
    top_tier_companies = [
        "google", "microsoft", "apple", "amazon", "meta", "facebook",
        "netflix", "uber", "airbnb", "stripe", "palantir", "openai",
        "anthropic", "nvidia", "tesla", "spacex", "linkedin", "twitter"
    ]
    
    return any(top_company in company.lower() for top_company in top_tier_companies)

def extract_year_from_duration(duration: str) -> int:
    """Extract year from duration string"""
    try:
        import re
        # Look for year patterns like "2023 - 2024" or "2023"
        year_match = re.search(r'20\d{2}', duration)
        if year_match:
            return int(year_match.group())
        return 2024  # Default year
    except:
        return 2024

def create_self_role_model(profile_data: Dict[str, Any], person_name: str) -> Dict[str, Any]:
    """
    Create self role model using LinkedIn profile data
    
    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        
    Returns:
        Self role model dictionary
    """
    try:
        # Extract information from profile
        headline = profile_data.get('headline') or profile_data.get('jobTitle') or ""
        experiences = profile_data.get('experiences', [])
        current_company = extract_company_from_experiences(experiences)
        if not current_company:
            current_company = profile_data.get("companyName") or profile_data.get("company") or ""
        
        # Create enhanced achievement description
        connections = profile_data.get('connections', 0)
        followers = profile_data.get('followers', 0)
        about = profile_data.get('about', '')

        # Build achievement based on profile strength
        achievement_parts = []
        if current_company:
            achievement_parts.append(f"{headline} at {current_company}")

        if connections > 5000:
            achievement_parts.append(f"influential professional with {connections:,} connections")
        elif connections > 1000:
            achievement_parts.append(f"well-connected professional with {connections:,} connections")

        if followers > 10000:
            achievement_parts.append(f"thought leader with {followers:,} followers")

        if any(word in headline.lower() for word in ['founder', 'ceo', 'chief', 'president']):
            achievement_parts.append("executive leader driving organizational success")

        if any(word in about.lower() for word in ['award', 'recognition', 'speaker', 'expert']):
            achievement_parts.append("recognized expert in their field")

        achievement = '; '.join(achievement_parts) if achievement_parts else f"Professional at {current_company}" if current_company else "Professional"

        # Create standard similarity reason for non-celebrities
        similarity_reason = "You are already your own role model! Your unique career path and professional achievements make you an inspiration to others in your field."

        # Extract real name from profile data, fallback to person_name if not available
        real_name = None

        # Try different name fields
        if profile_data.get('fullName'):
            real_name = profile_data.get('fullName')
        elif profile_data.get('firstName') and profile_data.get('lastName'):
            real_name = f"{profile_data.get('firstName')} {profile_data.get('lastName')}"
        elif profile_data.get('firstName'):
            real_name = profile_data.get('firstName')
        elif profile_data.get('name'):
            real_name = profile_data.get('name')
        else:
            real_name = person_name

        # Ensure real_name is never None
        if real_name:
            real_name = real_name.strip()
        if not real_name:
            real_name = person_name or "Professional"

        # If we still have a URL-like name (contains hyphens and numbers), try to clean it
        if real_name and '-' in real_name and any(char.isdigit() for char in real_name):
            # This looks like a LinkedIn username, try to clean it
            clean_name_parts = []
            for part in real_name.split('-'):
                if not any(char.isdigit() for char in part) and len(part) > 1:
                    clean_name_parts.append(part.capitalize())
            if clean_name_parts:
                real_name = ' '.join(clean_name_parts)
            else:
                # If cleaning failed, use original person_name
                real_name = person_name

        # Create self role model
        self_role_model = {
            "name": real_name,
            "institution": current_company,
            "position": headline,
            "photo_url": profile_data.get('profilePic') or profile_data.get('profilePicHighQuality') or "",
            "achievement": achievement,
            "similarity_reason": similarity_reason
        }
        
        return self_role_model

    except Exception as e:
        logger.error(f"Error creating self role model: {e}")
        return {
            "name": person_name,
            "institution": "",
            "position": "",
            "photo_url": "",
            "achievement": "Professional",
            "similarity_reason": "You are already your own role model! Your unique career path and professional achievements make you an inspiration to others in your field.",
            "is_celebrity": False,
            "celebrity_reasoning": ""
        }

def create_enhanced_self_role_model(profile_data: Dict[str, Any], person_name: str, celebrity_reasoning: str) -> Dict[str, Any]:
    """
    Create enhanced self role model for celebrities/notable figures.

    Args:
        profile_data: LinkedIn profile data
        person_name: Person's name
        celebrity_reasoning: AI reasoning for why they're a celebrity

    Returns:
        Enhanced self role model dictionary
    """
    try:
        # Extract information from profile
        headline = profile_data.get('headline') or profile_data.get('jobTitle') or ""
        experiences = profile_data.get('experiences', [])
        current_company = extract_company_from_experiences(experiences)
        connections = profile_data.get('connections', 0)
        followers = profile_data.get('followers', 0)
        about = profile_data.get('about', '')

        # Build comprehensive achievement description for celebrities
        achievement_parts = []

        # Add primary role
        if current_company:
            achievement_parts.append(f"{headline} at {current_company}")
        else:
            achievement_parts.append(headline)

        # Add influence metrics
        if followers > 100000:
            achievement_parts.append(f"influential thought leader with {followers:,} followers")
        elif followers > 50000:
            achievement_parts.append(f"recognized industry voice with {followers:,} followers")
        elif connections > 50000:
            achievement_parts.append(f"highly connected professional with {connections:,} connections")
        elif connections > 10000:
            achievement_parts.append(f"well-networked leader with {connections:,} connections")

        # Add leadership indicators
        if headline and any(word in headline.lower() for word in ['founder', 'ceo', 'chief executive', 'president']):
            achievement_parts.append("visionary leader driving industry innovation")
        elif headline and any(word in headline.lower() for word in ['cto', 'chief technology', 'vp', 'vice president']):
            achievement_parts.append("senior executive shaping organizational strategy")

        # Add expertise indicators
        if about and any(word in about.lower() for word in ['award', 'recognition', 'speaker', 'keynote']):
            achievement_parts.append("recognized expert and thought leader")

        if about and any(word in about.lower() for word in ['bestselling', 'published', 'author']):
            achievement_parts.append("published thought leader")

        # Combine achievements
        achievement = '; '.join(achievement_parts) if achievement_parts else f"Notable {headline}"

        # Create celebrity-specific similarity reason
        similarity_reason = f"🌟 Congratulations! You are already a notable figure and industry leader. {celebrity_reasoning} Your achievements, influence, and professional impact make you an inspiration and role model for countless others aspiring to reach similar heights in their careers."

        # Extract real name from profile data, fallback to person_name if not available
        real_name = None

        # Try different name fields
        if profile_data.get('fullName'):
            real_name = profile_data.get('fullName')
        elif profile_data.get('firstName') and profile_data.get('lastName'):
            real_name = f"{profile_data.get('firstName')} {profile_data.get('lastName')}"
        elif profile_data.get('firstName'):
            real_name = profile_data.get('firstName')
        elif profile_data.get('name'):
            real_name = profile_data.get('name')
        else:
            real_name = person_name

        real_name = real_name.strip() if real_name else person_name

        # If we still have a URL-like name (contains hyphens and numbers), try to clean it
        if '-' in real_name and any(char.isdigit() for char in real_name):
            # This looks like a LinkedIn username, try to clean it
            clean_name_parts = []
            for part in real_name.split('-'):
                if not any(char.isdigit() for char in part) and len(part) > 1:
                    clean_name_parts.append(part.capitalize())
            if clean_name_parts:
                real_name = ' '.join(clean_name_parts)
            else:
                # If cleaning failed, use original person_name
                real_name = person_name

        # Create enhanced self role model
        enhanced_self_role_model = {
            "name": real_name,
            "institution": current_company,
            "position": headline,
            "photo_url": profile_data.get('profilePic') or profile_data.get('profilePicHighQuality') or "",
            "achievement": achievement,
            "similarity_reason": similarity_reason
        }

        return enhanced_self_role_model

    except Exception as e:
        logger.error(f"Error creating enhanced self role model: {e}")
        # Fallback to regular self role model
        return create_self_role_model(profile_data, person_name)

# Removed create_generic_role_model function - no longer needed
# We now use self as role model when no external match is found, following scholar analysis pattern
