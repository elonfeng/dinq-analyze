# coding: UTF-8
"""
Researcher Prompts

This module contains prompt templates for researcher-related AI queries.
"""

def get_salary_evaluation_prompt(author_info):
    """
    Get prompt for salary and level evaluation of a researcher.
    
    NOTE: This function is kept for backward compatibility.
    New code should use get_career_level_prompt and get_evaluation_bars_prompt instead.

    Args:
        author_info (str): Researcher profile information

    Returns:
        dict: Prompt message in OpenAI format
    """
    return {
        "role": "user",
        "content": """Based on the researcher's profile:

        {}

        CRITICAL INSTRUCTION: You must NEVER return "No data" for any field. Even with limited information, you must always generate reasonable data based on what's available. If information is sparse, make educated guesses based on patterns in academia and industry.

        Please analyze:
        1. Their Years of Experience (YoE) based on:
           - First publication year to present
           - Publication history pattern
           - Career progression
        2. Their equivalent level at Google (e.g., L5, L6, L7, etc.) and corresponding Alibaba level (Alibaba P level = Google L level + 2, e.g., Google L5 = Alibaba P7)
        3. Estimated total annual compensation including base salary, bonus, and stock grants. Provide a realistic but optimistic estimation:
           - Full professors at top institutions can earn 1200000-1500000 USD annually
           - Associate professors typically earn 400000-700000 USD
           - Assistant professors typically earn 200000-400000 USD
           - Industry researchers at equivalent levels typically earn 10-20% more than academic counterparts
           - Senior industry researchers (L7+/P9+) can earn 800000-1600000 USD annually
        4. Detailed justification for this evaluation
        5. Three evaluation bars (each from 0-10):
           - Research Depth vs Breadth (0=very broad, 10=very deep)
             * Consider: Does the researcher focus deeply on a few specific topics or broadly across many areas?
             * Depth indicators: Multiple papers on the same topic, progressive advancement in a specific area, highly specialized venues
             * Breadth indicators: Publications across diverse topics, collaborations in different fields, varied publication venues
             * Analyze publication history, citation patterns, and research focus areas
           - Theory vs Practice (0=very practical, 10=very theoretical)
             * Consider: Does the researcher focus on theoretical foundations or practical applications?
             * Theory indicators: Mathematical models, proofs, algorithms, foundational concepts, methodology papers
             * Practice indicators: System implementations, real-world applications, industry collaborations, datasets, tools
             * Analyze paper titles, venues (e.g., theoretical conferences vs. applied conferences), and paper abstracts
           - Individual vs Team (0=very individual, 10=very team-oriented)
             * Consider: Does the researcher typically work alone or as part of larger teams?
             * Individual indicators: High percentage of single-author or first-author papers, consistent research direction
             * Team indicators: Many co-authors, large collaborative projects, varied author positions, interdisciplinary work
             * Analyze author lists, author positions, and collaboration patterns across publications

        Return in JSON format with exactly these fields:
        {{
            "years_of_experience": {{
                "years": [number],
                "start_year": [year],
                "calculation_basis": "[brief explanation of YoE calculation in English]"
            }},
            "level_us": "L[X]",
            "level_cn": "P[X+2]",
            "earnings": "[amount in USD without commas or separators]",
            "justification": "[IMPORTANT: Provide a concise justification of 50-70 words in English that emphasizes strengths and potential, highlighting publications, impact, and experience. Be generous in assessment.]",
            "evaluation_bars": {{
                 "depth_vs_breadth": {{
                    "score": [3-7],
                    "explanation": "[IMPORTANT: Provide a single-sentence explanation that cites specific evidence from their publication history, such as paper topics, venues, and research progression. Include concrete examples of depth or breadth in their work. NEVER return 'No data' or empty explanations - always provide meaningful content even with limited information.]"
                }},
                "theory_vs_practice": {{
                    "score": [3-7],
                    "explanation": "[IMPORTANT: Provide a single-sentence explanation that analyzes the nature of their research contributions. Cite specific examples of theoretical work (e.g., algorithms, models) or practical applications (e.g., systems, tools, datasets) from their publication record. NEVER return 'No data' or empty explanations - always provide meaningful content even with limited information.]"
                }},
                "individual_vs_team": {{
                    "score": [3-7],
                    "explanation": "[IMPORTANT: Provide a single-sentence explanation that examines their collaboration patterns. Include specific statistics about authorship positions, typical team sizes, and consistency of collaborators. Note any trends in how they approach research collaboration. NEVER return 'No data' or empty explanations - always provide meaningful content even with limited information.]"
                }}
            }}
        }}

        FINAL REMINDER: You must NEVER return "No data" for any field. Always generate reasonable data based on available information or make educated guesses. All levels, evaluations, and explanations MUST contain actual content.

        Please provide all text responses in English only.""".format(author_info)
    }


