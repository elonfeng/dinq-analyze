"""
HuggingFace Profile Analyzer

This module provides functionality to analyze HuggingFace user profiles using HuggingFace API.
"""

import os
import re
import json
import logging
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional

# Configure logging
logger = logging.getLogger(__name__)

class HuggingFaceAnalyzer:
    """Analyzer for Hugging Face user profiles using HuggingFace API"""
    
    def __init__(self):
        """Initialize the Hugging Face analyzer"""
        self.base_url = "https://huggingface.co/api"
        logger.info("HuggingFaceAnalyzer initialized")
    
    def analyze_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a Hugging Face user profile using HuggingFace API
        
        Args:
            username: Hugging Face username
            
        Returns:
            Dictionary containing profile analysis or None if failed
        """
        try:
            logger.info(f"Starting analysis for Hugging Face user: {username}")
            
            # Get user overview
            overview = self._get_user_overview(username)
            if not overview:
                logger.error(f"Failed to get overview for user: {username}")
                return None
            
            # Get user's models, datasets, and spaces
            models = self._get_user_models(username)
            datasets = self._get_user_datasets(username)
            spaces = self._get_user_spaces(username)
            
            # Find representative work
            representative_work = self._find_representative_work(models, datasets, spaces)

            # Build profile data
            profile_data = {
                "avatarUrl":overview['avatarUrl'],
                "fullname":overview['fullname'],
                "numModels":overview['numModels'],
                "numDatasets":overview['numDatasets'],
                "numSpaces":overview['numSpaces'],
                "numPapers":overview['numPapers'],
                "numFollowers":overview['numFollowers'],
                "numFollowing":overview['numFollowing'],
                "orgs":overview['orgs'],
                "representative_work":representative_work
            }
            
            logger.info(f"Analysis completed for {username}")
            return profile_data
            
        except Exception as e:
            logger.error(f"Error analyzing profile for {username}: {e}")
            return None
    
    def _get_user_overview(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user overview from HuggingFace API"""
        try:
            url = f"{self.base_url}/users/{username}/overview"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get user overview: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting user overview: {e}")
            return None
    
    def _get_user_models(self, username: str) -> List[Dict[str, Any]]:
        """Get user's models from HuggingFace API"""
        try:
            url = f"{self.base_url}/models"
            params = {
                'author': username,
                'limit': 20,
                'sort': 'downloads',
                'direction': -1
            }
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get user models: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting user models: {e}")
            return []
    
    def _get_user_datasets(self, username: str) -> List[Dict[str, Any]]:
        """Get user's datasets from HuggingFace API"""
        try:
            url = f"{self.base_url}/datasets"
            params = {
                'author': username,
                'limit': 20,
                'sort': 'downloads',
                'direction': -1
            }
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get user datasets: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting user datasets: {e}")
            return []
    
    def _get_user_spaces(self, username: str) -> List[Dict[str, Any]]:
        """Get user's spaces from HuggingFace API"""
        try:
            url = f"{self.base_url}/spaces"
            params = {
                'author': username,
                'limit': 20,
                'sort': 'likes',
                'direction': -1
            }
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get user spaces: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting user spaces: {e}")
            return []
    
    def _find_representative_work(self, models: List[Dict], datasets: List[Dict], spaces: List[Dict]) -> Optional[Dict[str, Any]]:
        """Find the most representative work based on downloads and likes"""
        try:
            representative_work = None
            temp_count = 0
            # Add models
            for model in models:
                if model.get("downloads") and (model.get("downloads") > temp_count):
                    temp_count = model.get("downloads")
                    representative_work = model

            # Add datasets
            for dataset in datasets:
                if dataset.get("downloads")  and (dataset.get("downloads") > temp_count):
                    temp_count = dataset.get("downloads")
                    representative_work = dataset
            
            # Add spaces
            for space in spaces:
                if space.get("likes") and (space.get("likes") > temp_count):
                    temp_count = space.get("likes")
                    representative_work = space
            return representative_work
            
        except Exception as e:
            logger.error(f"Error finding representative work: {e}")
            return None
    
    def _format_organizations(self, orgs: List[Dict]) -> List[Dict[str, Any]]:
        """Format organizations data"""
        try:
            formatted_orgs = []
            for org in orgs[:10]:  # Limit to 10 organizations
                formatted_orgs.append({
                    'name': org.get('name', ''),
                    'fullname': org.get('fullname', ''),
                    'url': f"https://huggingface.co/{org.get('name', '')}",
                    'logo': org.get('avatarUrl', '')
                })
            return formatted_orgs
            
        except Exception as e:
            logger.error(f"Error formatting organizations: {e}")
            return []
