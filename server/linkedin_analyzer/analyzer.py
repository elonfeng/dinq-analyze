import os
import json
import asyncio
import math
import logging
from datetime import datetime, timezone
import random
import re
from typing import Any, Optional, Dict, List
from server.llm.gateway import openrouter_chat
from server.config.llm_models import get_model

# Try to use DINQ project's trace logging system
try:
    from server.utils.trace_context import get_trace_logger
    logger = get_trace_logger(__name__)
except ImportError:
    # If cannot import, use standard logging
    logger = logging.getLogger(__name__)

# Import json-repair with fallback
try:
    from json_repair import repair_json
except ImportError:
    # Define a simple fallback function if json-repair is not installed
    def repair_json(json_str, **kwargs):
        logging.warning("json-repair library not available, using fallback")
        return json_str

# Import LinkedIn cache functions
try:
    from src.utils.linkedin_cache import get_linkedin_from_cache, cache_linkedin_data, update_linkedin_cache_partial
except ImportError:
    # Fallback functions if cache module is not available
    def get_linkedin_from_cache(linkedin_id: str, max_age_days: int = 7, person_name: str = None) -> Optional[Dict[str, Any]]:
        return None
    
    def cache_linkedin_data(linkedin_data: Dict[str, Any]) -> bool:
        return False
    
    def update_linkedin_cache_partial(linkedin_id: str, updates: Dict[str, Any]) -> bool:
        return False

