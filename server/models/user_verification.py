"""
User Verification Models

This module defines the database models for user verification system.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum

class UserType(Enum):
    """User type enumeration"""
    JOB_SEEKER = "job_seeker"  # 找工作的人
    RECRUITER = "recruiter"    # 招聘方

class VerificationStatus(Enum):
    """Verification status enumeration"""
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"

class VerificationStep(Enum):
    """Verification step enumeration"""
    BASIC_INFO = "basic_info"
    EDUCATION = "education"
    PROFESSIONAL = "professional"
    COMPANY_ORG = "company_org"
    SOCIAL_ACCOUNTS = "social_accounts"
    COMPLETED = "completed"

# Database table creation SQL
USER_VERIFICATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    user_type VARCHAR(50) NOT NULL,  -- 'job_seeker' or 'recruiter'
    current_step VARCHAR(50) NOT NULL DEFAULT 'basic_info',
    verification_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    
    -- Basic Information (共同字段)
    full_name VARCHAR(255),
    avatar_url VARCHAR(500),
    user_current_role  VARCHAR(255),
    current_title VARCHAR(255),
    
    -- Job Seeker specific fields
    research_fields TEXT,  -- JSON array
    
    -- Education (Job Seeker only)
    university_name VARCHAR(255),
    degree_level VARCHAR(100),
    department_major VARCHAR(255),
    edu_email VARCHAR(255),
    edu_email_verified BOOLEAN DEFAULT FALSE,
    education_documents TEXT,  -- JSON array of document URLs
    
    -- Professional (Job Seeker only)
    job_title VARCHAR(255),
    company_org VARCHAR(255),
    work_research_summary TEXT,
    company_email VARCHAR(255),
    company_email_verified BOOLEAN DEFAULT FALSE,
    professional_documents TEXT,  -- JSON array of document URLs
    
    -- Company/Org (Recruiter only)
    company_name VARCHAR(255),
    industry VARCHAR(255),
    company_website VARCHAR(500),
    company_introduction TEXT,
    recruiter_company_email VARCHAR(255),
    recruiter_company_email_verified BOOLEAN DEFAULT FALSE,
    company_documents TEXT,  -- JSON array of document URLs
    
    -- Social Accounts (共同字段)
    github_username VARCHAR(255),
    github_verified BOOLEAN DEFAULT FALSE,
    linkedin_url VARCHAR(500),
    linkedin_verified BOOLEAN DEFAULT FALSE,
    twitter_username VARCHAR(255),
    twitter_verified BOOLEAN DEFAULT FALSE,
    google_scholar_url VARCHAR(500),  -- Recruiter only
    google_scholar_verified BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    
    -- Indexes
    INDEX idx_user_id (user_id),
    INDEX idx_user_type (user_type),
    INDEX idx_verification_status (verification_status),
    INDEX idx_current_step (current_step)
);
"""