def get_career_level_prompt(author_info):
    """
    Get prompt for career level and earnings evaluation of a researcher.
    This is the first part of the split from the original get_salary_evaluation_prompt.
    
    Args:
        author_info (str): Researcher profile information
    
    Returns:
        dict: Prompt message in OpenAI format
    """
    return {
        "role": "user",
        "content": """Based on the researcher's profile:
    
        {}
    
        CRITICAL INSTRUCTION: You must NEVER return "No data" for any field. Even with limited information, you must always generate reasonable data based on what's available. If information is sparse, make educated guesses based on patterns in academia and industry.
    
        EVALUATION APPROACH: Be AGGRESSIVE and COMPETITIVE in recognizing top-tier AI/ML talent value. The current AI talent war has driven compensation far beyond traditional software engineering levels for exceptional researchers.
    
        Please analyze ONLY these aspects:
        1. Their Years of Experience (YoE) based on:
           - First publication year to present (add +2 years for pre-publication research)
           - Publication history pattern
           - Career progression and industry roles
    
        2. Their equivalent level at Google (e.g., L5, L6, L7, etc.) and corresponding Alibaba level (Alibaba P level = Google L level + 2, e.g., Google L5 = Alibaba P7)
           Apply these GENEROUS upgrade criteria:
           - H-index >50: minimum L8
           - Citations >100K: minimum L8  
           - Chief Scientist/VP roles: minimum L9
           - Breakthrough papers (>50K citations): +1 level boost
           - 15+ years experience: minimum L8
    
        3. Evaluate compensation factors for programmatic calculation:
           Rate each factor from 1-10 (10 = highest):

           a) Research Impact Score (1-10):
              - H-index level (1=<5, 5=20-30, 10=>50)
              - Citation count (1=<1K, 5=10K-50K, 10=>100K)
              - Breakthrough papers impact

           b) Field Premium Score (1-10):
              - AI/ML/Computer Science: 8-10
              - Other STEM: 1-3
              - Non-STEM: 1

           c) Role Seniority Score (1-10):
              - Student/Postdoc: 1-3
              - Assistant Professor/Researcher: 4-5
              - Associate Professor/Senior Researcher: 6-7
              - Full Professor/Principal Researcher: 8-9
              - Chief Scientist/VP/Distinguished: 10

           d) Industry Leadership Score (1-10):
              - Academic only: 1-4
              - Some industry collaboration: 5-6
              - Industry roles/consulting: 7-8
              - Industry leadership/founding: 9-10

           e) Market Competition Score (1-10):
              - Niche field: 1-4
              - Competitive field: 5-7
              - Hot field (AI/ML): 8-10
    
        4. Detailed justification for this evaluation (50-70 words explaining why this researcher commands their compensation level, emphasizing their competitive advantages, market value, and unique contributions)
    
        Return in JSON format with exactly these fields:
        {{
            "years_of_experience": {{
                "years": [number],
                "start_year": [year],
                "calculation_basis": "[brief explanation of YoE calculation in English]"
            }},
            "level_us": "L[X]",
            "level_cn": "P[X+2]",
            "earnings": "PLACEHOLDER",
            "justification": "[IMPORTANT: Provide a concise justification of 50-70 words in English that emphasizes COMPETITIVE ADVANTAGES, market scarcity, research breakthroughs, and why this researcher commands their compensation level. Be generous and highlight exceptional value.]",
            "compensation_factors": {{
                "research_impact_score": [1-10],
                "field_premium_score": [1-10],
                "role_seniority_score": [1-10],
                "industry_leadership_score": [1-10],
                "market_competition_score": [1-10]
            }}
        }}
    
        FINAL REMINDER: You must NEVER return "No data" for any field. Set earnings to "PLACEHOLDER" - it will be calculated programmatically. Provide a thoughtful justification and accurate scoring of compensation factors.
    
        Please provide all text responses in English only.""".format(author_info)
   }


