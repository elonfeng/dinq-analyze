"""
User Interactions Repository

This module provides repositories for managing user interactions with content,
such as likes and bookmarks for job posts.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import func, and_, or_, desc, asc
from sqlalchemy.orm import Session
from src.models.user_interactions import JobPostLike, JobPostBookmark, DemoRequest
from src.models.job_board import JobPost
from src.utils.db_utils import DatabaseRepository, get_db_session

# 配置日志
logger = logging.getLogger('user_interactions_repository')

class JobPostLikeRepository(DatabaseRepository[JobPostLike]):
    """Repository for job post likes"""

    def __init__(self):
        super().__init__(JobPostLike)

    def like_post(self, user_id: str, post_id: int) -> bool:
        """
        Add a like to a job post.

        Args:
            user_id: ID of the user liking the post
            post_id: ID of the post to like

        Returns:
            True if the like was successfully added, False otherwise
        """
        try:
            with get_db_session() as session:
                # Check if the post exists
                post = session.query(JobPost).filter(JobPost.id == post_id).first()
                if not post:
                    logger.warning(f"Cannot like non-existent post: {post_id}")
                    return False

                # Check if the user already liked this post
                existing_like = session.query(JobPostLike).filter(
                    JobPostLike.user_id == user_id,
                    JobPostLike.post_id == post_id
                ).first()

                if existing_like:
                    logger.info(f"User {user_id} already liked post {post_id}")
                    return True  # Already liked, consider it a success

                # Create new like
                like = JobPostLike(
                    user_id=user_id,
                    post_id=post_id,
                    created_at=datetime.now()
                )

                session.add(like)
                session.commit()
                logger.info(f"User {user_id} liked post {post_id}")
                return True
        except Exception as e:
            logger.error(f"Error liking post: {e}")
            return False

    def unlike_post(self, user_id: str, post_id: int) -> bool:
        """
        Remove a like from a job post.

        Args:
            user_id: ID of the user unliking the post
            post_id: ID of the post to unlike

        Returns:
            True if the like was successfully removed, False otherwise
        """
        try:
            with get_db_session() as session:
                # Find the like
                like = session.query(JobPostLike).filter(
                    JobPostLike.user_id == user_id,
                    JobPostLike.post_id == post_id
                ).first()

                if not like:
                    logger.warning(f"Cannot unlike post that wasn't liked: user {user_id}, post {post_id}")
                    return False

                # Delete the like
                session.delete(like)
                session.commit()
                logger.info(f"User {user_id} unliked post {post_id}")
                return True
        except Exception as e:
            logger.error(f"Error unliking post: {e}")
            return False

    def is_post_liked(self, user_id: str, post_id: int) -> bool:
        """
        Check if a user has liked a post.

        Args:
            user_id: ID of the user
            post_id: ID of the post

        Returns:
            True if the user has liked the post, False otherwise
        """
        try:
            with get_db_session() as session:
                like = session.query(JobPostLike).filter(
                    JobPostLike.user_id == user_id,
                    JobPostLike.post_id == post_id
                ).first()
                return like is not None
        except Exception as e:
            logger.error(f"Error checking if post is liked: {e}")
            return False

    def get_user_liked_posts(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get posts liked by a user.

        Args:
            user_id: ID of the user
            limit: Maximum number of posts to return
            offset: Number of posts to skip

        Returns:
            List of job post dictionaries
        """
        try:
            with get_db_session() as session:
                # Query for likes and join with posts
                query = session.query(JobPost).join(
                    JobPostLike, JobPostLike.post_id == JobPost.id
                ).filter(
                    JobPostLike.user_id == user_id
                ).order_by(
                    desc(JobPostLike.created_at)
                ).offset(offset).limit(limit)

                posts = query.all()

                # Convert to dictionaries
                return [post.to_dict() for post in posts]
        except Exception as e:
            logger.error(f"Error getting user liked posts: {e}")
            return []

    def count_post_likes(self, post_id: int) -> int:
        """
        Count the number of likes for a post.

        Args:
            post_id: ID of the post

        Returns:
            Number of likes
        """
        try:
            with get_db_session() as session:
                count = session.query(func.count(JobPostLike.id)).filter(
                    JobPostLike.post_id == post_id
                ).scalar()
                return count
        except Exception as e:
            logger.error(f"Error counting post likes: {e}")
            return 0

    def count_posts_likes(self, post_ids: List[int],session: Session) -> Dict[int, int]:
        """
        批量获取多个帖子的点赞数。

        Args:
            post_ids: 帖子ID列表

        Returns:
            字典，key为帖子ID，value为点赞数
        """
        try:
            
                # 使用 group by 和 count 一次性获取所有帖子的点赞数
            results = session.query(
                JobPostLike.post_id,
                func.count(JobPostLike.id).label('like_count')
            ).filter(
                JobPostLike.post_id.in_(post_ids)
            ).group_by(
                JobPostLike.post_id
            ).all()

            # 转换为字典
            return {post_id: count for post_id, count in results}
        except Exception as e:
            logger.error(f"Error counting posts likes: {e}")
            return {}

