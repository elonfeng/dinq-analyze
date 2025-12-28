"""
Job Board Database Models

This module defines the database models for the job board feature.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Boolean, JSON
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from src.models.db import Base

class JobPost(Base):
    """
    JobPost model for storing job postings and job seeking advertisements.
    """
    __tablename__ = 'job_posts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True, comment="User ID who created the post")
    title = Column(String(200), nullable=False, comment="Title of the post")
    content = Column(Text, nullable=False, comment="Content of the post")
    post_type = Column(Enum('job_offer', 'job_seeking', 'announcement', 'other', 'job', 'internship', 'collaboration', 'others',
                           name='job_post_type_enum'),
                      nullable=False, default='job_offer', index=True,
                      comment="Type of post (job_offer, job_seeking, announcement, other, job, internship, collaboration, others)")
    entity_type = Column(Enum('company', 'headhunter', 'individual', 'others',
                             name='job_post_entity_type_enum'),
                      nullable=True, default='company', index=True,
                      comment="Type of entity behind the post (company, headhunter, individual, others)")
    location = Column(String(100), nullable=True, index=True, comment="Location of the job")
    company = Column(String(100), nullable=True, index=True, comment="Company name")
    position = Column(String(100), nullable=True, index=True, comment="Job position")
    salary_range = Column(String(100), nullable=True, comment="Salary range")
    contact_info = Column(String(200), nullable=True, comment="Contact information")
    tags = Column(JSON, nullable=True, comment="Tags for the post")
    is_active = Column(Boolean, nullable=False, default=True, index=True, comment="Whether the post is active")
    view_count = Column(Integer, nullable=False, default=0, comment="Number of views")
    like_count = Column(Integer, nullable=False, default=0, comment="Number of like")
    bookmark_count = Column(Integer, nullable=False, default=0, comment="Number of bookmark")
    created_at = Column(DateTime, nullable=False, default=func.now(), index=True, comment="When the post was created")
    updated_at = Column(DateTime, nullable=False, default=func.now(),  comment="When the post was last updated")

    def __repr__(self):
        return f"<JobPost(id={self.id}, title='{self.title}', type='{self.post_type}', user_id='{self.user_id}')>"

    def to_dict(self):
        """Convert the model to a dictionary."""
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'content': self.content,
            'post_type': self.post_type,
            'entity_type': self.entity_type,
            'location': self.location,
            'company': self.company,
            'position': self.position,
            'salary_range': self.salary_range,
            'contact_info': self.contact_info,
            'tags': self.tags,
            'is_active': self.is_active,
            'view_count': self.view_count,
            'like_count': self.like_count,
            'bookmark_count': self.bookmark_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

        return result
