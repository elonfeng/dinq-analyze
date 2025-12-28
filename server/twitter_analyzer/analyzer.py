"""
Twitter Profile Analyzer

This module provides functionality to analyze Twitter/X user profiles using Apify API.
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
try:
    from apify_client import ApifyClient
except Exception:  # noqa: BLE001
    ApifyClient = None

# Configure logging
logger = logging.getLogger(__name__)

class TwitterAnalyzer:
    """Analyzer for Twitter/X user profiles using Apify API"""
    
    def __init__(self):
        """Initialize the Twitter analyzer"""

        api_key = os.getenv("APIFY_API_KEY", "")
        if ApifyClient is None or not api_key:
            self.client = None
        else:
            self.client = ApifyClient(api_key)
        logger.info("TwitterAnalyzer initialized")
    
    def analyze_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a Twitter user profile using Apify API
        
        Args:
            username: Twitter username (without @)
            
        Returns:
            Dictionary containing profile analysis or None if failed
        """
        try:
            logger.info(f"Starting analysis for Twitter user: {username}")
            
            if not self.client:
                logger.error("Apify client not initialized - missing API token")
                return None
            
            # Single Apify run: fetch user (if provided) and followers in one call
            followers_data,followings = self._fetch_user_and_followers(username)
            if followers_data is None:
                followers_data = []
            
            # Analyze followers
            top_followers = self._get_top_followers(followers_data)
            verified_followers = self._count_verified_followers(followers_data)
            # Trends not available reliably from this feed, skip for now

            summary = self.sum_generation(username)
            # Build profile data
            analysis_result = {
                "username": username,
                "followers_count": len(followers_data),
                "followings_count": len(followings),
                "verified_followers_count": verified_followers,
                "top_followers": top_followers,
                "summary": summary
            }
            
            logger.info(f"Analysis completed for {username}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing profile for {username}: {e}")
            return None

    def sum_generation(self,name) -> str:
        from server.llm.gateway import openrouter_chat
        from server.config.llm_models import get_model

        # Create a prompt for tag generation
        prompt = f"""Generate a 20-word summary of user's tweet content categories and communication style (e.g., technical insights, industry commentary). 
        Output no more than 20 words. user is {name}"""

        try:
            summary = openrouter_chat(
                task="twitter.summary",
                model=get_model("fast", task="twitter.summary"),
                messages=[
                    {"role": "system", "content": "you are an helpful assistant"},
                    {"role": "user", "content": f"{prompt}"},
                ],
                temperature=0.7,
                max_tokens=80,
            )
            return str(summary).strip() if summary else ""

        except Exception as e:
            print(f"Error generating summary: {e}")
            return ""  # Return empty string if tag generation fails

    def _fetch_user_and_followers(self, username: str):
        """Run Apify actor once and return followers list"""
        try:
            run_input = {
                "user_names": [username],
                "maxFollowers": 200,
                "maxFollowings": 200,
                "getFollowers": True,
                "getFollowing": True,
            }

            run = self.client.actor("C2Wk3I6xAqC4Xi63f").call(run_input=run_input)

            followers: List[Dict[str, Any]] = []
            followings: List[Dict[str, Any]] = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                item_type = item.get('type')
                if item_type == 'follower':
                    followers.append(item)
                if item_type == 'following':
                    followings.append(item)

            return followers,followings
        except Exception as e:
            logger.error(f"Error fetching user and followers: {e}")
            return []
    
    def _get_top_followers(self, followers_data: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        """Get top followers by follower count"""
        try:
            # Sort by followers count and get top N
            sorted_followers = sorted(
                followers_data, 
                key=lambda x: self._get_int(x, ['followers_count', 'followersCount'], 0), 
                reverse=True
            )
            
            top_followers = []
            for follower in sorted_followers[:limit]:
                top_followers.append({
                    "username": follower.get('screen_name') or follower.get('username', ''),
                    "profile_image": follower.get('profile_image_url_https') or follower.get('profile_image_url') or follower.get('profileImageUrl', '')
                    })
            
            return top_followers
            
        except Exception as e:
            logger.error(f"Error getting top followers: {e}")
            return []
    
    def _count_verified_followers(self, followers_data: List[Dict[str, Any]]) -> int:
        """Count verified followers"""
        try:
            verified_count = sum(1 for follower in followers_data if follower.get('verified', False))
            return verified_count
        except Exception as e:
            logger.error(f"Error counting verified followers: {e}")
            return 0
    
    # Trends intentionally omitted as Apify follower feed doesn't provide follow-time reliably
    
    def _calculate_engagement_rate(self, profile_data: Dict[str, Any]) -> float:
        """Calculate engagement rate based on available data"""
        try:
            followers_count = profile_data.get('followersCount', 0)
            tweets_count = profile_data.get('tweetsCount', 0)
            
            if followers_count == 0:
                return 0.0
            
            # Simple engagement rate calculation
            # This is a basic calculation - in reality you'd need more detailed metrics
            engagement_rate = min(tweets_count / followers_count * 100, 100.0)
            return round(engagement_rate, 2)
            
        except Exception as e:
            logger.error(f"Error calculating engagement rate: {e}")
            return 0.0
    
    def _generate_ai_summary(self, profile_data: Optional[Dict[str, Any]], followers_data: List[Dict[str, Any]]) -> str:
        """Generate AI summary of the user's content and audience"""
        try:
            # Aggregate followers' bios to infer typical content type
            verified_followers_count = sum(1 for f in followers_data if f.get('verified', False))
            bios = [f.get('description', '') or '' for f in followers_data if isinstance(f.get('description'), str)]
            sample_text = " ".join(bios[:50]).lower()

            content_type = "general content"
            if any(k in sample_text for k in ['ai', 'ml', 'deep learning', 'engineer', 'developer', 'programming', 'research']):
                content_type = "technology insights"
            elif any(k in sample_text for k in ['investor', 'founder', 'startup', 'business', 'product']):
                content_type = "business commentary"
            elif any(k in sample_text for k in ['news', 'journalist', 'report', 'media']):
                content_type = "news and journalism"

            summary = f"Posts focus on {content_type}; audience includes {verified_followers_count} verified followers."
            
            # Ensure summary is around 150 characters
            if len(summary) > 150:
                summary = summary[:147] + "..."
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating AI summary: {e}")
            return "Twitter user with verified audience and notable followers."

    def _get_int(self, obj: Dict[str, Any], keys: List[str], default: int = 0) -> int:
        """Get first present integer-like field from keys"""
        for key in keys:
            if key in obj and obj.get(key) is not None:
                try:
                    return int(obj.get(key))
                except Exception:
                    continue
        return default
