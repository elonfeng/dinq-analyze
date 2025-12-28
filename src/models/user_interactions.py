"""
User Interactions Database Models

This module defines the database models for user interactions with content,
such as likes and bookmarks for job posts, as well as demo requests.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from src.models.db import Base
from src.models.job_board import JobPost

class JobPostLike(Base):
    """
    JobPostLike model for storing user likes on job posts.
    """
    __tablename__ = 'job_post_likes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True, comment="User ID who liked the post")
    post_id = Column(Integer, ForeignKey('job_posts.id', ondelete='CASCADE'), nullable=False, index=True, comment="ID of the liked job post")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="When the like was created")

    # Define a unique constraint to prevent duplicate likes
    __table_args__ = (
        UniqueConstraint('user_id', 'post_id', name='uq_user_post_like'),
    )

    # Define relationship to JobPost
    post = relationship("JobPost", backref="likes")

    def __repr__(self):
        return f"<JobPostLike(id={self.id}, user_id='{self.user_id}', post_id={self.post_id})>"

    def to_dict(self):
        """Convert the model to a dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'post_id': self.post_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class JobPostBookmark(Base):
    """
    JobPostBookmark model for storing user bookmarks on job posts.
    """
    __tablename__ = 'job_post_bookmarks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True, comment="User ID who bookmarked the post")
    post_id = Column(Integer, ForeignKey('job_posts.id', ondelete='CASCADE'), nullable=False, index=True, comment="ID of the bookmarked job post")
    notes = Column(String(500), nullable=True, comment="User's notes about this bookmark")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="When the bookmark was created")
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="When the bookmark was last updated")

    # Define a unique constraint to prevent duplicate bookmarks
    __table_args__ = (
        UniqueConstraint('user_id', 'post_id', name='uq_user_post_bookmark'),
    )

    # Define relationship to JobPost
    post = relationship("JobPost", backref="bookmarks")

    def __repr__(self):
        return f"<JobPostBookmark(id={self.id}, user_id='{self.user_id}', post_id={self.post_id})>"

    def to_dict(self):
        """Convert the model to a dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'post_id': self.post_id,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class DemoRequest(Base):
    """
    DemoRequest model for storing user requests for product demonstrations.
    This helps track potential customers interested in the product.
    """
    __tablename__ = 'demo_requests'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True, comment="User ID who submitted the request")
    email = Column(String(200), nullable=False, index=True, comment="Email address for contact")
    affiliation = Column(String(200), nullable=False, comment="Organization or institution")
    country = Column(String(100), nullable=False, comment="Country of the requester")
    job_title = Column(String(200), nullable=False, comment="Job title of the requester")
    contact_reason = Column(Text, nullable=False, comment="Reason for requesting a demo")
    additional_details = Column(Text, nullable=True, comment="Additional details provided by the requester")
    marketing_consent = Column(Boolean, nullable=False, default=False, comment="Whether the user consents to marketing communications")
    status = Column(String(50), nullable=False, default="pending", comment="Status of the request (pending, contacted, completed)")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="When the request was created")
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="When the request was last updated")

    def __repr__(self):
        return f"<DemoRequest(id={self.id}, email='{self.email}', user_id='{self.user_id}')>"

    def to_dict(self):
        """Convert the model to a dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'email': self.email,
            'affiliation': self.affiliation,
            'country': self.country,
            'job_title': self.job_title,
            'contact_reason': self.contact_reason,
            'additional_details': self.additional_details,
            'marketing_consent': self.marketing_consent,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