def get_evaluation_bars_prompt(author_info):
    """
    Get prompt for the three evaluation bars of a researcher.
    This is the second part of the split from the original get_salary_evaluation_prompt.

    Args:
        author_info (str): Researcher profile information

    Returns:
        dict: Prompt message in OpenAI format
    """
    return {
        "role": "user",
        "content": """Based on the researcher's profile:

        {}

        CRITICAL INSTRUCTION: You must NEVER return "No data" for any field. Even with limited information, you must always generate reasonable data based on what's available. If information is sparse, make educated guesses based on patterns in academia and industry.

        Please analyze ONLY these three evaluation bars (each from 0-10):
        1. Research Depth vs Breadth (0=very broad, 10=very deep)
           * Consider: Does the researcher focus deeply on a few specific topics or broadly across many areas?
           * Depth indicators: Multiple papers on the same topic, progressive advancement in a specific area, highly specialized venues
           * Breadth indicators: Publications across diverse topics, collaborations in different fields, varied publication venues
           * Analyze publication history, citation patterns, and research focus areas
        2. Theory vs Practice (0=very practical, 10=very theoretical)
           * Consider: Does the researcher focus on theoretical foundations or practical applications?
           * Theory indicators: Mathematical models, proofs, algorithms, foundational concepts, methodology papers
           * Practice indicators: System implementations, real-world applications, industry collaborations, datasets, tools
           * Analyze paper titles, venues (e.g., theoretical conferences vs. applied conferences), and paper abstracts
        3. Individual vs Team (0=very individual, 10=very team-oriented)
           * Consider: Does the researcher typically work alone or as part of larger teams?
           * Individual indicators: High percentage of single-author or first-author papers, consistent research direction
           * Team indicators: Many co-authors, large collaborative projects, varied author positions, interdisciplinary work
           * Analyze author lists, author positions, and collaboration patterns across publications

        Return in JSON format with exactly these fields:
        {{
            "evaluation_bars": {{
                "depth_vs_breadth": {{
                    "score": [3-7],
                    "explanation": "[IMPORTANT: Provide a single-sentence explanation that cites specific evidence from their publication history, such as paper topics, venues, and research progression. Include concrete examples of depth or breadth in their work. NEVER return 'No data' or empty explanations - always provide meaningful content even with limited information.]"
                }},
                "theory_vs_practice": {{
                    "score": [3-7],
                    "explanation": "[IMPORTANT: Provide a single-sentence explanation that analyzes the nature of their research contributions. Cite specific examples of theoretical work (e.g., algorithms, models) or practical applications (e.g., systems, tools, datasets) from their publication record. NEVER return 'No data' or empty explanations - always provide meaningful content even with limited information.]"
                }},
                "individual_vs_team": {{
                    "score": [3-7],
                    "explanation": "[IMPORTANT: Provide a single-sentence explanation that examines their collaboration patterns. Include specific statistics about authorship positions, typical team sizes, and consistency of collaborators. Note any trends in how they approach research collaboration. NEVER return 'No data' or empty explanations - always provide meaningful content even with limited information.]"
                }}
            }}
        }}

        FINAL REMINDER: You must NEVER return "No data" for any field. Always generate reasonable data based on available information or make educated guesses. All evaluations and explanations MUST contain actual content.

        Please provide all text responses in English only.""".format(author_info)
    }


