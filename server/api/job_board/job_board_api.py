"""
Job Board API

This module provides API endpoints for the job board feature.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify, g, current_app
import sqlalchemy.exc
from server.utils.auth import require_verified_user
from server.utils.user_utils import get_current_user_id
from src.utils.job_board_repository import job_post_repo

# 配置日志
logger = logging.getLogger('server.api.job_board')

# 创建蓝图
job_board_bp = Blueprint('job_board', __name__)

@job_board_bp.route('/api/job-board/posts', methods=['GET'])
def get_job_posts():
    """
    Get job posts with filtering and pagination.

    Query parameters:
        limit: Maximum number of posts to return (default: 20)
        offset: Number of posts to skip (default: 0)
        post_type: Filter by post type (job_offer, job_seeking, announcement, other)
        location: Filter by location
        company: Filter by company
        position: Filter by position
        search: Search in title and content
        user_id: Filter by user ID
        tags: Filter by tags (comma-separated)
        sort_by: Field to sort by (default: created_at)
        sort_order: Sort order (asc or desc, default: desc)

    Returns:
        JSON response with job posts and pagination info
    """
    try:
        # Get query parameters
        limit = int(request.args.get('limit', 20))
        # limit最大20
        if limit > 20:
            limit = 20
        offset = int(request.args.get('offset', 0))
        post_type = request.args.get('post_type')
        entity_type = request.args.get('entity_type')
        location = request.args.get('location')
        company = request.args.get('company')
        position = request.args.get('position')
        search_term = request.args.get('search')
        user_id = request.args.get('user_id')
        tags_str = request.args.get('tags')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        # include_interactions = request.args.get('include_interactions', True) == 'true'
        # 默认包含交互，但是也要判断用户的请求
        include_interactions = True
        if request.args.get('include_interactions') == 'false':
            include_interactions = False
        # Parse tags
        tags = tags_str.split(',') if tags_str else None
        # Get posts
        posts = job_post_repo.get_posts_random(
            limit=limit,
            post_type=post_type
        )

        # Count total posts
        total_count = len(posts)
        # total_count = job_post_repo.count_posts(
        #     post_type=post_type,
        #     entity_type=entity_type,
        #     location=location,
        #     company=company,
        #     position=position,
        #     search_term=search_term,
        #     user_id=user_id,
        #     tags=tags
        # )

        # 由于 get_posts 现在直接返回字典列表，不需要再转换
        posts_data = posts

        # Return response
        return jsonify({
            'success': True,
            'data': {
                'posts': posts_data,
                'pagination': {
                    'total': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_more': offset + len(posts) < total_count
                }
            }
        })
    except Exception as e:
        logger.error(f"Error getting job posts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@job_board_bp.route('/api/job-board/posts/<int:post_id>', methods=['GET'])
def get_job_post(post_id):
    """
    Get a job post by ID.

    Args:
        post_id: ID of the post

    Returns:
        JSON response with job post data
    """
    try:
        # Get post
        post = job_post_repo.get_post_by_id(post_id)

        if not post:
            return jsonify({
                'success': False,
                'error': 'Post not found'
            }), 404

        # Increment view count
        job_post_repo.increment_view_count(post_id)

        # Return response
        return jsonify({
            'success': True,
            'data': post  # 现在 get_post_by_id 直接返回字典，不需要再调用 to_dict()
        })
    except Exception as e:
        logger.error(f"Error getting job post: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@job_board_bp.route('/api/job-board/posts', methods=['POST'])
@require_verified_user
def create_job_post():
    """
    Create a new job post.

    Request body:
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
        JSON response with created job post data
    """
    try:
        # Get user ID
        user_id = get_current_user_id()

        # Get request data
        data = request.json

        # Validate required fields
        if not data.get('title'):
            return jsonify({
                'success': False,
                'error': 'Title is required'
            }), 400

        if not data.get('content'):
            return jsonify({
                'success': False,
                'error': 'Content is required'
            }), 400

        # Create post
        post = job_post_repo.create_post(
            user_id=user_id,
            title=data.get('title'),
            content=data.get('content'),
            post_type=data.get('post_type', 'job_offer'),
            entity_type=data.get('entity_type', 'company'),
            location=data.get('location'),
            company=data.get('company'),
            position=data.get('position'),
            salary_range=data.get('salary_range'),
            contact_info=data.get('contact_info'),
            tags=data.get('tags')
        )

        if not post:
            return jsonify({
                'success': False,
                'error': 'Failed to create post'
            }), 500

        # Return response
        return jsonify({
            'success': True,
            'data': {
                **post,  # post 是字典
                'display_name': data.get('display_name')
            }
        }), 201
    except Exception as e:
        logger.error(f"Error creating job post: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@job_board_bp.route('/api/job-board/posts/<int:post_id>', methods=['PUT'])
@require_verified_user
def update_job_post(post_id):
    """
    Update a job post.

    Args:
        post_id: ID of the post

    Request body:
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
        is_active: Whether the post is active

    Returns:
        JSON response with updated job post data
    """
    try:
        # Get user ID
        user_id = get_current_user_id()

        # Get request data
        data = request.json

        # Get post to check if it exists and belongs to the user
        post = job_post_repo.get_post_by_id(post_id)

        if not post:
            return jsonify({
                'success': False,
                'error': 'Post not found'
            }), 404

        if post['user_id'] != user_id:
            return jsonify({
                'success': False,
                'error': 'You are not authorized to update this post'
            }), 403

        # Update post
        update_data = {}
        for key in ['title', 'content', 'post_type', 'entity_type', 'location', 'company', 'position',
                   'salary_range', 'contact_info', 'tags', 'is_active']:
            if key in data:
                update_data[key] = data[key]

        success = job_post_repo.update_post(post_id, user_id, **update_data)

        if not success:
            return jsonify({
                'success': False,
                'error': 'Failed to update post'
            }), 500

        # Get updated post
        updated_post = job_post_repo.get_post_by_id(post_id)

        # Return response
        return jsonify({
            'success': True,
            'data': updated_post  # 现在 get_post_by_id 直接返回字典，不需要再调用 to_dict()
        })
    except Exception as e:
        logger.error(f"Error updating job post: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@job_board_bp.route('/api/job-board/posts/<int:post_id>', methods=['DELETE'])
@require_verified_user
def delete_job_post(post_id):
    """
    Delete a job post.

    Args:
        post_id: ID of the post

    Returns:
        JSON response with success status
    """
    try:
        # Get user ID
        user_id = get_current_user_id()

        # Get post to check if it exists and belongs to the user
        post = job_post_repo.get_post_by_id(post_id)

        if not post:
            return jsonify({
                'success': False,
                'error': 'Post not found'
            }), 404

        if post['user_id'] != user_id:
            return jsonify({
                'success': False,
                'error': 'You are not authorized to delete this post'
            }), 403

        # Delete post
        success = job_post_repo.delete_post(post_id, user_id)

        if not success:
            return jsonify({
                'success': False,
                'error': 'Failed to delete post'
            }), 500

        # Return response
        return jsonify({
            'success': True,
            'message': 'Post deleted successfully'
        })
    except sqlalchemy.exc.IntegrityError as e:
        # 处理外键约束错误
        logger.error(f"Database integrity error when deleting job post: {e}")
        if "post_id" in str(e) and "cannot be null" in str(e):
            return jsonify({
                'success': False,
                'error': 'This job post cannot be deleted because it is saved in bookmarks. Please remove all bookmarks first.'
            }), 400
        return jsonify({
            'success': False,
            'error': 'This post cannot be deleted because it is referenced by other data in the system.'
        }), 400
    except Exception as e:
        logger.error(f"Error deleting job post: {e}")
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred. Please try again later.'
        }), 500

@job_board_bp.route('/api/job-board/my-posts', methods=['GET'])
@require_verified_user
def get_my_job_posts():
    """
    Get job posts created by the current user.

    Query parameters:
        limit: Maximum number of posts to return (default: 20)
        offset: Number of posts to skip (default: 0)
        post_type: Filter by post type (job_offer, job_seeking, announcement, other)
        sort_by: Field to sort by (default: created_at)
        sort_order: Sort order (asc or desc, default: desc)

    Returns:
        JSON response with job posts and pagination info
    """
    try:
        # Get user ID
        user_id = get_current_user_id()

        # Get query parameters
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        post_type = request.args.get('post_type')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        # Get posts
        posts = job_post_repo.get_posts(
            limit=limit,
            offset=offset,
            post_type=post_type,
            user_id=user_id,
            sort_by=sort_by,
            sort_order=sort_order
        )

        # Count total posts
        total_count = 0
        # 由于 get_posts 现在直接返回字典列表，不需要再转换
        posts_data = posts

        # Return response
        return jsonify({
            'success': True,
            'data': {
                'posts': posts_data,
                'pagination': {
                    'total': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_more': offset + len(posts) < total_count
                }
            }
        })
    except Exception as e:
        logger.error(f"Error getting user's job posts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
