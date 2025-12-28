"""
User Verification Models

This module defines the SQLAlchemy models for user verification system.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.sql import func
from src.models.db import Base

class UserVerification(Base):
    """
    User verification model for storing verification process data
    """
    __tablename__ = 'user_verifications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), unique=True, nullable=False, index=True, comment="Unique user identifier")
    user_type = Column(String(50), nullable=False, index=True, comment="User type: job_seeker or recruiter")
    current_step = Column(String(50), nullable=False, default='basic_info', index=True, comment="Current verification step")
    verification_status = Column(String(50), nullable=False, default='pending', index=True, comment="Verification status")
    
    # Basic Information (共同字段)
    full_name = Column(String(255), nullable=True, comment="User's full name")
    avatar_url = Column(String(500), nullable=True, comment="URL to user's avatar image")
    user_current_role = Column(String(255), nullable=True, comment="User's current role")
    current_title = Column(String(255), nullable=True, comment="User's current title")
    
    # Job Seeker specific fields
    research_fields = Column(JSON, nullable=True, comment="Research fields (JSON array)")
    
    # Education (Job Seeker only)
    university_name = Column(String(255), nullable=True, comment="University name")
    degree_level = Column(String(100), nullable=True, comment="Degree level (PhD, Master's, etc.)")
    department_major = Column(String(255), nullable=True, comment="Department or major")
    edu_email = Column(String(255), nullable=True, comment="Educational email address")
    edu_email_verified = Column(Boolean, default=False, nullable=False, comment="Whether edu email is verified")
    education_documents = Column(JSON, nullable=True, comment="Education documents (JSON array of URLs)")
    
    # Professional (Job Seeker only)
    job_title = Column(String(255), nullable=True, comment="Job title")
    company_org = Column(String(255), nullable=True, comment="Company or organization")
    work_research_summary = Column(Text, nullable=True, comment="Work or research summary")
    company_email = Column(String(255), nullable=True, comment="Company email address")
    company_email_verified = Column(Boolean, default=False, nullable=False, comment="Whether company email is verified")
    professional_documents = Column(JSON, nullable=True, comment="Professional documents (JSON array of URLs)")
    
    # Company/Org (Recruiter only)
    company_name = Column(String(255), nullable=True, comment="Company name")
    industry = Column(String(255), nullable=True, comment="Industry")
    company_website = Column(String(500), nullable=True, comment="Company website")
    company_introduction = Column(Text, nullable=True, comment="Company introduction")
    recruiter_company_email = Column(String(255), nullable=True, comment="Recruiter's company email")
    recruiter_company_email_verified = Column(Boolean, default=False, nullable=False, comment="Whether recruiter company email is verified")
    company_documents = Column(JSON, nullable=True, comment="Company documents (JSON array of URLs)")
    
    # Social Accounts (共同字段)
    github_username = Column(String(255), nullable=True, comment="GitHub username")
    github_verified = Column(Boolean, default=False, nullable=False, comment="Whether GitHub is verified")
    linkedin_url = Column(String(500), nullable=True, comment="LinkedIn profile URL")
    linkedin_verified = Column(Boolean, default=False, nullable=False, comment="Whether LinkedIn is verified")
    twitter_username = Column(String(255), nullable=True, comment="Twitter/X username")
    twitter_verified = Column(Boolean, default=False, nullable=False, comment="Whether Twitter is verified")
    google_scholar_url = Column(String(500), nullable=True, comment="Google Scholar profile URL (Recruiter only)")
    google_scholar_verified = Column(Boolean, default=False, nullable=False, comment="Whether Google Scholar is verified")
    
    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False, comment="Record creation timestamp")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp")
    completed_at = Column(DateTime, nullable=True, comment="Verification completion timestamp")

    def __repr__(self):
        return f"<UserVerification(id={self.id}, user_id='{self.user_id}', user_type='{self.user_type}', status='{self.verification_status}')>"

class EmailVerification(Base):
    """
    Email verification model for storing email verification codes
    """
    __tablename__ = 'email_verifications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True, comment="User identifier")
    email = Column(String(255), nullable=False, index=True, comment="Email address to verify")
    email_type = Column(String(50), nullable=False, comment="Type of email: edu_email, company_email, recruiter_company_email")
    verification_code = Column(String(10), nullable=False, index=True, comment="6-digit verification code")
    expires_at = Column(DateTime, nullable=False, index=True, comment="Expiration timestamp")
    verified_at = Column(DateTime, nullable=True, comment="Verification timestamp")
    attempts = Column(Integer, default=0, nullable=False, comment="Number of verification attempts")
    max_attempts = Column(Integer, default=3, nullable=False, comment="Maximum allowed attempts")
    created_at = Column(DateTime, default=func.now(), nullable=False, comment="Record creation timestamp")

    def __repr__(self):
        status = "Verified" if self.verified_at else "Pending"
        return f"<EmailVerification(id={self.id}, email='{self.email}', status='{status}')>"