def get_role_model_prompt(author_info_str, celeb_dict=None, max_tokens=100000):
    """
    Get prompt for finding a suitable role model for a researcher.

    Args:
        author_info_str (str): Formatted researcher profile information
        celeb_dict (dict, optional): Dictionary of celebrity researchers
        max_tokens (int, optional): Maximum tokens for the celebrity dictionary

    Returns:
        list: List of message dictionaries in OpenAI format
    """
    import json
    import logging

    logger = logging.getLogger('server.prompts.researcher_prompts')

    messages = [
        {
            "role": "system",
            "content": """You are an AI research mentor. Your task is to analyze the researcher's profile and find the most suitable role model from the provided academic database.

                        IMPORTANT: You must respond in English only.

                        Please return your analysis in the following JSON format:
                        {
                            "role_model": {
                                "name": "Role model's full name",
                                "institution": "Current institution",
                                "position": "Academic position",
                                "photo_url": "URL to their photo",
                                "achievement": "Their most significant achievement",
                                "similarity_reason": "[IMPORTANT: Provide a concise explanation of 50-70 words in English that explains why this role model matches the researcher's profile based on research interests, career trajectory, or methodological approach]"
                            }
                        }

                        Focus on matching research interests, career stage, and publication patterns.
                        The similarity_reason should be specific and based on concrete similarities in their research trajectory or expertise.

                        Remember: Your entire response must be in English only."""
        }
    ]

    # Add celebrity dictionary if provided, with size control
    if celeb_dict is not None:
        try:
            # 估计字典大小
            celeb_dict_str = str(celeb_dict)
            estimated_tokens = len(celeb_dict_str) / 4  # 粗略估计：平均每个token 4个字符

            logger.info(f"Celebrity dictionary size: {len(celeb_dict)} entries, {len(celeb_dict_str)} chars, est. {estimated_tokens:.0f} tokens")

            if estimated_tokens > max_tokens:
                logger.warning(f"Celebrity dictionary too large (est. {estimated_tokens} tokens), compressing...")

                # 更激进的压缩策略：只保留关键字段并直接限制条目数量
                # 首先限制条目数量，只保留前50个条目
                limited_items = list(celeb_dict.items())[:50]
                logger.info(f"Limiting to top 50 celebrity entries from {len(celeb_dict)} total")

                # 然后压缩每个条目的字段
                compressed_dict = {}
                for name, info in limited_items:
                    # 只保留最关键的字段，并省略研究领域
                    compressed_dict[name] = {
                        "name": info.get("name", name),
                        "institution": info.get("institution", info.get("affiliation", ""))
                    }

                # 记录压缩后的大小
                compressed_str = str(compressed_dict)
                compressed_tokens = len(compressed_str) / 4
                logger.info(f"After first compression: {len(compressed_dict)} entries, {len(compressed_str)} chars, est. {compressed_tokens:.0f} tokens")

                # 如果仍然太大，进一步减少条目
                if len(str(compressed_dict)) / 4 > max_tokens:
                    logger.warning("Even compressed dictionary too large, further limiting entries...")
                    # 只保留前20个条目
                    limited_dict = {}
                    for i, (name, info) in enumerate(compressed_dict.items()):
                        if i >= 20:  # 限制为20个条目
                            break
                        limited_dict[name] = info

                    compressed_dict = limited_dict
                    compressed_str = str(compressed_dict)
                    compressed_tokens = len(compressed_str) / 4
                    logger.info(f"Further limited to {len(compressed_dict)} celebrity entries, {len(compressed_str)} chars, est. {compressed_tokens:.0f} tokens")

                # 如果还是太大，则完全放弃使用字典
                if len(str(compressed_dict)) / 4 > max_tokens:
                    logger.warning("Dictionary still too large, abandoning dictionary approach")
                    # 不使用字典，而是提供一个简单的名人列表
                    top_names = list(compressed_dict.keys())[:10]
                    return [messages[0], {
                        "role": "system",
                        "content": f"Here are some notable researchers you can consider as role models: {', '.join(top_names)}"
                    }, messages[-1]]

                celeb_dict_str = json.dumps(compressed_dict)
                logger.info(f"Compressed dictionary size: {len(celeb_dict_str)} chars (est. {len(celeb_dict_str)/4} tokens)")

                messages.append({
                    "role": "system",
                    "content": f"Here is a compressed database of notable researchers: {celeb_dict_str}"
                })
            else:
                messages.append({
                    "role": "system",
                    "content": celeb_dict_str
                })
        except Exception as e:
            logger.error(f"Error processing celebrity dictionary: {e}")
            # 出错时不添加字典，但继续处理
            messages.append({
                "role": "system",
                "content": "Unable to provide celebrity database due to size constraints. Please suggest a well-known researcher in the field as a role model."
            })

    # Add user message with researcher profile
    messages.append({
        "role": "user",
        "content": "Please analyze this researcher's profile and suggest a role model: {}, return as JSON format."
        .format(author_info_str)
    })

    return messages


def get_paper_evaluation_prompt(paper_info):
    """
    Get prompt for generating a one-sentence evaluation of a research paper.

    Args:
        paper_info (dict): Information about the research paper

    Returns:
        dict: Prompt message in OpenAI format
    """
    return {
        "role": "user",
        "content": f"""Based on the following research paper information:

        {paper_info}

        Generate a single, concise sentence that evaluates the significance and impact of this paper.
        Your evaluation should:
        1. Highlight what makes this paper noteworthy or innovative
        2. Consider its impact on the field
        3. Be written in a professional academic tone
        4. Be no longer than 25 words
        5. Be in English only

        Return only the evaluation sentence without any additional text, quotes, or formatting.
        """
    }


def get_pk_roast_prompt(author1_info, author2_info):
    """
    Get prompt for generating a one-sentence roast comparing two researchers.

    Args:
        author1_info (str): Information about the first researcher
        author2_info (str): Information about the second researcher

    Returns:
        list: List of message dictionaries in OpenAI format
    """
    return [
        {
            "role": "system",
            "content": """You are an AI research mentor. Your task is to analyze the provided two researcher's profiles and generate a one sentence roast.
                        Focus on first author citation number, top paper, representative paper, and year of experience etc.
                        Return the roast in the following JSON format:
                        {
                            "roast": "your one sentence roast here",
                            "comparison_focus": ["aspect1", "aspect2", ...],
                            "winner": "researcher1 or researcher2 or tie"
                        }"""
        },
        {
            "role": "user",
            "content": f"Compare these researchers and generate a roast in JSON format: author1: {author1_info}, author2: {author2_info}"
        }
    ]