class LinkedInAnalyzer:
    """LinkedIn Profile Analyzer"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tvly_client = None
        self.apify_api_key = config.get("apify", {}).get("api_key") or os.getenv("APIFY_API_KEY", "")
        self.use_cache = config.get("use_cache", True)
        self.cache_max_age_days = config.get("cache_max_age_days", 7)
        
        # Initialize Tavily client
        try:
            from tavily import TavilyClient
            tavily_key = os.getenv("TAVILY_API_KEY", "")
            self.tvly_client = TavilyClient(tavily_key) if tavily_key else None
            if self.tvly_client is not None:
                logger.info("Tavily client initialized successfully")
            from apify_client import ApifyClient
            self.apifyclient = ApifyClient(self.apify_api_key) if self.apify_api_key else None
        except Exception as e:
            logger.error(f"Failed to initialize Tavily client: {e}")
            self.tvly_client = None
            self.apifyclient = None

    def convert_datetime_for_json(self, obj):
        """
        Recursively convert datetime objects to ISO format strings for JSON serialization
        
        Args:
            obj: Object to convert (dict, list, or primitive type)
            
        Returns:
            Object with datetime objects converted to strings
        """
        if isinstance(obj, dict):
            return {k: self.convert_datetime_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_datetime_for_json(i) for i in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj

    def generate_linkedin_id(self, person_name: str, linkedin_url: str = None) -> str:
        """
        Generate a unique LinkedIn ID for caching purposes.
        
        Args:
            person_name: Person's name
            linkedin_url: LinkedIn URL if available
            
        Returns:
            Unique LinkedIn ID string
        """
        if linkedin_url and "linkedin.com/in/" in linkedin_url:
            # Extract LinkedIn username from URL
            linkedin_username = linkedin_url.split("linkedin.com/in/")[1].split("?")[0].split("/")[0]
            return f"{linkedin_username}"
        else:
            # Use person name as fallback
            return f"name:{person_name.lower().replace(' ', '_')}"

    def validate_and_complete_cache(self, cached_data: Dict[str, Any], callback=None) -> Dict[str, Any]:
        """
        Validate and complete cached LinkedIn data.
        
        Args:
            cached_data: Cached LinkedIn data
            callback: Optional progress callback function
            
        Returns:
            Validated and completed LinkedIn data
        """
        try:
            logger.info("Validating and completing cached LinkedIn data...")
            
            # Check if all required fields are present
            required_fields = ['profile_data']
            missing_fields = []
            
            for field in required_fields:
                if not cached_data.get(field):
                    missing_fields.append(field)
            
            if missing_fields:
                logger.warning(f"Missing fields in cached data: {missing_fields}")
                return None
            
            # Check if AI analysis is complete in profile_data
            profile_data = cached_data.get('profile_data', {})
            
            # Check required AI analysis fields
            required_ai_fields = ['role_model', 'money_analysis', 'roast', 'skills', 'colleagues_view', 'career', 'life_well_being']
            missing_ai_fields = []
            
            for field in required_ai_fields:
                if not profile_data.get(field):
                    missing_ai_fields.append(field)
            
            # Check if skills structure is complete

            
            if missing_ai_fields:
                logger.info(f"Missing AI analysis fields: {missing_ai_fields}, will regenerate...")
                
                # Regenerate missing AI analysis
                person_name = cached_data.get('person_name', '')
                
                if callback:
                    callback('ai_analysis', f'Regenerating missing AI analysis: {", ".join(missing_ai_fields)}')
                
                # Generate missing AI analysis
                from concurrent.futures import ThreadPoolExecutor, as_completed
                
                tasks = []
                
                def get_role_model_info(profile_data, person_name):
                    """Get role model information thread function"""
                    try:
                        from server.linkedin_analyzer.role_model_service import get_linkedin_role_model
                        role_model = get_linkedin_role_model(profile_data, person_name)
                        return ('role_model', role_model)
                    except Exception as e:
                        logger.error(f"Error getting role model: {str(e)}")
                        return ('role_model', None)
                
                def get_money_analysis_info(profile_data, person_name):
                    """Get money analysis information thread function"""
                    try:
                        from server.linkedin_analyzer.money_service import get_linkedin_money_analysis
                        money_analysis = get_linkedin_money_analysis(profile_data, person_name)
                        return ('money_analysis', money_analysis)
                    except Exception as e:
                        logger.error(f"Error getting money analysis: {str(e)}")
                        return ('money_analysis', None)
                
                def get_roast_info(profile_data, person_name):
                    """Get roast information thread function"""
                    try:
                        from server.linkedin_analyzer.roast_service import get_linkedin_roast
                        roast = get_linkedin_roast(profile_data, person_name)
                        return ('roast', roast)
                    except Exception as e:
                        logger.error(f"Error getting roast: {str(e)}")
                        return ('roast', "No roast available")
                
                def get_industry_knowledge_info(profile_data, person_name):
                    """Get industry knowledge information thread function"""
                    try:
                        from server.linkedin_analyzer.industry_knowledge_service import get_linkedin_industry_knowledge
                        industry_knowledge = get_linkedin_industry_knowledge(profile_data, person_name)
                        return ('industry_knowledge', industry_knowledge)
                    except Exception as e:
                        logger.error(f"Error getting industry knowledge: {str(e)}")
                        return ('industry_knowledge', [])
                
                def get_tools_technologies_info(profile_data, person_name):
                    """Get tools and technologies information thread function"""
                    try:
                        from server.linkedin_analyzer.tools_technologies_service import get_linkedin_tools_technologies
                        tools_technologies = get_linkedin_tools_technologies(profile_data, person_name)
                        return ('tools_technologies', tools_technologies)
                    except Exception as e:
                        logger.error(f"Error getting tools and technologies: {str(e)}")
                        return ('tools_technologies', [])
                
                def get_interpersonal_skills_info(profile_data, person_name):
                    """Get interpersonal skills information thread function"""
                    try:
                        from server.linkedin_analyzer.interpersonal_skills_service import get_linkedin_interpersonal_skills
                        interpersonal_skills = get_linkedin_interpersonal_skills(profile_data, person_name)
                        return ('interpersonal_skills', interpersonal_skills)
                    except Exception as e:
                        logger.error(f"Error getting interpersonal skills: {str(e)}")
                        return ('interpersonal_skills', [])
                
                def get_language_info(profile_data, person_name):
                    """Get language information thread function"""
                    try:
                        from server.linkedin_analyzer.language_service import get_linkedin_languages
                        languages = get_linkedin_languages(profile_data, person_name)
                        return ('language', languages)
                    except Exception as e:
                        logger.error(f"Error getting languages: {str(e)}")
                        return ('language', [])
                
                def get_colleagues_view_info(profile_data, person_name):
                    """Get colleagues view information thread function"""
                    try:
                        from server.linkedin_analyzer.colleagues_view_service import get_linkedin_colleagues_view
                        colleagues_view = get_linkedin_colleagues_view(profile_data, person_name)
                        return ('colleagues_view', colleagues_view)
                    except Exception as e:
                        logger.error(f"Error getting colleagues view: {str(e)}")
                        return ('colleagues_view', {"highlights": [], "areas_for_improvement": []})
                
                def get_career_info(profile_data, person_name):
                    """Get career information thread function"""
                    try:
                        from server.linkedin_analyzer.career_service import get_linkedin_career
                        career = get_linkedin_career(profile_data, person_name)
                        return ('career', career)
                    except Exception as e:
                        logger.error(f"Error getting career: {str(e)}")
                        return ('career', {"future_development_potential": "", "development_advice": {"past_evaluation": "", "future_advice": ""}})
                
                def get_life_well_being_info(profile_data, person_name):
                    """Get life and well-being information thread function"""
                    try:
                        from server.linkedin_analyzer.life_well_being_service import get_linkedin_life_well_being
                        life_well_being = get_linkedin_life_well_being(profile_data, person_name)
                        return ('life_well_being', life_well_being)
                    except Exception as e:
                        logger.error(f"Error getting life and well-being: {str(e)}")
                        return ('life_well_being', {"life_suggestion": "", "health": ""})
                
                # Add tasks for missing fields only
                if 'role_model' in missing_ai_fields:
                    tasks.append(('role_model', get_role_model_info, (profile_data, person_name)))
                if 'money_analysis' in missing_ai_fields:
                    tasks.append(('money_analysis', get_money_analysis_info, (profile_data, person_name)))
                if 'roast' in missing_ai_fields:
                    tasks.append(('roast', get_roast_info, (profile_data, person_name)))
                if 'skills' in missing_ai_fields:
                    # Add all skills-related tasks when skills is missing
                    tasks.append(('industry_knowledge', get_industry_knowledge_info, (profile_data, person_name)))
                    tasks.append(('tools_technologies', get_tools_technologies_info, (profile_data, person_name)))
                    tasks.append(('interpersonal_skills', get_interpersonal_skills_info, (profile_data, person_name)))
                    tasks.append(('language', get_language_info, (profile_data, person_name)))
                if 'colleagues_view' in missing_ai_fields:
                    tasks.append(('colleagues_view', get_colleagues_view_info, (profile_data, person_name)))
                if 'career' in missing_ai_fields:
                    tasks.append(('career', get_career_info, (profile_data, person_name)))
                if 'life_well_being' in missing_ai_fields:
                    tasks.append(('life_well_being', get_life_well_being_info, (profile_data, person_name)))
                
                # Execute tasks in parallel
                thread_results = {}
                with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
                    future_to_task = {}
                    for task_name, task_func, task_args in tasks:
                        future = executor.submit(task_func, *task_args)
                        future_to_task[future] = task_name
                    
                    for future in as_completed(future_to_task):
                        task_name = future_to_task[future]
                        try:
                            result_type, result_data = future.result()
                            thread_results[result_type] = result_data
                            if callback:
                                callback('ai_step_complete', f'Completed {task_name} analysis')
                            logger.info(f"Completed {task_name} analysis")
                        except Exception as e:
                            logger.error(f"Task {task_name} generated an exception: {e}")
                            thread_results[task_name] = None
                
                # Update AI analysis with new results
                updated_profile_data = profile_data.copy()
                for field, value in thread_results.items():
                    if value is not None:
                        updated_profile_data[field] = value
                
                # Process work experience and education with logo URLs
                import json
                try:
                    # Process work experience - directly use original experiences data
                    work_experience_data = profile_data.get('experiences', [])
                    if work_experience_data:
                        updated_profile_data["work_experience"] = work_experience_data
                    
                    # Process education - directly use original educations data
                    education_data = profile_data.get('educations', [])
                    if education_data:
                        updated_profile_data["education"] = education_data
                    
                    # Process skills - combine original skills data with AI analysis
                    original_skills = profile_data.get('skills', [])
                    original_languages = profile_data.get('languages', [])
                    
                    # Extract skill names from original data
                    original_skill_names = [skill.get('title', '') for skill in original_skills if skill.get('title')]
                    original_language_names = [lang.get('title', '') for lang in original_languages if lang.get('title')]
                    
                    # Combine AI analysis with original data
                    combined_skills = {
                        "industry_knowledge": thread_results.get('industry_knowledge', []),
                        "tools_technologies": thread_results.get('tools_technologies', []),
                        "interpersonal_skills": thread_results.get('interpersonal_skills', []),
                        "language": thread_results.get('language', [])
                    }
                    
                    # Add original skills data
                    if original_skills:
                        combined_skills["original_skills"] = original_skills
                    if original_languages:
                        combined_skills["original_languages"] = original_languages
                    
                    updated_profile_data["skills"] = combined_skills
                    
                except Exception as e:
                    logger.error(f"Error processing work experience and education data in cache validation: {e}")
                
                # Update cache with new AI analysis
                linkedin_id = cached_data.get('linkedin_id')
                if linkedin_id:
                    # Convert datetime objects to strings for JSON serialization
                    updated_profile_data = self.convert_datetime_for_json(updated_profile_data)
                    update_linkedin_cache_partial(linkedin_id, {'profile_data': updated_profile_data})
                
                # Update cached data
                cached_data['profile_data'] = updated_profile_data
            
            logger.info("LinkedIn cached data validation completed")
            return cached_data
            
        except Exception as e:
            logger.error(f"Error validating cached LinkedIn data: {e}")
            return None

    def search_linkedin_url(self, person_name: str) -> Optional[List[Dict[str, Any]]]:
        """
        Search for LinkedIn URLs based on user input name using tvly_client.search
        
        Args:
            person_name: Name to search for
            
        Returns:
            JSON array containing LinkedIn URL information or None
        """
        if not self.tvly_client:
            logger.error("Tavily client not available")
            return None
            
        try:
            logger.info(f"Searching LinkedIn URL for: {person_name}")
            
            response = self.tvly_client.search(
                query=person_name
            )

            # Extract LinkedIn URLs from search results
            linkedin_results = self.extract_linkedin_url_from_response(response, person_name)
            
            if linkedin_results:
                logger.info(f"Found {len(linkedin_results)} LinkedIn profiles for: {person_name}")
                return linkedin_results
            else:
                logger.warning(f"No LinkedIn URLs found for: {person_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error searching LinkedIn URL for {person_name}: {e}")
            return None

    def extract_linkedin_url_from_response(self, response: Dict[str, Any], person_name: str) -> Optional[List[Dict[str, Any]]]:
        """
        Extract LinkedIn URLs from Tavily response
        
        Args:
            response: Tavily API response
            person_name: Name to search for
            
        Returns:
            JSON array containing LinkedIn URL information or None
        """
        try:
            if not response or "results" not in response:
                return None
                
            results = response["results"]
            linkedin_results = []
            
            # Iterate through search results, looking for LinkedIn URLs
            for result in results:
                url = result.get("url", "")
                title = result.get("title", "")
                content = result.get("content", "")
                score = result.get("score", 0)
                
                # Check if it's a LinkedIn URL
                if "linkedin.com/in/" in url:
                    # Further verify if it matches the person's name
                    if self.is_likely_match(url, title, content, person_name):
                        linkedin_info = {
                            "url": url,
                            "title": title,
                            "content": content,
                            "score": score,
                            "person_name": person_name
                        }
                        linkedin_results.append(linkedin_info)
                        
            if linkedin_results:
                logger.info(f"Found {len(linkedin_results)} LinkedIn profiles for {person_name}")
                return linkedin_results
            else:
                logger.warning(f"No LinkedIn URLs found for {person_name}")
                return None
            
        except Exception as e:
            logger.error(f"Error extracting LinkedIn URL from response: {e}")
            return None

    def is_likely_match(self, url: str, title: str, content: str, person_name: str) -> bool:
        """
        Determine if LinkedIn URL likely matches target person
        
        Args:
            url: LinkedIn URL
            title: Page title
            content: Page content
            person_name: Target person's name
            
        Returns:
            Whether it likely matches
        """
        try:
            # Extract LinkedIn username
            if "linkedin.com/in/" in url:
                linkedin_username = url.split("linkedin.com/in/")[1].split("?")[0].split("/")[0]
                
                # Convert person's name to possible LinkedIn username format
                name_parts = person_name.lower().split()
                
                # Check if username contains parts of the person's name
                for part in name_parts:
                    if len(part) > 2 and part in linkedin_username:
                        return True
                        
                # Check if title and content contain the person's name
                search_text = (title + " " + content).lower()
                for part in name_parts:
                    if len(part) > 2 and part in search_text:
                        return True
                        
            return False
            
        except Exception as e:
            logger.error(f"Error in is_likely_match: {e}")
            return False

    def get_linkedin_profile(self, linkedin_url: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile based on LinkedIn URL
        
        Args:
            linkedin_url: LinkedIn profile URL
            
        Returns:
            LinkedIn profile data or None
        """
        try:
            logger.info(f"Fetching LinkedIn profile from: {linkedin_url}")
            
            # Extract LinkedIn username
            if "linkedin.com/in/" not in linkedin_url:
                logger.error(f"Invalid LinkedIn URL: {linkedin_url}")
                return None
                
            run_input = { "profileUrls": [
                    linkedin_url
                ] }

            # Run the Actor and wait for it to finish
            run = self.apifyclient.actor("2SyF0bVxmgGr8IVCZ").call(run_input=run_input)
            
            logger.info(f"Apify run completed with status: {run.get('status')}")
            
            # Check if run was successful
            if run.get('status') != 'SUCCEEDED':
                logger.error(f"Apify run failed with status: {run.get('status')}")
                return None
            
            # Get the dataset ID from the run
            dataset_id = run.get('defaultDatasetId')
            if not dataset_id:
                logger.error("No dataset ID found in run result")
                return None
            
            # Fetch the actual data from the dataset.
            # Only need the first item (profile), avoid pulling full pages when the dataset is large.
            dataset = self.apifyclient.dataset(dataset_id)
            try:
                items = dataset.list_items(limit=1).items
            except Exception:
                items = dataset.list_items().items
            
            if not items:
                logger.error("No items found in dataset")
                return None
            
            # Return the first item (should be the LinkedIn profile data)
            profile_data = items[0]
            
            # Convert datetime objects to strings for JSON serialization
            profile_data = self.convert_datetime_for_json(profile_data)
            
            # Add debug logging to see the actual structure
            logger.info(f"LinkedIn profile data keys: {list(profile_data.keys())}")
            logger.info(f"Successfully fetched LinkedIn profile data")
            
            return profile_data
                
        except Exception as e:
            logger.error(f"Error fetching LinkedIn profile from {linkedin_url}: {e}")
            return None

    def get_company_logo_url(self, company_name):
        """获取公司logo URL"""
        if not company_name:
            return None
        
        # 转换公司名为文件名格式（小写，空格转下划线）
        filename = company_name.lower().replace(' ', '_')
        
        # 检查当前目录下的 images/company 文件夹
        import os
        import glob
        
        company_images_dir = os.path.join(os.getcwd(), 'images', 'company')
        if os.path.exists(company_images_dir):
            # 查找匹配的图片文件
            pattern = os.path.join(company_images_dir, f"{filename}.*")
            matching_files = glob.glob(pattern)
            if matching_files:
                # 获取第一个匹配的文件
                file_path = matching_files[0]
                file_name = os.path.basename(file_path)
                return f"https://api.dinq.io/images/company/{file_name}"
        
        return None

    def get_school_logo_url(self, school_name):
        """获取学校logo URL"""
        if not school_name:
            return None
        
        # 转换学校名为文件名格式（小写，空格转下划线）
        filename = school_name.lower().replace(' ', '_')
        
        # 检查当前目录下的 images/school 文件夹
        import os
        import glob
        
        school_images_dir = os.path.join(os.getcwd(), 'images', 'school')
        if os.path.exists(school_images_dir):
            # 查找匹配的图片文件
            pattern = os.path.join(school_images_dir, f"{filename}.*")
            matching_files = glob.glob(pattern)
            if matching_files:
                # 获取第一个匹配的文件
                file_path = matching_files[0]
                file_name = os.path.basename(file_path)
                return f"https://api.dinq.io/images/school/{file_name}"
        
        return None

    def process_linkedin_data(self, profile_data: Dict[str, Any], person_name: str, linkedin_url: str = "", linkedin_id: str = "") -> Dict[str, Any]:
        """
        Process LinkedIn profile data
        
        Args:
            profile_data: Raw LinkedIn profile data
            person_name: Person's name
            linkedin_url: LinkedIn profile URL
            linkedin_id: LinkedIn profile ID for caching
            
        Returns:
            Processed analysis result with only required fields
        """
        try:
            # Extract basic information - only return required fields
            result = {
                "linkedin_id": linkedin_id,
                "person_name": person_name,
                "linkedin_url": linkedin_url,
                "profile_data": {},
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"Successfully processed LinkedIn data for: {person_name}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing LinkedIn data for {person_name}: {e}")
            return {
                "linkedin_id": linkedin_id,
                "person_name": person_name,
                "linkedin_url": linkedin_url,
                "profile_data": {},
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }

    async def analyze(self, person_name: str, linkedin_url: str = None) -> Optional[Dict[str, Any]]:
        """
        Analyze LinkedIn profile
        
        Args:
            person_name: Name to analyze
            linkedin_url: Optional LinkedIn URL to use directly
            
        Returns:
            Analysis result or None
        """
        try:
            logger.info(f"Starting LinkedIn analysis for: {person_name}")
            
            # Step 1: Get LinkedIn URL (either provided or search)
            if linkedin_url:
                # Use provided LinkedIn URL directly
                logger.info(f"Using provided LinkedIn URL: {linkedin_url}")
                first_result = {"url": linkedin_url}
            else:
                # Search for LinkedIn URL
                linkedin_results = self.search_linkedin_url(person_name)
                
                if not linkedin_results:
                    logger.warning(f"LinkedIn URL not found for: {person_name}")
                    return None
                
                # Select first (most relevant) LinkedIn URL
                first_result = linkedin_results[0]
                linkedin_url = first_result["url"]
                logger.info(f"Selected LinkedIn URL: {linkedin_url}")
            
            # Generate LinkedIn ID for caching
            linkedin_id = self.generate_linkedin_id(person_name, linkedin_url)
            
            # Check cache if enabled
            if self.use_cache:
                logger.info(f"Checking cache for LinkedIn ID: {linkedin_id}...")
                cached_data = get_linkedin_from_cache(linkedin_id, self.cache_max_age_days, person_name)
                if cached_data:
                    logger.info(f"Found recent data in cache for LinkedIn ID: {linkedin_id}")

                    # Validate and complete cached data
                    logger.info("Validating and completing cached data...")
                    validated_data = self.validate_and_complete_cache(cached_data)

                    # Add flag indicating data is from cache
                    if isinstance(validated_data, dict):
                        validated_data['_from_cache'] = True

                    logger.info(f"LinkedIn analysis completed from cache for: {person_name}")
                    # Convert datetime objects to strings for JSON serialization before returning
                    validated_data = self.convert_datetime_for_json(validated_data)
                    return validated_data
                
            # Step 2: Get LinkedIn profile
            profile_data = self.get_linkedin_profile(linkedin_url)
            
            if not profile_data:
                logger.error(f"Failed to fetch LinkedIn profile for: {person_name}")
                return None
                
            # Step 3: Process and analyze profile data
            analysis_result = self.process_linkedin_data(profile_data, person_name, linkedin_url, linkedin_id)
            
            # Step 4: Generate AI analysis using independent services
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            # Prepare parallel execution tasks
            tasks = []
            
            def get_role_model_info(profile_data, person_name):
                """Get role model information thread function"""
                try:
                    from server.linkedin_analyzer.role_model_service import get_linkedin_role_model
                    role_model = get_linkedin_role_model(profile_data, person_name)
                    return ('role_model', role_model)
                except Exception as e:
                    logger.error(f"Error getting role model: {str(e)}")
                    return ('role_model', None)
            
            def get_money_analysis_info(profile_data, person_name):
                """Get money analysis information thread function"""
                try:
                    from server.linkedin_analyzer.money_service import get_linkedin_money_analysis
                    money_analysis = get_linkedin_money_analysis(profile_data, person_name)
                    return ('money_analysis', money_analysis)
                except Exception as e:
                    logger.error(f"Error getting money analysis: {str(e)}")
                    return ('money_analysis', None)
            
            def get_roast_info(profile_data, person_name):
                """Get roast information thread function"""
                try:
                    from server.linkedin_analyzer.roast_service import get_linkedin_roast
                    roast = get_linkedin_roast(profile_data, person_name)
                    return ('roast', roast)
                except Exception as e:
                    logger.error(f"Error getting roast: {str(e)}")
                    return ('roast', "No roast available")
            
            def get_industry_knowledge_info(profile_data, person_name):
                """Get industry knowledge information thread function"""
                try:
                    from server.linkedin_analyzer.industry_knowledge_service import get_linkedin_industry_knowledge
                    industry_knowledge = get_linkedin_industry_knowledge(profile_data, person_name)
                    return ('industry_knowledge', industry_knowledge)
                except Exception as e:
                    logger.error(f"Error getting industry knowledge: {str(e)}")
                    return ('industry_knowledge', [])
            
            def get_tools_technologies_info(profile_data, person_name):
                """Get tools and technologies information thread function"""
                try:
                    from server.linkedin_analyzer.tools_technologies_service import get_linkedin_tools_technologies
                    tools_technologies = get_linkedin_tools_technologies(profile_data, person_name)
                    return ('tools_technologies', tools_technologies)
                except Exception as e:
                    logger.error(f"Error getting tools and technologies: {str(e)}")
                    return ('tools_technologies', [])
            
            def get_interpersonal_skills_info(profile_data, person_name):
                """Get interpersonal skills information thread function"""
                try:
                    from server.linkedin_analyzer.interpersonal_skills_service import get_linkedin_interpersonal_skills
                    interpersonal_skills = get_linkedin_interpersonal_skills(profile_data, person_name)
                    return ('interpersonal_skills', interpersonal_skills)
                except Exception as e:
                    logger.error(f"Error getting interpersonal skills: {str(e)}")
                    return ('interpersonal_skills', [])
            
            def get_language_info(profile_data, person_name):
                """Get language information thread function"""
                try:
                    from server.linkedin_analyzer.language_service import get_linkedin_languages
                    languages = get_linkedin_languages(profile_data, person_name)
                    return ('language', languages)
                except Exception as e:
                    logger.error(f"Error getting languages: {str(e)}")
                    return ('language', [])
            
            def get_colleagues_view_info(profile_data, person_name):
                """Get colleagues view information thread function"""
                try:
                    from server.linkedin_analyzer.colleagues_view_service import get_linkedin_colleagues_view
                    colleagues_view = get_linkedin_colleagues_view(profile_data, person_name)
                    return ('colleagues_view', colleagues_view)
                except Exception as e:
                    logger.error(f"Error getting colleagues view: {str(e)}")
                    return ('colleagues_view', {"highlights": [], "areas_for_improvement": []})
            
            def get_career_info(profile_data, person_name):
                """Get career information thread function"""
                try:
                    from server.linkedin_analyzer.career_service import get_linkedin_career
                    career = get_linkedin_career(profile_data, person_name)
                    return ('career', career)
                except Exception as e:
                    logger.error(f"Error getting career: {str(e)}")
                    return ('career', {"future_development_potential": "", "development_advice": {"past_evaluation": "", "future_advice": ""}})
            
            def get_life_well_being_info(profile_data, person_name):
                """Get life and well-being information thread function"""
                try:
                    from server.linkedin_analyzer.life_well_being_service import get_linkedin_life_well_being
                    life_well_being = get_linkedin_life_well_being(profile_data, person_name)
                    return ('life_well_being', life_well_being)
                except Exception as e:
                    logger.error(f"Error getting life and well-being: {str(e)}")
                    return ('life_well_being', {"life_suggestion": "", "health": ""})
            
            # Add tasks for parallel execution
            tasks.append(('role_model', get_role_model_info, (profile_data, person_name)))
            tasks.append(('money_analysis', get_money_analysis_info, (profile_data, person_name)))
            tasks.append(('roast', get_roast_info, (profile_data, person_name)))
            tasks.append(('industry_knowledge', get_industry_knowledge_info, (profile_data, person_name)))
            tasks.append(('tools_technologies', get_tools_technologies_info, (profile_data, person_name)))
            tasks.append(('interpersonal_skills', get_interpersonal_skills_info, (profile_data, person_name)))
            tasks.append(('language', get_language_info, (profile_data, person_name)))
            tasks.append(('colleagues_view', get_colleagues_view_info, (profile_data, person_name)))
            tasks.append(('career', get_career_info, (profile_data, person_name)))
            tasks.append(('life_well_being', get_life_well_being_info, (profile_data, person_name)))
            
            # Execute tasks in parallel
            thread_results = {}
            with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
                future_to_task = {}
                for task_name, task_func, task_args in tasks:
                    future = executor.submit(task_func, *task_args)
                    future_to_task[future] = task_name
                
                for future in as_completed(future_to_task):
                    task_name = future_to_task[future]
                    try:
                        result_type, result_data = future.result()
                        thread_results[result_type] = result_data
                        logger.info(f"Completed {task_name} analysis")
                    except Exception as e:
                        logger.error(f"Task {task_name} generated an exception: {e}")
                        thread_results[task_name] = None
            
            # Extract personal tags
            personal_tags = self.extract_personal_tags(profile_data)

            # Generate AI summaries for work experience and education
            work_summary = self.generate_work_experience_summary(profile_data.get('experiences', []))
            education_summary = self.generate_education_summary(profile_data.get('educations', []))

            # Generate AI about section if missing
            about_content = profile_data.get("about")
            if not about_content or not about_content.strip():
                about_content = self.generate_ai_about_section(profile_data, person_name)

            # Add AI analysis results to profile_data (not as separate field)
            analysis_result["profile_data"].update({
                "role_model": thread_results.get('role_model'),
                "money_analysis": thread_results.get('money_analysis'),
                "roast": thread_results.get('roast'),
                "skills": {
                    "industry_knowledge": thread_results.get('industry_knowledge', []),
                    "tools_technologies": thread_results.get('tools_technologies', []),
                    "interpersonal_skills": thread_results.get('interpersonal_skills', []),
                    "language": thread_results.get('language', [])
                },
                "colleagues_view": thread_results.get('colleagues_view'),
                "career": thread_results.get('career'),
                "life_well_being": thread_results.get('life_well_being'),
                "about": about_content,
                "personal_tags": personal_tags,
                "work_experience": profile_data.get('experiences', []),
                "work_experience_summary": work_summary,
                "education": profile_data.get('educations', []),
                "education_summary": education_summary
            })
            
            # Process work experience and education with logo URLs
            import json
            try:
                # Process work experience - directly use original experiences data
                work_experience_data = profile_data.get('experiences', [])
                if work_experience_data:
                    analysis_result["profile_data"]["work_experience"] = work_experience_data
                
                # Process education - directly use original educations data
                education_data = profile_data.get('educations', [])
                if education_data:
                    analysis_result["profile_data"]["education"] = education_data
                
                # Process skills - combine original skills data with AI analysis
                original_skills = profile_data.get('skills', [])
                original_languages = profile_data.get('languages', [])
                
                # Extract skill names from original data
                original_skill_names = [skill.get('title', '') for skill in original_skills if skill.get('title')]
                original_language_names = [lang.get('title', '') for lang in original_languages if lang.get('title')]
                
                # Combine AI analysis with original data
                combined_skills = {
                    "industry_knowledge": thread_results.get('industry_knowledge', []),
                    "tools_technologies": thread_results.get('tools_technologies', []),
                    "interpersonal_skills": thread_results.get('interpersonal_skills', []),
                    "language": thread_results.get('language', [])
                }
                
                # Add original skills data
                if original_skills:
                    combined_skills["original_skills"] = original_skills
                if original_languages:
                    combined_skills["original_languages"] = original_languages
                
                analysis_result["profile_data"]["skills"] = combined_skills
                
            except Exception as e:
                logger.error(f"Error processing work experience and education data: {e}")

            # Add raw profile data for PK analysis


            # Cache the result if enabled
            if self.use_cache:
                # Convert datetime objects to strings for JSON serialization
                analysis_result = self.convert_datetime_for_json(analysis_result)
                cache_linkedin_data(analysis_result)

            logger.info(f"LinkedIn analysis completed for: {person_name}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in LinkedIn analysis for {person_name}: {e}")
            return None

    async def analyze_with_progress(self, person_name: str, progress_callback=None, linkedin_url: str = None, cancel_event=None) -> Optional[Dict[str, Any]]:
        """
        LinkedIn profile analysis with progress callback
        
        Args:
            person_name: Name to analyze
            progress_callback: Progress callback function
            linkedin_url: Optional LinkedIn URL to use directly
            
        Returns:
            Analysis result or None
        """
        from server.utils.trace_context import TraceContext, propagate_trace_to_thread

        # Get current trace ID
        current_trace_id = TraceContext.get_trace_id()

        def safe_progress_callback(step, message, data=None):
            """Safe progress callback, ensuring trace ID propagation"""
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                return
            if progress_callback:
                try:
                    # Ensure trace ID in callback
                    if current_trace_id:
                        TraceContext.set_trace_id(current_trace_id)
                    progress_callback(step, message, data)
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")

        try:
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                return None

            # Step 1: Get LinkedIn URL (either provided or search)
            if linkedin_url:
                # Use provided LinkedIn URL directly
                safe_progress_callback('url_provided', f'Starting LinkedIn profile analysis...')
                logger.info(f"Using provided LinkedIn URL: {linkedin_url}")
                first_result = {"url": linkedin_url}
            else:
                # Search for LinkedIn URL
                safe_progress_callback('searching', f'Searching for {person_name}\'s LinkedIn profile...')
                if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                    return None
                
                linkedin_results = self.search_linkedin_url(person_name)
                
                if not linkedin_results:
                    safe_progress_callback('not_found', f'No LinkedIn profile found for {person_name}')
                    logger.warning(f"LinkedIn URL not found for: {person_name}")
                    return None
                
                # Select first (most relevant) LinkedIn URL
                first_result = linkedin_results[0]
                linkedin_url = first_result["url"]
                logger.info(f"Selected LinkedIn URL: {linkedin_url}")
                
                safe_progress_callback('url_found', f'Found LinkedIn profile, getting detailed information...')
            
            # Generate LinkedIn ID for caching
            linkedin_id = self.generate_linkedin_id(person_name, linkedin_url)
                
            # Check cache if enabled
            if self.use_cache:
                safe_progress_callback('checking_cache', f'Checking for cached analysis results...')
                logger.info(f"Checking cache for LinkedIn ID: {linkedin_id}...")
                if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                    return None
                cached_data = get_linkedin_from_cache(linkedin_id, self.cache_max_age_days, person_name)
                if cached_data:
                    logger.info(f"Found recent data in cache for LinkedIn ID: {linkedin_id}")

                    # Validate and complete cached data
                    logger.info("Validating and completing cached data...")
                    safe_progress_callback('validating_cache', f'Validating cached data...')
                    validated_data = self.validate_and_complete_cache(cached_data, safe_progress_callback)

                    # Add flag indicating data is from cache
                    if isinstance(validated_data, dict):
                        validated_data['_from_cache'] = True

                    safe_progress_callback('complete', f'Analysis completed! (using cached data)')
                    logger.info(f"LinkedIn analysis completed from cache for: {person_name}")
                    # Convert datetime objects to strings for JSON serialization before returning
                    validated_data = self.convert_datetime_for_json(validated_data)
                    return validated_data
                
            # Step 2: Get LinkedIn profile
            safe_progress_callback('fetching', f'Fetching LinkedIn profile details...')
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                return None
            
            profile_data = self.get_linkedin_profile(linkedin_url)
            person_name = profile_data.get("fullName")
            if not profile_data:
                safe_progress_callback('fetch_failed', f'Failed to fetch profile, please check the URL')
                logger.error(f"Failed to fetch LinkedIn profile for: {person_name}")
                return None
                
            safe_progress_callback('fetch_success', f'Successfully fetched profile, starting analysis...')
                
            # Step 3: Process and analyze profile data
            safe_progress_callback('analyzing', f'Analyzing profile data...')
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                return None
            
            analysis_result = self.process_linkedin_data(profile_data, person_name, linkedin_url, linkedin_id)
            
            
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            # Prepare parallel execution tasks
            tasks = []
            
            def get_role_model_info(profile_data, person_name):
                """Get role model information thread function"""
                try:
                    from server.linkedin_analyzer.role_model_service import get_linkedin_role_model
                    role_model = get_linkedin_role_model(profile_data, person_name)
                    return ('role_model', role_model)
                except Exception as e:
                    logger.error(f"Error getting role model: {str(e)}")
                    return ('role_model', None)
            
            def get_money_analysis_info(profile_data, person_name):
                """Get money analysis information thread function"""
                try:
                    from server.linkedin_analyzer.money_service import get_linkedin_money_analysis
                    money_analysis = get_linkedin_money_analysis(profile_data, person_name)
                    return ('money_analysis', money_analysis)
                except Exception as e:
                    logger.error(f"Error getting money analysis: {str(e)}")
                    return ('money_analysis', None)
            
            def get_roast_info(profile_data, person_name):
                """Get roast information thread function"""
                try:
                    from server.linkedin_analyzer.roast_service import get_linkedin_roast
                    roast = get_linkedin_roast(profile_data, person_name)
                    return ('roast', roast)
                except Exception as e:
                    logger.error(f"Error getting roast: {str(e)}")
                    return ('roast', "No roast available")
            
            def get_industry_knowledge_info(profile_data, person_name):
                """Get industry knowledge information thread function"""
                try:
                    from server.linkedin_analyzer.industry_knowledge_service import get_linkedin_industry_knowledge
                    industry_knowledge = get_linkedin_industry_knowledge(profile_data, person_name)
                    return ('industry_knowledge', industry_knowledge)
                except Exception as e:
                    logger.error(f"Error getting industry knowledge: {str(e)}")
                    return ('industry_knowledge', [])
            
            def get_tools_technologies_info(profile_data, person_name):
                """Get tools and technologies information thread function"""
                try:
                    from server.linkedin_analyzer.tools_technologies_service import get_linkedin_tools_technologies
                    tools_technologies = get_linkedin_tools_technologies(profile_data, person_name)
                    return ('tools_technologies', tools_technologies)
                except Exception as e:
                    logger.error(f"Error getting tools and technologies: {str(e)}")
                    return ('tools_technologies', [])
            
            def get_interpersonal_skills_info(profile_data, person_name):
                """Get interpersonal skills information thread function"""
                try:
                    from server.linkedin_analyzer.interpersonal_skills_service import get_linkedin_interpersonal_skills
                    interpersonal_skills = get_linkedin_interpersonal_skills(profile_data, person_name)
                    return ('interpersonal_skills', interpersonal_skills)
                except Exception as e:
                    logger.error(f"Error getting interpersonal skills: {str(e)}")
                    return ('interpersonal_skills', [])
            
            def get_language_info(profile_data, person_name):
                """Get language information thread function"""
                try:
                    from server.linkedin_analyzer.language_service import get_linkedin_languages
                    languages = get_linkedin_languages(profile_data, person_name)
                    return ('language', languages)
                except Exception as e:
                    logger.error(f"Error getting languages: {str(e)}")
                    return ('language', [])
            
            def get_colleagues_view_info(profile_data, person_name):
                """Get colleagues view information thread function"""
                try:
                    from server.linkedin_analyzer.colleagues_view_service import get_linkedin_colleagues_view
                    colleagues_view = get_linkedin_colleagues_view(profile_data, person_name)
                    return ('colleagues_view', colleagues_view)
                except Exception as e:
                    logger.error(f"Error getting colleagues view: {str(e)}")
                    return ('colleagues_view', {"highlights": [], "areas_for_improvement": []})
            
            def get_career_info(profile_data, person_name):
                """Get career information thread function"""
                try:
                    from server.linkedin_analyzer.career_service import get_linkedin_career
                    career = get_linkedin_career(profile_data, person_name)
                    return ('career', career)
                except Exception as e:
                    logger.error(f"Error getting career: {str(e)}")
                    return ('career', {"future_development_potential": "", "development_advice": {"past_evaluation": "", "future_advice": ""}})
            
            def get_life_well_being_info(profile_data, person_name):
                """Get life and well-being information thread function"""
                try:
                    from server.linkedin_analyzer.life_well_being_service import get_linkedin_life_well_being
                    life_well_being = get_linkedin_life_well_being(profile_data, person_name)
                    return ('life_well_being', life_well_being)
                except Exception as e:
                    logger.error(f"Error getting life and well-being: {str(e)}")
                    return ('life_well_being', {"life_suggestion": "", "health": ""})
            
            # Add tasks for parallel execution
            tasks.append(('role_model', get_role_model_info, (profile_data, person_name)))
            tasks.append(('money_analysis', get_money_analysis_info, (profile_data, person_name)))
            tasks.append(('roast', get_roast_info, (profile_data, person_name)))
            tasks.append(('industry_knowledge', get_industry_knowledge_info, (profile_data, person_name)))
            tasks.append(('tools_technologies', get_tools_technologies_info, (profile_data, person_name)))
            tasks.append(('interpersonal_skills', get_interpersonal_skills_info, (profile_data, person_name)))
            tasks.append(('language', get_language_info, (profile_data, person_name)))
            tasks.append(('colleagues_view', get_colleagues_view_info, (profile_data, person_name)))
            tasks.append(('career', get_career_info, (profile_data, person_name)))
            tasks.append(('life_well_being', get_life_well_being_info, (profile_data, person_name)))
            
            # Execute tasks in parallel
            thread_results = {}
            with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
                future_to_task = {}
                for task_name, task_func, task_args in tasks:
                    future = executor.submit(task_func, *task_args)
                    future_to_task[future] = task_name
                
                for future in as_completed(future_to_task):
                    task_name = future_to_task[future]
                    try:
                        result_type, result_data = future.result()
                        thread_results[result_type] = result_data
                        
                        # 用户友好的进度消息
                        progress_messages = {
                            'role_model': 'Analyzing role model...',
                            'money_analysis': 'Evaluating salary level...',
                            'roast': 'Generating humorous evaluation...',
                            'industry_knowledge': 'Analyzing industry knowledge...',
                            'tools_technologies': 'Evaluating technical tools...',
                            'interpersonal_skills': 'Analyzing interpersonal skills...',
                            'language': 'Evaluating language skills...',
                            'colleagues_view': 'Simulating colleague perspective...',
                            'career': 'Analyzing career development...',
                            'life_well_being': 'Evaluating life health...'
                        }
                        
                        message = progress_messages.get(task_name, f'Completed {task_name} analysis...')
                        safe_progress_callback('ai_step_complete', message)
                        logger.info(f"Completed {task_name} analysis")
                    except Exception as e:
                        logger.error(f"Task {task_name} generated an exception: {e}")
                        thread_results[task_name] = None
            
            # Extract personal tags
            safe_progress_callback('extracting_tags', f'Extracting personal tags...')
            personal_tags = self.extract_personal_tags(profile_data)

            # Generate AI summaries for work experience and education
            safe_progress_callback('generating_summaries', f'Generating experience and education summaries...')
            work_summary = self.generate_work_experience_summary(profile_data.get('experiences', []))
            education_summary = self.generate_education_summary(profile_data.get('educations', []))

            # Generate AI about section if missing
            about_content = profile_data.get("about")
            if not about_content or not about_content.strip():
                safe_progress_callback('generating_about', f'Generating personal introduction...')
                about_content = self.generate_ai_about_section(profile_data, person_name)

            # Add AI analysis results to profile_data (not as separate field)
            analysis_result["profile_data"].update({
                "role_model": thread_results.get('role_model'),
                "money_analysis": thread_results.get('money_analysis'),
                "roast": thread_results.get('roast'),
                "skills": {
                    "industry_knowledge": thread_results.get('industry_knowledge', []),
                    "tools_technologies": thread_results.get('tools_technologies', []),
                    "interpersonal_skills": thread_results.get('interpersonal_skills', []),
                    "language": thread_results.get('language', [])
                },
                "colleagues_view": thread_results.get('colleagues_view'),
                "career": thread_results.get('career'),
                "life_well_being": thread_results.get('life_well_being'),
                "about": about_content,
                "personal_tags": personal_tags,
                "work_experience": profile_data.get('experiences', []),
                "work_experience_summary": work_summary,
                "education": profile_data.get('educations', []),
                "education_summary": education_summary,
                "avatar": profile_data.get("profilePic"),
                "name": profile_data.get("fullName"),
                "raw_profile": profile_data
            })
            
            # Process work experience and education with logo URLs
            import json
            try:
                # Process work experience - directly use original experiences data
                work_experience_data = profile_data.get('experiences', [])
                if work_experience_data:
                    analysis_result["profile_data"]["work_experience"] = work_experience_data
                
                # Process education - directly use original educations data
                education_data = profile_data.get('educations', [])
                if education_data:
                    analysis_result["profile_data"]["education"] = education_data
                
                # Process skills - combine original skills data with AI analysis
                original_skills = profile_data.get('skills', [])
                original_languages = profile_data.get('languages', [])
                
                # Extract skill names from original data
                original_skill_names = [skill.get('title', '') for skill in original_skills if skill.get('title')]
                original_language_names = [lang.get('title', '') for lang in original_languages if lang.get('title')]
                
                # Combine AI analysis with original data
                combined_skills = {
                    "industry_knowledge": thread_results.get('industry_knowledge', []),
                    "tools_technologies": thread_results.get('tools_technologies', []),
                    "interpersonal_skills": thread_results.get('interpersonal_skills', []),
                    "language": thread_results.get('language', [])
                }
                
                
                analysis_result["profile_data"]["skills"] = combined_skills
                
            except Exception as e:
                logger.error(f"Error processing work experience and education data: {e}")
            
            # Cache the result if enabled
            if self.use_cache:
                safe_progress_callback('caching', f'Saving analysis results to cache...')
                # Convert datetime objects to strings for JSON serialization
                analysis_result = self.convert_datetime_for_json(analysis_result)
                cache_linkedin_data(analysis_result)

            safe_progress_callback('complete', f'LinkedIn profile analysis completed!')
            
            logger.info(f"Successfully completed LinkedIn analysis with progress for {person_name}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Critical error during LinkedIn analysis with progress of {person_name}: {e}")
            safe_progress_callback('critical_error', f'An error occurred during analysis, please try again later')
            return None

    def get_cached_result(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Get cached LinkedIn analysis result only (no new analysis)

        Args:
            content: Person name or LinkedIn URL

        Returns:
            Cached analysis result or None
        """
        try:
            # Use existing cache logic from get_result method
            cache_key = content
            cached_data = get_linkedin_from_cache(cache_key, max_age_days=30)

            if cached_data:
                logger.info(f"Found cached LinkedIn result for: {content}")
                return cached_data
            else:
                logger.info(f"No cached LinkedIn result found for: {content}")
                return None

        except Exception as e:
            logger.error(f"Error getting cached LinkedIn result for {content}: {e}")
            return None

    def get_cached_pk_result(self, person1: str, person2: str) -> Optional[Dict[str, Any]]:
        """获取缓存的PK结果"""
        try:
            # 检查缓存文件
            pk_filename = f"linkedin_pk_{person1}_vs_{person2}.json"

            # 直接读取JSON文件内容
            reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports")
            pk_filepath = os.path.join(reports_dir, pk_filename)

            if os.path.exists(pk_filepath):
                try:
                    with open(pk_filepath, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                    logger.info(f"Retrieved cached PK result for {person1} vs {person2}")
                    return result
                except Exception as e:
                    logger.error(f"Error reading cached PK file: {e}")
                    return None
            else:
                logger.info(f"No cached PK result found for {person1} vs {person2}")
                return None

        except Exception as e:
            logger.error(f"Critical error in get_cached_pk_result for {person1} vs {person2}: {e}")
            return None

    def save_pk_report(self, pk_result: Dict) -> Dict[str, str]:
        """保存LinkedIn PK报告为JSON"""
        try:
            # 创建reports目录（如果不存在）
            reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports")
            os.makedirs(reports_dir, exist_ok=True)

            # 获取用户名
            user1_name = pk_result.get('user1', {}).get('linkedin_id', 'unknown1')
            user2_name = pk_result.get('user2', {}).get('linkedin_id', 'unknown2')

            # 生成文件名
            pk_filename = f"linkedin_pk_{user1_name}_vs_{user2_name}.json"
            pk_filepath = os.path.join(reports_dir, pk_filename)

            # 保存PK结果
            with open(pk_filepath, 'w', encoding='utf-8') as f:
                json.dump(pk_result, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved LinkedIn PK report: {pk_filename}")
            return {"pk_report_path": pk_filepath}

        except Exception as e:
            logger.error(f"Error saving LinkedIn PK report: {e}")
            return {}

    def get_result(self, person_name: str, linkedin_url: str = None) -> Optional[Dict[str, Any]]:
        """
        Get LinkedIn analysis result (synchronous version)

        Args:
            person_name: Name to analyze
            linkedin_url: Optional LinkedIn URL to use directly

        Returns:
            Analysis result or None
        """
        try:
            # Create new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(self.analyze(person_name, linkedin_url))
                return result
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Error getting LinkedIn result for {person_name}: {e}")
            return None

    def get_result_with_progress(self, person_name: str, progress_callback=None, linkedin_url: str = None, cancel_event=None) -> Optional[Dict[str, Any]]:
        """
        Get LinkedIn analysis result (synchronous version with progress callback)
        
        Args:
            person_name: Name to analyze
            progress_callback: Progress callback function
            linkedin_url: Optional LinkedIn URL to use directly
            
        Returns:
            Analysis result or None
        """
        try:
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                return None

            # Create new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    self.analyze_with_progress(
                        person_name,
                        progress_callback,
                        linkedin_url,
                        cancel_event=cancel_event,
                    )
                )
                return result
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error getting LinkedIn result with progress for {person_name}: {e}")
            return None

    def extract_personal_tags(self, profile_data: Dict[str, Any]) -> List[str]:
        """
        Extract 4-5 most relevant personal tags from LinkedIn profile data.

        Args:
            profile_data: LinkedIn profile data

        Returns:
            List of 4-5 personal tags
        """
        try:
            tags = []

            # 1. Extract from top skills (highest priority)
            top_skills = profile_data.get('topSkillsByEndorsements', '')
            if top_skills:
                # Get first 2 top skills
                skill_list = [skill.strip() for skill in top_skills.split(',')]
                tags.extend(skill_list[:2])

            # 2. Extract from headline (professional identity)
            headline = profile_data.get('headline', '')
            if headline:
                # Extract key role identifiers
                role_keywords = ['Manager', 'Director', 'Lead', 'Engineer', 'Developer', 'Designer',
                               'Analyst', 'Consultant', 'Specialist', 'Expert', 'Writer', 'Creator']
                for keyword in role_keywords:
                    if keyword.lower() in headline.lower() and keyword not in tags:
                        tags.append(keyword)
                        break

            # 3. Extract from industry/company info
            industry = profile_data.get('companyIndustry', '')
            if industry and len(tags) < 4:
                # Simplify industry names
                industry_mapping = {
                    'Marketing And Advertising': 'Marketing',
                    'Information Technology': 'Technology',
                    'Computer Software': 'Software',
                    'Financial Services': 'Finance',
                    'Health Care': 'Healthcare',
                    'Education': 'Education',
                    'Consulting': 'Consulting'
                }
                simplified_industry = industry_mapping.get(industry, industry.split(' ')[0])
                if simplified_industry not in tags:
                    tags.append(simplified_industry)

            # 4. Extract from about section hashtags
            about = profile_data.get('about', '')
            if about and len(tags) < 4:
                import re
                hashtags = re.findall(r'#(\w+)', about)
                for hashtag in hashtags[:2]:  # Take first 2 hashtags
                    if hashtag not in tags and len(tags) < 5:
                        tags.append(hashtag)

            # 5. Extract from current job title if still need more tags
            if len(tags) < 4:
                experiences = profile_data.get('experiences', [])
                if experiences:
                    current_title = experiences[0].get('title', '')
                    if current_title:
                        # Extract meaningful words from job title
                        title_words = current_title.split()
                        meaningful_words = [word for word in title_words
                                          if len(word) > 3 and word.lower() not in ['and', 'the', 'for', 'with']]
                        for word in meaningful_words[:1]:  # Take first meaningful word
                            if word not in tags and len(tags) < 5:
                                tags.append(word)

            # 6. Fallback: extract from skills if still need more
            if len(tags) < 4:
                skills = profile_data.get('skills', [])
                for skill in skills[:10]:  # Check first 10 skills
                    skill_title = skill.get('title', '')
                    if skill_title and skill_title not in tags and len(tags) < 5:
                        tags.append(skill_title)
                        if len(tags) >= 5:
                            break

            # Clean and limit tags
            cleaned_tags = []
            for tag in tags[:5]:  # Limit to 5 tags
                # Clean tag: remove special characters, capitalize first letter
                clean_tag = ''.join(c for c in tag if c.isalnum() or c.isspace()).strip()
                if clean_tag and len(clean_tag) > 2:
                    # Capitalize first letter of each word
                    clean_tag = ' '.join(word.capitalize() for word in clean_tag.split())
                    if clean_tag not in cleaned_tags:
                        cleaned_tags.append(clean_tag)

            # Ensure we have 4-5 tags, add defaults if needed
            if len(cleaned_tags) < 4:
                default_tags = ['Professional', 'Experienced', 'Skilled', 'Dedicated']
                for default_tag in default_tags:
                    if default_tag not in cleaned_tags and len(cleaned_tags) < 4:
                        cleaned_tags.append(default_tag)

            logger.info(f"Extracted personal tags: {cleaned_tags}")
            return cleaned_tags[:5]  # Return maximum 5 tags

        except Exception as e:
            logger.error(f"Error extracting personal tags: {e}")
            # Return default tags in case of error
            return ['Professional', 'Experienced', 'Skilled', 'Dedicated']

    def generate_work_experience_summary(self, experiences: List[Dict[str, Any]]) -> str:
        """
        Generate AI summary of work experience.

        Args:
            experiences: List of work experience entries

        Returns:
            AI-generated summary of work experience
        """
        try:
            if not experiences:
                return "No work experience information available."

            # Build experience summary for AI
            experience_text = ""
            for i, exp in enumerate(experiences[:10], 1):  # Limit to 10 most recent
                title = exp.get('title', 'Unknown Position')
                company = exp.get('subtitle', '').split('·')[0].strip() if exp.get('subtitle') else 'Unknown Company'
                duration = exp.get('caption', '')
                location = exp.get('metadata', '')

                experience_text += f"{i}. {title} at {company}"
                if duration:
                    experience_text += f" ({duration})"
                if location:
                    experience_text += f" - {location}"
                experience_text += "\n"

            # Generate AI summary
            summary_prompt = f"""
            Based on the following work experience, provide a concise professional summary (40-60 words) that highlights:
            1. Career progression and growth
            2. Key industries and roles
            3. Professional expertise developed
            4. Overall career trajectory

            Work Experience:
            {experience_text}

            Provide a professional summary that captures the essence of this career journey in 40-60 words. Focus on progression, expertise, and professional development.

            Return only the summary text, no additional formatting.
            """

            summary = openrouter_chat(
                task="linkedin_work_summary",
                messages=[{"role": "user", "content": summary_prompt}],
                model=get_model("fast", task="linkedin_work_summary"),
                temperature=0.3,
                max_tokens=150,
            )
            if summary:
                logger.info(f"Generated work experience summary: {str(summary)[:50]}...")
                return summary
            return self.create_default_work_summary(experiences)

        except Exception as e:
            logger.error(f"Error generating work experience summary: {e}")
            return self.create_default_work_summary(experiences)

    def create_default_work_summary(self, experiences: List[Dict[str, Any]]) -> str:
        """Create default work experience summary."""
        try:
            if not experiences:
                return "No work experience information available."

            # Extract key information
            total_positions = len(experiences)
            companies = set()
            roles = []

            for exp in experiences[:5]:  # Look at recent 5
                if exp.get('subtitle'):
                    company = exp.get('subtitle', '').split('·')[0].strip()
                    if company:
                        companies.add(company)

                if exp.get('title'):
                    roles.append(exp.get('title'))

            # Build summary
            summary_parts = []

            if total_positions > 1:
                summary_parts.append(f"Progressive career with {total_positions} professional positions")

            if companies:
                if len(companies) > 3:
                    summary_parts.append("across multiple organizations")
                else:
                    summary_parts.append(f"at companies including {', '.join(list(companies)[:2])}")

            if roles:
                # Identify common role patterns
                if any('manager' in role.lower() for role in roles):
                    summary_parts.append("with management and leadership experience")
                elif any('senior' in role.lower() for role in roles):
                    summary_parts.append("demonstrating senior-level expertise")
                else:
                    summary_parts.append("building specialized professional skills")

            summary = '. '.join(summary_parts) + '.'
            return summary if len(summary) > 20 else "Experienced professional with diverse background across multiple roles and organizations."

        except Exception as e:
            logger.error(f"Error creating default work summary: {e}")
            return "Experienced professional with diverse background."

    def generate_education_summary(self, educations: List[Dict[str, Any]]) -> str:
        """
        Generate AI summary of education background.

        Args:
            educations: List of education entries

        Returns:
            AI-generated summary of education background
        """
        try:
            if not educations:
                return "No education information available."

            # Build education summary for AI
            education_text = ""
            for i, edu in enumerate(educations, 1):
                institution = edu.get('title', 'Unknown Institution')
                degree = edu.get('subtitle', '')
                duration = edu.get('caption', '')

                education_text += f"{i}. {institution}"
                if degree:
                    education_text += f" - {degree}"
                if duration:
                    education_text += f" ({duration})"
                education_text += "\n"

            # Generate AI summary
            summary_prompt = f"""
            Based on the following education background, provide a concise academic summary (30-50 words) that highlights:
            1. Educational level and qualifications
            2. Fields of study and specialization
            3. Academic institutions attended
            4. Overall educational foundation

            Education Background:
            {education_text}

            Provide an academic summary that captures the educational foundation in 30-50 words. Focus on qualifications, specialization, and academic preparation.

            Return only the summary text, no additional formatting.
            """

            summary = openrouter_chat(
                task="linkedin_education_summary",
                messages=[{"role": "user", "content": summary_prompt}],
                model=get_model("fast", task="linkedin_education_summary"),
                temperature=0.3,
                max_tokens=120,
            )
            if summary:
                logger.info(f"Generated education summary: {str(summary)[:50]}...")
                return summary
            return self.create_default_education_summary(educations)

        except Exception as e:
            logger.error(f"Error generating education summary: {e}")
            return self.create_default_education_summary(educations)

    def create_default_education_summary(self, educations: List[Dict[str, Any]]) -> str:
        """Create default education summary."""
        try:
            if not educations:
                return "No education information available."

            # Extract key information
            degrees = []
            institutions = []

            for edu in educations:
                if edu.get('subtitle'):
                    degree_info = edu.get('subtitle', '')
                    degrees.append(degree_info)

                if edu.get('title'):
                    institutions.append(edu.get('title'))

            # Build summary
            summary_parts = []

            # Analyze degree levels
            has_masters = any('master' in deg.lower() or 'mba' in deg.lower() for deg in degrees)
            has_bachelors = any('bachelor' in deg.lower() for deg in degrees)
            has_phd = any('phd' in deg.lower() or 'doctorate' in deg.lower() for deg in degrees)

            if has_phd:
                summary_parts.append("Advanced doctoral-level education")
            elif has_masters:
                summary_parts.append("Graduate-level education with master's degree")
            elif has_bachelors:
                summary_parts.append("University-level education with bachelor's degree")
            else:
                summary_parts.append("Formal education background")

            # Add field information if available
            business_fields = ['business', 'mba', 'management', 'marketing', 'finance']
            tech_fields = ['computer', 'engineering', 'technology', 'science']

            degree_text = ' '.join(degrees).lower()
            if any(field in degree_text for field in business_fields):
                summary_parts.append("in business and management")
            elif any(field in degree_text for field in tech_fields):
                summary_parts.append("in technology and engineering")

            # Add institution info
            if institutions:
                if len(institutions) > 1:
                    summary_parts.append("from multiple institutions")
                else:
                    summary_parts.append(f"from {institutions[0]}")

            summary = ' '.join(summary_parts) + '.'
            return summary if len(summary) > 20 else "Solid educational foundation with formal qualifications."

        except Exception as e:
            logger.error(f"Error creating default education summary: {e}")
            return "Educational background with formal qualifications."

    def generate_ai_about_section(self, profile_data: Dict[str, Any], person_name: str) -> str:
        """
        Generate AI-powered about section when missing.

        Args:
            profile_data: LinkedIn profile data
            person_name: Person's name

        Returns:
            AI-generated about section (max 50 words)
        """
        try:
            # Extract key information for AI generation
            headline = profile_data.get('headline', '')
            experiences = profile_data.get('experiences', [])
            skills = profile_data.get('skills', [])
            education = profile_data.get('educations', [])
            company_name = profile_data.get('companyName', '')
            industry = profile_data.get('companyIndustry', '')

            # Build context for AI
            context_parts = []

            if headline:
                context_parts.append(f"Current role: {headline}")

            if company_name:
                context_parts.append(f"Company: {company_name}")

            if industry:
                context_parts.append(f"Industry: {industry}")

            # Add recent experience
            if experiences:
                recent_exp = experiences[0]
                exp_title = recent_exp.get('title', '')
                exp_company = recent_exp.get('subtitle', '').split('·')[0].strip() if recent_exp.get('subtitle') else ''
                if exp_title:
                    context_parts.append(f"Experience: {exp_title}")
                    if exp_company and exp_company != company_name:
                        context_parts.append(f"at {exp_company}")

            # Add key skills
            if skills:
                skill_names = [skill.get('title', '') for skill in skills[:3] if skill.get('title')]
                if skill_names:
                    context_parts.append(f"Skills: {', '.join(skill_names)}")

            # Add education
            if education:
                edu = education[0]
                edu_degree = edu.get('subtitle', '')
                edu_school = edu.get('title', '')
                if edu_degree:
                    context_parts.append(f"Education: {edu_degree}")
                    if edu_school:
                        context_parts.append(f"from {edu_school}")

            context_text = '. '.join(context_parts)

            # Generate AI about section
            about_prompt = f"""
            Based on the following professional profile information, write a brief personal introduction (maximum 50 words) that sounds natural and professional.

            Profile Information:
            {context_text}

            Write a first-person introduction that:
            1. Highlights their professional expertise and current role
            2. Mentions key skills or industry focus
            3. Sounds engaging and authentic
            4. Is exactly 50 words or less
            5. Uses a professional but friendly tone

            Examples of good introductions:
            - "Passionate marketing professional with expertise in digital strategy and brand development. Currently leading social media initiatives at a growing agency, helping brands connect with their audiences through creative campaigns and data-driven insights."
            - "Experienced software engineer specializing in full-stack development and cloud technologies. I enjoy building scalable applications and mentoring junior developers while staying current with emerging tech trends."

            Return only the introduction text, no additional formatting or quotes.
            """

            about_text = openrouter_chat(
                task="linkedin_about",
                messages=[{"role": "user", "content": about_prompt}],
                model=get_model("fast", task="linkedin_about"),
                temperature=0.7,
                max_tokens=100,
            )
            if not about_text:
                return self.create_default_about_section(profile_data, person_name)

            about_text = str(about_text).strip()
            words = about_text.split()
            if len(words) > 50:
                about_text = ' '.join(words[:50]) + '...'
            logger.info(f"Generated AI about section: {about_text[:50]}...")
            return about_text

        except Exception as e:
            logger.error(f"Error generating AI about section: {e}")
            return self.create_default_about_section(profile_data, person_name)

    def create_default_about_section(self, profile_data: Dict[str, Any], person_name: str) -> str:
        """
        Create default about section when AI generation fails.

        Args:
            profile_data: LinkedIn profile data
            person_name: Person's name

        Returns:
            Default about section
        """
        try:
            headline = profile_data.get('headline', '')
            company_name = profile_data.get('companyName', '')
            industry = profile_data.get('companyIndustry', '')

            # Build default about section
            about_parts = []

            if headline:
                # Extract main role from headline
                main_role = headline.split('|')[0].strip() if '|' in headline else headline
                about_parts.append(f"Experienced {main_role.lower()}")
            else:
                about_parts.append("Experienced professional")

            if industry:
                about_parts.append(f"in the {industry.lower()} industry")

            if company_name:
                about_parts.append(f"currently working at {company_name}")

            # Add skills if available
            skills = profile_data.get('skills', [])
            if skills:
                skill_names = [skill.get('title', '') for skill in skills[:2] if skill.get('title')]
                if skill_names:
                    about_parts.append(f"with expertise in {' and '.join(skill_names).lower()}")

            about_parts.append("Passionate about delivering excellent results and continuous professional growth.")

            about_text = ' '.join(about_parts)

            # Ensure reasonable length
            if len(about_text) > 250:
                about_text = about_text[:247] + '...'

            return about_text

        except Exception as e:
            logger.error(f"Error creating default about section: {e}")
            return f"Professional with diverse experience and expertise. Committed to excellence and continuous learning in their field."


    def transform_linkedin_pk_result(self, person1_name: str, person2_name: str, result1: Dict[str, Any], result2: Dict[str, Any]) -> Dict[str, Any]:
        """Transform LinkedIn analysis results into PK format"""
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def extract_pk_data(person_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
                """Extract PK-relevant data from LinkedIn analysis result"""
                profile_data = result.get("profile_data", {})
                linkedin_id = result.get("linkedin_id", {})

                # 从原始LinkedIn profile中获取技能和兴趣数据
                raw_profile = profile_data.get("raw_profile", {})

                # 准备用于打分的数据
                user_data = {
                    "education": profile_data.get("education", []),
                    "work_experience": profile_data.get("work_experience", []),
                    "network": {"connections": raw_profile.get("connections",0) , "followers": raw_profile.get("followers",0)},
                    "skills": profile_data.get("skills",[]),
                    "interests": raw_profile.get("interests",[])
                }

                # 生成AI打分
                dimension_scores = self._generate_dimension_scores(user_data)

                return {
                    "name": result.get("person_name", person_name),
                    "linkedin_id":  linkedin_id,
                    "avater": profile_data.get("avatar", ""),
                    "personal_tags": profile_data.get("personal_tags", []),
                    "education": profile_data.get("education", []),
                    "work_experience": profile_data.get("work_experience", []),
                    "network": {"connections": raw_profile.get("connections",0) , "followers": raw_profile.get("followers",0)},
                    "skills": profile_data.get("skills",[]),
                    "interests": raw_profile.get("interests",[]),
                    "scores": dimension_scores  # 添加AI打分
                }

            # Prepare parallel tasks for both users and roast generation
            tasks = []

            def extract_user1_data():
                """Extract user1 data with scoring"""
                try:
                    return ('user1', extract_pk_data(person1_name, result1))
                except Exception as e:
                    logger.error(f"Error extracting user1 data: {e}")
                    return ('user1', {"name": person1_name, "scores": self._get_default_scores()})

            def extract_user2_data():
                """Extract user2 data with scoring"""
                try:
                    return ('user2', extract_pk_data(person2_name, result2))
                except Exception as e:
                    logger.error(f"Error extracting user2 data: {e}")
                    return ('user2', {"name": person2_name, "scores": self._get_default_scores()})

            def generate_roast():
                """Generate PK roast"""
                try:
                    roast = self._generate_linkedin_pk_roast(result1, result2)
                    return ('roast', roast)
                except Exception as e:
                    logger.error(f"Error generating PK roast: {e}")
                    return ('roast', "Failed to generate roast")

            # Add tasks for parallel execution
            tasks.append(('user1', extract_user1_data, ()))
            tasks.append(('user2', extract_user2_data, ()))
            tasks.append(('roast', generate_roast, ()))

            # Execute tasks in parallel
            thread_results = {}
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_task = {}
                for task_name, task_func, task_args in tasks:
                    future = executor.submit(task_func, *task_args)
                    future_to_task[future] = task_name

                for future in as_completed(future_to_task):
                    task_name = future_to_task[future]
                    try:
                        result_type, result_data = future.result()
                        thread_results[result_type] = result_data
                        logger.info(f"Completed PK task: {result_type}")
                    except Exception as e:
                        logger.error(f"Error in PK task {task_name}: {e}")
                        if result_type == 'roast':
                            thread_results[result_type] = "Failed to generate roast"
                        else:
                            thread_results[result_type] = {"name": f"Unknown {result_type}", "scores": self._get_default_scores()}

            return {
                "user1": thread_results.get("user1", {"name": person1_name, "scores": self._get_default_scores()}),
                "user2": thread_results.get("user2", {"name": person2_name, "scores": self._get_default_scores()}),
                "roast": thread_results.get("roast", "Failed to generate roast")
            }

        except Exception as e:
            logger.error(f"Error transforming LinkedIn PK result: {e}")
            return {}

    def _generate_dimension_scores(self, user_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Generate AI scores for each dimension using OpenRouter with parallel execution"""
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            # Prepare parallel execution tasks
            tasks = []

            def score_education_thread(user_data):
                """Score education dimension thread function"""
                try:
                    result = self._score_education(user_data)
                    return ('education', result)
                except Exception as e:
                    logger.error(f"Error in education scoring thread: {e}")
                    return ('education', {"score": 50, "description": "Unable to analyze education"})

            def score_work_experience_thread(user_data):
                """Score work experience dimension thread function"""
                try:
                    result = self._score_work_experience(user_data)
                    return ('work_experience', result)
                except Exception as e:
                    logger.error(f"Error in work experience scoring thread: {e}")
                    return ('work_experience', {"score": 50, "description": "Unable to analyze work experience"})

            def score_network_thread(user_data):
                """Score network dimension thread function"""
                try:
                    result = self._score_network(user_data)
                    return ('network', result)
                except Exception as e:
                    logger.error(f"Error in network scoring thread: {e}")
                    return ('network', {"score": 50, "description": "Unable to analyze network"})

            def score_ai_native_thread(user_data):
                """Score AI-Native dimension thread function"""
                try:
                    result = self._score_ai_native(user_data)
                    return ('ai_native', result)
                except Exception as e:
                    logger.error(f"Error in AI-native scoring thread: {e}")
                    return ('ai_native', {"score": 50, "description": "Unable to analyze AI level"})

            def score_work_life_balance_thread(user_data):
                """Score work-life balance dimension thread function"""
                try:
                    result = self._score_work_life_balance(user_data)
                    return ('work_life_balance', result)
                except Exception as e:
                    logger.error(f"Error in work-life balance scoring thread: {e}")
                    return ('work_life_balance', {"score": 50, "description": "Unable to analyze work-life balance"})

            # Add all scoring tasks
            tasks.append(('education', score_education_thread, (user_data,)))
            tasks.append(('work_experience', score_work_experience_thread, (user_data,)))
            tasks.append(('network', score_network_thread, (user_data,)))
            tasks.append(('ai_native', score_ai_native_thread, (user_data,)))
            tasks.append(('work_life_balance', score_work_life_balance_thread, (user_data,)))

            # Execute tasks in parallel
            thread_results = {}
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_task = {}
                for task_name, task_func, task_args in tasks:
                    future = executor.submit(task_func, *task_args)
                    future_to_task[future] = task_name

                for future in as_completed(future_to_task):
                    task_name = future_to_task[future]
                    try:
                        result_type, result_data = future.result()
                        thread_results[result_type] = result_data
                        logger.info(f"Completed scoring for dimension: {result_type}")
                    except Exception as e:
                        logger.error(f"Error in scoring task {task_name}: {e}")
                        thread_results[result_type] = {"score": 50, "description": f"Unable to analyze {result_type}"}

            return thread_results

        except Exception as e:
            logger.error(f"Error generating dimension scores: {e}")
            return self._get_default_scores()

    def _call_kimi_api(self, prompt: str) -> str:
        """Call LLM with given prompt (speed-first)."""
        try:
            content = openrouter_chat(
                task="linkedin.dimension_scores",
                model=get_model("fast", task="linkedin.dimension_scores"),
                messages=[
                    {"role": "system", "content": "You are an expert career analyst. Provide objective scores and descriptions based on the data provided."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            return str(content or "")

        except Exception as e:
            logger.error(f"Error calling Kimi API: {e}")
            return ""

    def _score_education(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Score education dimension"""
        import json

        education_data = user_data.get("education", [])

        prompt = f"""
Analyze the education background and provide a score (0-100) and description.

Education Data: {json.dumps(education_data, ensure_ascii=False)}

Consider:
- University prestige and ranking
- Degree level (PhD > Master > Bachelor)
- Field relevance to career
- Academic achievements

Return ONLY a JSON object (description must be 10 words or less):
{{"score": 85, "description": "Strong educational background from prestigious institutions"}}
"""

        response = self._call_kimi_api(prompt)
        try:
            return json.loads(response)
        except:
            return {"score": 50, "description": "Unable to analyze education"}

    def _score_work_experience(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Score work experience dimension"""
        import json

        work_data = user_data.get("work_experience", [])

        prompt = f"""
Analyze the work experience and provide a score (0-100) and description.

Work Experience Data: {json.dumps(work_data, ensure_ascii=False)}

Consider:
- Company prestige and size
- Career progression and growth
- Role responsibilities and achievements
- Industry leadership
- Years of experience

Return ONLY a JSON object (description must be 10 words or less):
{{"score": 90, "description": "Impressive career progression at top companies"}}
"""

        response = self._call_kimi_api(prompt)
        try:
            return json.loads(response)
        except:
            return {"score": 50, "description": "Unable to analyze work experience"}

    def _score_network(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Score network dimension"""
        import json

        network_data = user_data.get("network", {})

        prompt = f"""
Analyze the professional network and provide a score (0-100) and description.

Network Data: {json.dumps(network_data, ensure_ascii=False)}

Consider:
- Number of connections (quality over quantity)
- Number of followers
- Professional influence and reach
- Industry networking

Return ONLY a JSON object (description must be 10 words or less):
{{"score": 75, "description": "Good professional network with solid connections"}}
"""

        response = self._call_kimi_api(prompt)
        try:
            return json.loads(response)
        except:
            return {"score": 50, "description": "Unable to analyze network"}

    def _score_ai_native(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Score AI-Native dimension"""
        import json

        skills_data = user_data.get("skills", [])
        work_data = user_data.get("work_experience", [])

        prompt = f"""
Analyze the AI-Native level and provide a score (0-100) and description.

Skills Data: {json.dumps(skills_data, ensure_ascii=False)}
Work Experience: {json.dumps(work_data, ensure_ascii=False)}

Consider:
- AI/ML related skills and technologies
- Experience with AI companies or projects
- Technical depth in AI/ML
- Understanding of AI trends and applications

Return ONLY a JSON object (description must be 10 words or less):
{{"score": 60, "description": "Some AI exposure but not deeply technical"}}
"""

        response = self._call_kimi_api(prompt)
        try:
            return json.loads(response)
        except:
            return {"score": 50, "description": "Unable to analyze AI level"}

    def _score_work_life_balance(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Score work-life balance dimension"""
        import json

        interests_data = user_data.get("interests", [])

        prompt = f"""
Analyze the work-life balance and provide a score (0-100) and description.

Interests Data: {json.dumps(interests_data, ensure_ascii=False)}

Consider:
- Diversity of personal interests outside work
- Hobbies and recreational activities
- Volunteer work and community involvement
- Balance between professional and personal life

Return ONLY a JSON object (description must be 10 words or less):
{{"score": 80, "description": "Well-balanced with diverse interests outside work"}}
"""

        response = self._call_kimi_api(prompt)
        try:
            return json.loads(response)
        except:
            return {"score": 50, "description": "Unable to analyze work-life balance"}

    def _get_default_scores(self) -> Dict[str, Dict[str, Any]]:
        """Return default scores when AI scoring fails"""
        return {
            "education": {"score": 50, "description": "Unable to analyze education"},
            "work_experience": {"score": 50, "description": "Unable to analyze work experience"},
            "network": {"score": 50, "description": "Unable to analyze network"},
            "ai_native": {"score": 50, "description": "Unable to analyze AI level"},
            "work_life_balance": {"score": 50, "description": "Unable to analyze work-life balance"}
        }

    def _generate_linkedin_pk_roast(self, user1_info: Dict[str, Any], user2_info: Dict[str, Any]) -> str:
        """Generate a roast comparing two LinkedIn profiles"""
        try:
            import json
            from server.prompts.github_prompts import get_linkedin_pk_roast_prompt

            # Format user information for roast generation
            # Truncate to max 5000 characters each to avoid token limit issues
            max_chars = 5000
            user1_str = json.dumps(user1_info, ensure_ascii=False)
            user2_str = json.dumps(user2_info, ensure_ascii=False)

            if len(user1_str) > max_chars:
                logger.info(f"Truncating user1 info from {len(user1_str)} to {max_chars} chars")
                user1_str = user1_str[:max_chars]
            if len(user2_str) > max_chars:
                logger.info(f"Truncating user2 info from {len(user2_str)} to {max_chars} chars")
                user2_str = user2_str[:max_chars]

            # Get LinkedIn-specific prompt
            messages = get_linkedin_pk_roast_prompt(user1_str, user2_str)

            model = get_model("fast", task="linkedin_pk.roast")
            response = openrouter_chat(
                task="linkedin_pk.roast",
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=300,
                expect_json=True,
            )
            if isinstance(response, dict) and response.get("roast"):
                return str(response.get("roast") or "").strip()
            if isinstance(response, str) and response.strip():
                return response.strip()
            return "Failed to generate roast"

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in LinkedIn roast generation: {e}")
            return "Failed to generate roast due to JSON parsing error"
        except Exception as e:
            logger.error(f"Error generating LinkedIn roast: {e}")
            return f"Failed to generate roast: {str(e)}"

    def close(self):
        """Close analyzer"""
        logger.info("LinkedIn analyzer closed")