class JobPostBookmarkRepository(DatabaseRepository[JobPostBookmark]):
    """Repository for job post bookmarks"""

    def __init__(self):
        super().__init__(JobPostBookmark)

    def bookmark_post(self, user_id: str, post_id: int, notes: Optional[str] = None) -> bool:
        """
        Bookmark a job post.

        Args:
            user_id: ID of the user bookmarking the post
            post_id: ID of the post to bookmark
            notes: Optional notes about the bookmark

        Returns:
            True if the bookmark was successfully added, False otherwise
        """
        try:
            with get_db_session() as session:

                # Check if the user already bookmarked this post
                existing_bookmark = session.query(JobPostBookmark).filter(
                    JobPostBookmark.user_id == user_id,
                    JobPostBookmark.post_id == post_id
                ).first()

                if existing_bookmark:
                    # Update notes if provided
                    if notes is not None:
                        existing_bookmark.notes = notes
                        existing_bookmark.updated_at = datetime.now()
                        session.commit()
                    return True  # Already bookmarked, consider it a success

                # Create new bookmark
                bookmark = JobPostBookmark(
                    user_id=user_id,
                    post_id=post_id,
                    notes=notes,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )

                session.add(bookmark)
                session.commit()
                
                
                post = session.query(JobPost).filter(JobPost.id == post_id).first()
                if not post:
                    return False
                else:
                    post.bookmark_count += 1
                    session.commit()
                return True
        except Exception as e:
            logger.error(f"Error bookmarking post: {e}")
            return False

    def remove_bookmark(self, user_id: str, post_id: int) -> bool:
        """
        Remove a bookmark from a job post.

        Args:
            user_id: ID of the user removing the bookmark
            post_id: ID of the post to remove from bookmarks

        Returns:
            True if the bookmark was successfully removed, False otherwise
        """
        try:
            with get_db_session() as session:
                # Find the bookmark
                bookmark = session.query(JobPostBookmark).filter(
                    JobPostBookmark.user_id == user_id,
                    JobPostBookmark.post_id == post_id
                ).first()

                if not bookmark:
                    return False
                session.delete(bookmark)
                session.commit()

                post = session.query(JobPost).filter(JobPost.id == post_id).first()
                if not post:
                    return False
                else:
                    post.bookmark_count -= 1
                    session.commit()
                return True
        except Exception as e:
            logger.error(f"Error removing bookmark: {e}")
            return False

    def update_bookmark_notes(self, user_id: str, post_id: int, notes: str) -> bool:
        """
        Update notes for a bookmarked post.

        Args:
            user_id: ID of the user
            post_id: ID of the bookmarked post
            notes: New notes for the bookmark

        Returns:
            True if the notes were successfully updated, False otherwise
        """
        try:
            with get_db_session() as session:
                # Find the bookmark
                bookmark = session.query(JobPostBookmark).filter(
                    JobPostBookmark.user_id == user_id,
                    JobPostBookmark.post_id == post_id
                ).first()

                if not bookmark:
                    logger.warning(f"Cannot update notes for non-existent bookmark: user {user_id}, post {post_id}")
                    return False

                # Update notes
                bookmark.notes = notes
                bookmark.updated_at = datetime.now()
                session.commit()
                logger.info(f"User {user_id} updated notes for bookmarked post {post_id}")
                return True
        except Exception as e:
            logger.error(f"Error updating bookmark notes: {e}")
            return False

    def is_post_bookmarked(self, user_id: str, post_id: int) -> bool:
        """
        Check if a user has bookmarked a post.

        Args:
            user_id: ID of the user
            post_id: ID of the post

        Returns:
            True if the user has bookmarked the post, False otherwise
        """
        try:
            with get_db_session() as session:
                bookmark = session.query(JobPostBookmark).filter(
                    JobPostBookmark.user_id == user_id,
                    JobPostBookmark.post_id == post_id
                ).first()
                return bookmark is not None
        except Exception as e:
            logger.error(f"Error checking if post is bookmarked: {e}")
            return False

    def get_user_bookmarked_posts(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get posts bookmarked by a user.

        Args:
            user_id: ID of the user
            limit: Maximum number of posts to return
            offset: Number of posts to skip

        Returns:
            List of job post dictionaries with bookmark information
        """
        try:
            with get_db_session() as session:
                # Query for bookmarks and join with posts
                results = session.query(JobPost, JobPostBookmark).join(
                    JobPostBookmark, JobPostBookmark.post_id == JobPost.id
                ).filter(
                    JobPostBookmark.user_id == user_id
                ).order_by(
                    desc(JobPostBookmark.created_at)
                ).offset(offset).limit(limit).all()

                # Convert to dictionaries with bookmark info
                posts_with_bookmarks = []
                for post, bookmark in results:
                    post_dict = post.to_dict()
                    post_dict['bookmark'] = {
                        'id': bookmark.id,
                        'notes': bookmark.notes,
                        'created_at': bookmark.created_at.isoformat() if bookmark.created_at else None,
                        'updated_at': bookmark.updated_at.isoformat() if bookmark.updated_at else None
                    }
                    posts_with_bookmarks.append(post_dict)

                return posts_with_bookmarks
        except Exception as e:
            logger.error(f"Error getting user bookmarked posts: {e}")
            return []

    def count_user_bookmarks(self, user_id: str) -> int:
        """
        Count the number of bookmarks for a user.

        Args:
            user_id: ID of the user

        Returns:
            Number of bookmarks
        """
        try:
            with get_db_session() as session:
                count = session.query(func.count(JobPostBookmark.id)).filter(
                    JobPostBookmark.user_id == user_id
                ).scalar()
                return count
        except Exception as e:
            logger.error(f"Error counting user bookmarks: {e}")
            return 0
            
    def count_post_bookmarks(self, post_id: int) -> int:
        """
        Count the number of bookmarks for a post.

        Args:
            post_id: ID of the post

        Returns:
            Number of bookmarks
        """
        try:
            with get_db_session() as session:
                count = session.query(func.count(JobPostBookmark.id)).filter(
                    JobPostBookmark.post_id == post_id
                ).scalar()
                return count
        except Exception as e:
            logger.error(f"Error counting post bookmarks: {e}")
            return 0

    def count_posts_bookmarks(self, post_ids: List[int],session: Session) -> Dict[int, int]:
        """
        批量获取多个帖子的收藏数。

        Args:
            post_ids: 帖子ID列表

        Returns:
            字典，key为帖子ID，value为收藏数
        """
        try:
            
                # 使用 group by 和 count 一次性获取所有帖子的收藏数
            results = session.query(
                JobPostBookmark.post_id,
                func.count(JobPostBookmark.id).label('bookmark_count')
            ).filter(
                JobPostBookmark.post_id.in_(post_ids)
            ).group_by(
                JobPostBookmark.post_id
            ).all()

            # 转换为字典
            return {post_id: count for post_id, count in results}
        except Exception as e:
            logger.error(f"Error counting posts bookmarks: {e}")
            return {}

class DemoRequestRepository(DatabaseRepository[DemoRequest]):
    """Repository for demo requests"""

    def __init__(self):
        super().__init__(DemoRequest)

    def create_demo_request(self, user_id: str, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a new demo request.

        Args:
            user_id: ID of the user submitting the request
            request_data: Dictionary containing demo request data

        Returns:
            Dictionary representation of the created DemoRequest object or None if creation failed
        """
        try:
            with get_db_session() as session:
                # Create the demo request object
                demo_request = DemoRequest(
                    user_id=user_id,
                    email=request_data.get('email'),
                    affiliation=request_data.get('affiliation'),
                    country=request_data.get('country'),
                    job_title=request_data.get('job_title'),
                    contact_reason=request_data.get('contact_reason'),
                    additional_details=request_data.get('additional_details'),
                    marketing_consent=request_data.get('marketing_consent', False),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )

                session.add(demo_request)
                session.commit()  # Commit the transaction

                # Get the demo request data as a dictionary
                result = demo_request.to_dict()

                logger.info(f"Created demo request for user {user_id}, email {request_data.get('email')}")
                return result
        except Exception as e:
            logger.error(f"Error creating demo request: {e}")
            return None

    def get_user_demo_requests(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all demo requests submitted by a user.

        Args:
            user_id: ID of the user

        Returns:
            List of demo request dictionaries
        """
        try:
            with get_db_session() as session:
                requests = session.query(DemoRequest).filter(
                    DemoRequest.user_id == user_id
                ).order_by(desc(DemoRequest.created_at)).all()

                return [req.to_dict() for req in requests]
        except Exception as e:
            logger.error(f"Error getting user demo requests: {e}")
            return []

    def get_all_demo_requests(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get all demo requests with pagination.

        Args:
            limit: Maximum number of requests to return
            offset: Number of requests to skip

        Returns:
            List of demo request dictionaries
        """
        try:
            with get_db_session() as session:
                requests = session.query(DemoRequest).order_by(
                    desc(DemoRequest.created_at)
                ).limit(limit).offset(offset).all()

                return [req.to_dict() for req in requests]
        except Exception as e:
            logger.error(f"Error getting all demo requests: {e}")
            return []

    def update_demo_request_status(self, request_id: int, status: str) -> bool:
        """
        Update the status of a demo request.

        Args:
            request_id: ID of the demo request
            status: New status (pending, contacted, completed)

        Returns:
            True if the status was successfully updated, False otherwise
        """
        try:
            with get_db_session() as session:
                request = session.query(DemoRequest).filter(DemoRequest.id == request_id).first()
                if not request:
                    logger.warning(f"Cannot update non-existent demo request: {request_id}")
                    return False

                request.status = status
                request.updated_at = datetime.now()
                session.commit()
                logger.info(f"Updated demo request {request_id} status to {status}")
                return True
        except Exception as e:
            logger.error(f"Error updating demo request status: {e}")
            return False

# Create singleton instances
job_post_like_repo = JobPostLikeRepository()
job_post_bookmark_repo = JobPostBookmarkRepository()
demo_request_repo = DemoRequestRepository()
