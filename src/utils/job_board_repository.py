"""
Job Board Repository

This module provides a repository for managing job board posts.
"""

import logging
import time
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import func, and_, or_, desc, asc, join, text, distinct, literal_column, inspect

import random
from src.models.job_board import JobPost
from src.models.db import User
from src.utils.db_utils import DatabaseRepository, get_db_session, engine, create_tables
from src.utils.user_interactions_repository import JobPostLikeRepository, JobPostBookmarkRepository
# 配置日志
logger = logging.getLogger('job_board_repository')

class JobPostRepository(DatabaseRepository[JobPost]):
    """Repository for job posts"""
    POST_TYPES = [
        "job_offer",
        "job_seeking",
        "announcement",
        "other",
        "job",
        "internship",
        "collaboration",
        "others",
    ]
    def __init__(self):
        super().__init__(JobPost)
        self._random_cache = {}
        # 初始化缓存
        self._initialize_cache()    
        
    def _initialize_cache(self):
        """启动时初始化缓存"""
        try:
            inspector = inspect(engine)
            if not inspector.has_table("job_posts"):
                logger.info("Job posts table not ready; skip cache warmup")
                return
        except Exception:
            logger.info("Job posts table check failed; skip cache warmup")
            return

        logger.info("Initializing random posts cache...")
        for post_type in self.POST_TYPES:
            self._update_cache_for_post_type(post_type)
            
    def _update_cache_for_post_type(self, post_type: str, cache_size: int = 30):
        """为指定post_type更新缓存"""
        try:
            with get_db_session() as session:
                # 直接查询前30条活跃的帖子ID
                query = session.query(JobPost.id).filter(
                    JobPost.post_type == post_type,
                    JobPost.is_active == True
                ).order_by(JobPost.created_at.desc()).limit(cache_size)

                results = query.all()
                post_ids = [result.id for result in results]

                # 更新缓存
                self._random_cache[post_type] = post_ids

                logger.info(f"Updated cache for {post_type}: {len(post_ids)} IDs cached")
                print("success")
            
        except Exception as e:
            logger.error(f"Error updating cache for post_type {post_type}: {e}")
            self._random_cache[post_type] = []
            
    def _get_random_ids_from_cache(self, post_type: str, limit: int) -> List[int]:
        """从缓存中获取随机ID"""
        cached_ids = self._random_cache.get(post_type, [])
        if not cached_ids:
            return []
        
        # 如果缓存的ID数量少于请求数量，返回所有可用的
        if len(cached_ids) <= limit:
            return cached_ids.copy()
        
        # 随机选择指定数量的ID
        return random.sample(cached_ids, limit)
    
    def get_posts_random(self,
                        limit: int = 6,
                        post_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取随机帖子
        
        Args:
            limit: 返回帖子数量，默认6条
            post_type: 帖子类型筛选
            post_ids: 指定的帖子ID列表
            
        Returns:
            随机帖子列表
        """
        try:
            with get_db_session() as session:
                query = session.query(JobPost, User.display_name).outerjoin(
                    User, JobPost.user_id == User.user_id
                )
                

                if post_type:
                    random_ids = self._get_random_ids_from_cache(post_type, limit)
                    if not random_ids:
                        logger.warning(f"No cached IDs for post_type: {post_type}")
                        return []
                    query = query.filter(JobPost.id.in_(random_ids))
                else:
                    # 如果没有指定post_type，从所有类型中随机选择
                    all_random_ids = []
                    for pt in self.POST_TYPES:
                        pt_ids  = self._random_cache.get(pt, [])
                        all_random_ids.extend(pt_ids)
                    
                    if not all_random_ids:
                        logger.warning("No cached IDs available")
                        return []
                    
                    # 随机选择最终的ID列表
                    print(f"all_random_ids: {all_random_ids}")
                    final_ids = random.sample(all_random_ids, min(limit, len(all_random_ids)))
                    query = query.filter(JobPost.id.in_(final_ids))
                
                
                posts = query.all()
                
                # 转换结果
                result = []
                for post, display_name in posts:
                    post_dict = {
                        'id': post.id,
                        'user_id': post.user_id,
                        'display_name': display_name,
                        'title': post.title,
                        'content': post.content,
                        'post_type': post.post_type,
                        'entity_type': post.entity_type,
                        'location': post.location,
                        'company': post.company,
                        'position': post.position,  
                        'salary_range': post.salary_range,
                        'contact_info': post.contact_info,
                        'tags': post.tags,
                        'is_active': post.is_active,
                        'view_count': post.view_count,
                        'like_count': post.like_count,
                        'bookmark_count': post.bookmark_count,
                        'created_at': post.created_at.isoformat() if post.created_at else None,
                        'updated_at': post.updated_at.isoformat() if post.updated_at else None
                    }
                    result.append(post_dict)
                
                return result
                
        except Exception as e:
            logger.error(f"Error getting random posts: {e}")
            return []
        
    def create_post(self,
                   user_id: str,
                   title: str,
                   content: str,
                   post_type: str = 'job_offer',
                   entity_type: str = 'company',
                   location: Optional[str] = None,
                   company: Optional[str] = None,
                   position: Optional[str] = None,
                   salary_range: Optional[str] = None,
                   contact_info: Optional[str] = None,
                   tags: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Create a new job post.

        Args:
            user_id: ID of the user creating the post
            title: Title of the post
            content: Content of the post
            post_type: Type of post (job_offer, job_seeking, announcement, other)
            entity_type: Type of entity behind the post (company, headhunter, individual, others)
            location: Location of the job
            company: Company name
            position: Job position
            salary_range: Salary range
            contact_info: Contact information
            tags: Tags for the post

        Returns:
            Dictionary containing the created job post data, or None if creation failed
        """
        try:
            if os.getenv("DINQ_DB_AUTO_CREATE_TABLES", "false").lower() in ("1", "true", "yes", "on"):
                try:
                    inspector = inspect(engine)
                    if not inspector.has_table("job_posts"):
                        create_tables()
                except Exception:
                    pass
            with get_db_session() as session:
                post = JobPost(
                    user_id=user_id,
                    title=title,
                    content=content,
                    post_type=post_type,
                    entity_type=entity_type,
                    location=location,
                    company=company,
                    position=position,
                    salary_range=salary_range,
                    contact_info=contact_info,
                    tags=tags,
                    is_active=True,
                    view_count=0,
                    like_count=0,
                    bookmark_count=0,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )

                session.add(post)
                session.flush()

                # 获取ID
                post_id = post.id
                session.commit()

                post_dict = {
                    'id': post_id,
                    'user_id': user_id,
                    'title': title,
                    'content': content,
                    'post_type': post_type,
                    'entity_type': entity_type,
                    'location': location,
                    'company': company,
                    'position': position,
                    'salary_range': salary_range,
                    'contact_info': contact_info,
                    'tags': tags,
                    'is_active': True,
                    'view_count': 0,
                    'like_count': 0,
                    'bookmark_count': 0,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
                try:
                    self._update_cache_for_post_type(post_type)
                except Exception:
                    pass
                return post_dict
        except Exception as e:
            logger.error(f"Error creating job post: {e}")
            return None

    def get_posts(self,
                 limit: int = 20,
                 offset: int = 0,
                 post_type: Optional[str] = None,
                 entity_type: Optional[str] = None,
                 location: Optional[str] = None,
                 company: Optional[str] = None,
                 position: Optional[str] = None,
                 search_term: Optional[str] = None,
                 user_id: Optional[str] = None,
                 tags: Optional[List[str]] = None,
                 is_active: bool = True,
                 sort_by: str = 'created_at',
                 sort_order: str = 'desc',
                 include_interactions: bool = True) -> List[Dict[str, Any]]:
        """
        Get job posts with filtering and sorting.

        Args:
            limit: Maximum number of posts to return
            offset: Number of posts to skip
            post_type: Filter by post type
            entity_type: Filter by entity type (company, headhunter, individual, others)
            location: Filter by location
            company: Filter by company
            position: Filter by position
            search_term: Search in title and content
            user_id: Filter by user ID
            tags: Filter by tags
            is_active: Filter by active status
            sort_by: Field to sort by
            sort_order: Sort order ('asc' or 'desc')
            include_interactions: Include like and bookmark counts

        Returns:
            List of job post dictionaries
        """
        try:
            with get_db_session() as session:
                # 基础查询，包含用户表
                query = session.query(JobPost, User.display_name).outerjoin(
                    User, JobPost.user_id == User.user_id
                )
                # Apply filters
                if post_type:
                    query = query.filter(JobPost.post_type == post_type)

                if entity_type:
                    query = query.filter(JobPost.entity_type == entity_type)

                if location:
                    query = query.filter(JobPost.location.ilike(f"%{location}%"))

                if company:
                    query = query.filter(JobPost.company.ilike(f"%{company}%"))

                if position:
                    query = query.filter(JobPost.position.ilike(f"%{position}%"))

                if search_term:
                    query = query.filter(
                        or_(
                            JobPost.title.ilike(f"%{search_term}%"),
                            JobPost.content.ilike(f"%{search_term}%")
                        )
                    )

                if user_id:
                    query = query.filter(JobPost.user_id == user_id)

                if tags:
                    # This is a simplified approach for JSON filtering
                    # For more complex filtering, you might need to use database-specific JSON functions
                    for tag in tags:
                        query = query.filter(JobPost.tags.contains(tag))

                if is_active is not None:
                    query = query.filter(JobPost.is_active == is_active)

                # Apply sorting
                if sort_order.lower() == 'asc':
                    query = query.order_by(asc(getattr(JobPost, sort_by)))
                else:
                    query = query.order_by(desc(getattr(JobPost, sort_by)))

                # Apply pagination
                query = query.limit(limit).offset(offset)
                
                # 获取结果并转换为字典，避免会话绑定问题
                posts = query.all()
              
                # 如果需要包含互动数据，初始化仓库
                


                # 转换结果
                result = []
                for post, display_name in posts:
                    # 将每个 JobPost 对象转换为字典
                    post_dict = {
                        'id': post.id,
                        'user_id': post.user_id,
                        'display_name': display_name,  # 添加用户显示名称
                        'title': post.title,
                        'content': post.content,
                        'post_type': post.post_type,
                        'entity_type': post.entity_type,
                        'location': post.location,
                        'company': post.company,
                        'position': post.position,
                        'salary_range': post.salary_range,
                        'contact_info': post.contact_info,
                        'tags': post.tags,
                        'is_active': post.is_active,
                        'view_count': post.view_count,
                        'like_count': post.like_count,
                        'bookmark_count': post.bookmark_count,
                        'created_at': post.created_at.isoformat() if post.created_at else None,
                        'updated_at': post.updated_at.isoformat() if post.updated_at else None
                    }

                    # 添加喜欢和收藏计数
                    result.append(post_dict)

                return result
        except Exception as e:
            logger.error(f"Error getting job posts: {e}")
            return []

    def get_post_by_id(self, post_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a job post by ID.

        Args:
            post_id: ID of the post

        Returns:
            Job post dictionary if found, None otherwise
        """
        try:
            with get_db_session() as session:
                # 修改查询以包含用户表
                row = session.query(JobPost, User.display_name)\
                    .outerjoin(User, JobPost.user_id == User.user_id)\
                    .filter(JobPost.id == post_id)\
                    .first()

                if not row:
                    return None

                post, display_name = row

                # 将 JobPost 对象转换为字典
                return {
                    'id': post.id,
                    'user_id': post.user_id,
                    'display_name': display_name,  # 添加用户显示名称
                    'title': post.title,
                    'content': post.content,
                    'post_type': post.post_type,
                    'entity_type': post.entity_type,
                    'location': post.location,
                    'company': post.company,
                    'position': post.position,
                    'salary_range': post.salary_range,
                    'contact_info': post.contact_info,
                    'tags': post.tags,
                    'is_active': post.is_active,
                    'view_count': post.view_count,
                    'like_count': post.like_count,
                    'bookmark_count': post.bookmark_count,
                    'created_at': post.created_at.isoformat() if post.created_at else None,
                    'updated_at': post.updated_at.isoformat() if post.updated_at else None
                }
        except Exception as e:
            logger.error(f"Error getting job post by ID: {e}")
            return None

    def update_post(self,
                   post_id: int,
                   user_id: str,
                   **update_data) -> bool:
        """
        Update a job post.

        Args:
            post_id: ID of the post to update
            user_id: ID of the user updating the post (for authorization)
            **update_data: Fields to update

        Returns:
            True if update was successful, False otherwise
        """
        try:
            with get_db_session() as session:
                post = session.query(JobPost).filter(JobPost.id == post_id).first()

                if not post:
                    logger.warning(f"Post not found: {post_id}")
                    return False

                # Check if the user is authorized to update this post
                if post.user_id != user_id:
                    logger.warning(f"User {user_id} not authorized to update post {post_id}")
                    return False

                # Update fields
                for key, value in update_data.items():
                    if hasattr(post, key):
                        setattr(post, key, value)

                # Update the updated_at timestamp
                post.updated_at = datetime.now()

                session.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating job post: {e}")
            return False

    def delete_post(self, post_id: int, user_id: str) -> bool:
        """
        Delete a job post.

        Args:
            post_id: ID of the post to delete
            user_id: ID of the user deleting the post (for authorization)

        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            with get_db_session() as session:
                post = session.query(JobPost).filter(JobPost.id == post_id).first()

                if not post:
                    logger.warning(f"Post not found: {post_id}")
                    return False

                # Check if the user is authorized to delete this post
                if post.user_id != user_id:
                    logger.warning(f"User {user_id} not authorized to delete post {post_id}")
                    return False

                session.delete(post)
                session.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting job post: {e}")
            return False

    def increment_view_count(self, post_id: int) -> bool:
        """
        Increment the view count of a post.

        Args:
            post_id: ID of the post

        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_session() as session:
                post = session.query(JobPost).filter(JobPost.id == post_id).first()

                if not post:
                    logger.warning(f"Post not found: {post_id}")
                    return False

                post.view_count += 1
                session.commit()
                return True
        except Exception as e:
            logger.error(f"Error incrementing view count: {e}")
            return False

    def count_posts(self,
                   post_type: Optional[str] = None,
                   entity_type: Optional[str] = None,
                   location: Optional[str] = None,
                   company: Optional[str] = None,
                   position: Optional[str] = None,
                   search_term: Optional[str] = None,
                   user_id: Optional[str] = None,
                   tags: Optional[List[str]] = None,
                   is_active: bool = True) -> int:
        """
        Count job posts with filtering.

        Args:
            post_type: Filter by post type
            entity_type: Filter by entity type (company, headhunter, individual, others)
            location: Filter by location
            company: Filter by company
            position: Filter by position
            search_term: Search in title and content
            user_id: Filter by user ID
            tags: Filter by tags
            is_active: Filter by active status

        Returns:
            Number of posts matching the filters
        """
        try:
            with get_db_session() as session:
                query = session.query(func.count(JobPost.id))

                # Apply filters
                if post_type:
                    query = query.filter(JobPost.post_type == post_type)

                if entity_type:
                    query = query.filter(JobPost.entity_type == entity_type)

                if location:
                    query = query.filter(JobPost.location.ilike(f"%{location}%"))

                if company:
                    query = query.filter(JobPost.company.ilike(f"%{company}%"))

                if position:
                    query = query.filter(JobPost.position.ilike(f"%{position}%"))

                if search_term:
                    query = query.filter(
                        or_(
                            JobPost.title.ilike(f"%{search_term}%"),
                            JobPost.content.ilike(f"%{search_term}%")
                        )
                    )

                if user_id:
                    query = query.filter(JobPost.user_id == user_id)

                if tags:
                    for tag in tags:
                        query = query.filter(JobPost.tags.contains(tag))

                if is_active is not None:
                    query = query.filter(JobPost.is_active == is_active)

                return query.scalar() or 0
        except Exception as e:
            logger.error(f"Error counting job posts: {e}")
            return 0

# Create a singleton instance
job_post_repo = JobPostRepository()