EMAIL_VERIFICATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS email_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    email_type VARCHAR(50) NOT NULL,  -- 'edu_email', 'company_email', 'recruiter_company_email'
    verification_code VARCHAR(10) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    verified_at TIMESTAMP NULL,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_email (email),
    INDEX idx_verification_code (verification_code),
    INDEX idx_expires_at (expires_at)
);
"""

class UserVerificationModel:
    """User verification data model"""
    
    def __init__(self, data: Dict[str, Any] = None):
        """Initialize with data dictionary"""
        if data is None:
            data = {}
        
        # Basic fields
        self.id = data.get('id')
        self.user_id = data.get('user_id')
        self.user_type = data.get('user_type')
        self.current_step = data.get('current_step', 'basic_info')
        self.verification_status = data.get('verification_status', 'pending')
        
        # Basic Information
        self.full_name = data.get('full_name')
        self.avatar_url = data.get('avatar_url')
        self.user_current_role  = data.get('user_current_role')
        self.current_title = data.get('current_title')
        
        # Job Seeker specific
        self.research_fields = self._parse_json_field(data.get('research_fields'))
        
        # Education
        self.university_name = data.get('university_name')
        self.degree_level = data.get('degree_level')
        self.department_major = data.get('department_major')
        self.edu_email = data.get('edu_email')
        self.edu_email_verified = data.get('edu_email_verified', False)
        self.education_documents = self._parse_json_field(data.get('education_documents'))
        
        # Professional
        self.job_title = data.get('job_title')
        self.company_org = data.get('company_org')
        self.work_research_summary = data.get('work_research_summary')
        self.company_email = data.get('company_email')
        self.company_email_verified = data.get('company_email_verified', False)
        self.professional_documents = self._parse_json_field(data.get('professional_documents'))
        
        # Company/Org (Recruiter)
        self.company_name = data.get('company_name')
        self.industry = data.get('industry')
        self.company_website = data.get('company_website')
        self.company_introduction = data.get('company_introduction')
        self.recruiter_company_email = data.get('recruiter_company_email')
        self.recruiter_company_email_verified = data.get('recruiter_company_email_verified', False)
        self.company_documents = self._parse_json_field(data.get('company_documents'))
        
        # Social Accounts
        self.github_username = data.get('github_username')
        self.github_verified = data.get('github_verified', False)
        self.linkedin_url = data.get('linkedin_url')
        self.linkedin_verified = data.get('linkedin_verified', False)
        self.twitter_username = data.get('twitter_username')
        self.twitter_verified = data.get('twitter_verified', False)
        self.google_scholar_url = data.get('google_scholar_url')
        self.google_scholar_verified = data.get('google_scholar_verified', False)
        
        # Metadata
        self.created_at = data.get('created_at')
        self.updated_at = data.get('updated_at')
        self.completed_at = data.get('completed_at')
    
    def _parse_json_field(self, field_value) -> List[str]:
        """Parse JSON field value"""
        if field_value is None:
            return []
        if isinstance(field_value, str):
            try:
                return json.loads(field_value)
            except json.JSONDecodeError:
                return []
        if isinstance(field_value, list):
            return field_value
        return []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_type': self.user_type,
            'current_step': self.current_step,
            'verification_status': self.verification_status,
            
            # Basic Information
            'full_name': self.full_name,
            'avatar_url': self.avatar_url,
            'user_current_role': self.user_current_role,
            'current_title': self.current_title,
            
            # Job Seeker specific
            'research_fields': self.research_fields,
            
            # Education
            'university_name': self.university_name,
            'degree_level': self.degree_level,
            'department_major': self.department_major,
            'edu_email': self.edu_email,
            'edu_email_verified': self.edu_email_verified,
            'education_documents': self.education_documents,
            
            # Professional
            'job_title': self.job_title,
            'company_org': self.company_org,
            'work_research_summary': self.work_research_summary,
            'company_email': self.company_email,
            'company_email_verified': self.company_email_verified,
            'professional_documents': self.professional_documents,
            
            # Company/Org (Recruiter)
            'company_name': self.company_name,
            'industry': self.industry,
            'company_website': self.company_website,
            'company_introduction': self.company_introduction,
            'recruiter_company_email': self.recruiter_company_email,
            'recruiter_company_email_verified': self.recruiter_company_email_verified,
            'company_documents': self.company_documents,
            
            # Social Accounts
            'github_username': self.github_username,
            'github_verified': self.github_verified,
            'linkedin_url': self.linkedin_url,
            'linkedin_verified': self.linkedin_verified,
            'twitter_username': self.twitter_username,
            'twitter_verified': self.twitter_verified,
            'google_scholar_url': self.google_scholar_url,
            'google_scholar_verified': self.google_scholar_verified,
            
            # Metadata
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'completed_at': self.completed_at
        }

class EmailVerificationModel:
    """Email verification data model"""
    
    def __init__(self, data: Dict[str, Any] = None):
        """Initialize with data dictionary"""
        if data is None:
            data = {}
        
        self.id = data.get('id')
        self.user_id = data.get('user_id')
        self.email = data.get('email')
        self.email_type = data.get('email_type')
        self.verification_code = data.get('verification_code')
        self.expires_at = data.get('expires_at')
        self.verified_at = data.get('verified_at')
        self.attempts = data.get('attempts', 0)
        self.max_attempts = data.get('max_attempts', 3)
        self.created_at = data.get('created_at')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'email': self.email,
            'email_type': self.email_type,
            'verification_code': self.verification_code,
            'expires_at': self.expires_at,
            'verified_at': self.verified_at,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts,
            'created_at': self.created_at
        }
    
    def is_expired(self) -> bool:
        """Check if verification code is expired"""
        if self.expires_at is None:
            return True
        
        if isinstance(self.expires_at, str):
            expires_at = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
        else:
            expires_at = self.expires_at
        
        return datetime.utcnow() > expires_at
    
    def is_verified(self) -> bool:
        """Check if email is verified"""
        return self.verified_at is not None
    
    def can_attempt(self) -> bool:
        """Check if more attempts are allowed"""
        return self.attempts < self.max_attempts and not self.is_expired()

# Step validation schemas
JOB_SEEKER_STEP_SCHEMAS = {
    'basic_info': {
        'required': ['full_name', 'user_current_role', 'current_title'],
        'optional': ['avatar_url', 'research_fields']
    },
    'education': {
        'required': ['university_name', 'degree_level', 'department_major', 'edu_email'],
        'optional': ['education_documents']
    },
    'professional': {
        'required': ['job_title', 'company_org', 'work_research_summary'],
        'optional': ['company_email', 'professional_documents']
    },
    'social_accounts': {
        'required': [],
        'optional': ['github_username', 'linkedin_url', 'twitter_username']
    }
}

RECRUITER_STEP_SCHEMAS = {
    'basic_info': {
        'required': ['full_name', 'user_current_role', 'current_title'],
        'optional': ['avatar_url']
    },
    'company_org': {
        'required': ['company_name', 'industry', 'recruiter_company_email'],
        'optional': ['company_website', 'company_introduction', 'company_documents']
    },
    'social_accounts': {    
        'required': [],
        'optional': ['github_username', 'linkedin_url', 'twitter_username', 'google_scholar_url']
    }
}
