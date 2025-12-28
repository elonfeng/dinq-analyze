"""
Job Board User Interactions API

This module provides API endpoints for user interactions with job posts,
such as likes and bookmarks.
"""

import logging
from flask import Blueprint, request, jsonify, g

from server.utils.auth import require_verified_user
from server.utils.user_utils import get_current_user_id
from src.utils.user_interactions_repository import job_post_like_repo, job_post_bookmark_repo
from src.utils.job_board_repository import job_post_repo

# 创建蓝图
job_board_interactions_bp = Blueprint('job_board_interactions', __name__)

# 配置日志
logger = logging.getLogger(__name__)

@job_board_interactions_bp.route('/api/job-board/posts/<int:post_id>/like', methods=['POST'])
@require_verified_user
def like_post(post_id):
    """
    Like a job post.

    Args:
        post_id: ID of the post to like

    Returns:
        JSON response with success status
    """
    try:
        # 获取当前用户ID
        user_id = get_current_user_id()
        
        # 添加点赞
        result = job_post_like_repo.like_post(user_id, post_id)
        
        if result:
            # 获取帖子的点赞数
            like_count = job_post_like_repo.count_post_likes(post_id)
            
            return jsonify({
                'success': True,
                'message': 'Post liked successfully',
                'data': {
                    'post_id': post_id,
                    'like_count': like_count,
                    'is_liked': True
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to like post'
            }), 400
    except Exception as e:
        logger.error(f"Error liking post: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }), 500

@job_board_interactions_bp.route('/api/job-board/posts/<int:post_id>/like', methods=['DELETE'])
@require_verified_user
def unlike_post(post_id):
    """
    Unlike a job post.

    Args:
        post_id: ID of the post to unlike

    Returns:
        JSON response with success status
    """
    try:
        # 获取当前用户ID
        user_id = get_current_user_id()
        
        # 移除点赞
        result = job_post_like_repo.unlike_post(user_id, post_id)
        
        if result:
            # 获取帖子的点赞数
            like_count = job_post_like_repo.count_post_likes(post_id)
            
            return jsonify({
                'success': True,
                'message': 'Post unliked successfully',
                'data': {
                    'post_id': post_id,
                    'like_count': like_count,
                    'is_liked': False
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to unlike post'
            }), 400
    except Exception as e:
        logger.error(f"Error unliking post: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }), 500

@job_board_interactions_bp.route('/api/job-board/posts/<int:post_id>/bookmark', methods=['POST'])
@require_verified_user
def bookmark_post(post_id):
    """
    Bookmark a job post.

    Args:
        post_id: ID of the post to bookmark

    Returns:
        JSON response with success status
    """
    try:
        # 获取当前用户ID
        user_id = get_current_user_id()
        
        # 获取请求数据
        data = request.json or {}
        notes = data.get('notes')
        
        # 添加收藏
        result = job_post_bookmark_repo.bookmark_post(user_id, post_id, notes)
        
        if result:
            return jsonify({
                'success': True,
                'message': 'Post bookmarked successfully',
                'data': {
                    'post_id': post_id,
                    'is_bookmarked': True,
                    'notes': notes
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to bookmark post'
            }), 400
    except Exception as e:
        logger.error(f"Error bookmarking post: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }), 500

@job_board_interactions_bp.route('/api/job-board/posts/<int:post_id>/bookmark', methods=['DELETE'])
@require_verified_user
def remove_bookmark(post_id):
    """
    Remove a bookmark from a job post.

    Args:
        post_id: ID of the post to remove from bookmarks

    Returns:
        JSON response with success status
    """
    try:
        # 获取当前用户ID
        user_id = get_current_user_id()
        
        # 移除收藏
        result = job_post_bookmark_repo.remove_bookmark(user_id, post_id)
        
        if result:
            return jsonify({
                'success': True,
                'message': 'Bookmark removed successfully',
                'data': {
                    'post_id': post_id,
                    'is_bookmarked': False
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to remove bookmark'
            }), 400
    except Exception as e:
        logger.error(f"Error removing bookmark: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }), 500

@job_board_interactions_bp.route('/api/job-board/posts/<int:post_id>/bookmark/notes', methods=['PUT'])
@require_verified_user
def update_bookmark_notes(post_id):
    """
    Update notes for a bookmarked post.

    Args:
        post_id: ID of the bookmarked post

    Returns:
        JSON response with success status
    """
    try:
        # 获取当前用户ID
        user_id = get_current_user_id()
        
        # 获取请求数据
        data = request.json
        if not data or 'notes' not in data:
            return jsonify({
                'success': False,
                'message': 'Notes are required'
            }), 400
        
        notes = data['notes']
        
        # 更新收藏备注
        result = job_post_bookmark_repo.update_bookmark_notes(user_id, post_id, notes)
        
        if result:
            return jsonify({
                'success': True,
                'message': 'Bookmark notes updated successfully',
                'data': {
                    'post_id': post_id,
                    'notes': notes
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to update bookmark notes'
            }), 400
    except Exception as e:
        logger.error(f"Error updating bookmark notes: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }), 500

@job_board_interactions_bp.route('/api/job-board/posts/<int:post_id>/status', methods=['GET'])
@require_verified_user
def get_post_interaction_status(post_id):
    """
    Get the interaction status of a post for the current user.

    Args:
        post_id: ID of the post

    Returns:
        JSON response with interaction status
    """
    try:
        # 获取当前用户ID
        user_id = get_current_user_id()
        
        # 检查帖子是否存在
        post = job_post_repo.get_post_by_id(post_id)
        if not post:
            return jsonify({
                'success': False,
                'message': 'Post not found'
            }), 404
        
        # 获取交互状态
        is_liked = job_post_like_repo.is_post_liked(user_id, post_id)
        is_bookmarked = job_post_bookmark_repo.is_post_bookmarked(user_id, post_id)
        like_count = job_post_like_repo.count_post_likes(post_id)
        
        return jsonify({
            'success': True,
            'data': {
                'post_id': post_id,
                'is_liked': is_liked,
                'is_bookmarked': is_bookmarked,
                'like_count': like_count
            }
        })
    except Exception as e:
        logger.error(f"Error getting post interaction status: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }), 500

@job_board_interactions_bp.route('/api/job-board/my-liked-posts', methods=['GET'])
@require_verified_user
def get_my_liked_posts():
    """
    Get posts liked by the current user.

    Returns:
        JSON response with liked posts
    """
    try:
        # 获取当前用户ID
        user_id = get_current_user_id()
        
        # 获取分页参数
        limit = request.args.get('limit', default=20, type=int)
        offset = request.args.get('offset', default=0, type=int)
        
        # 获取用户点赞的帖子
        posts = job_post_like_repo.get_user_liked_posts(user_id, limit, offset)
        
        return jsonify({
            'success': True,
            'data': {
                'posts': posts,
                'pagination': {
                    'limit': limit,
                    'offset': offset
                }
            }
        })
    except Exception as e:
        logger.error(f"Error getting liked posts: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }), 500

@job_board_interactions_bp.route('/api/job-board/my-bookmarked-posts', methods=['GET'])
@require_verified_user
def get_my_bookmarked_posts():
    """
    Get posts bookmarked by the current user.

    Returns:
        JSON response with bookmarked posts
    """
    try:
        # 获取当前用户ID
        user_id = get_current_user_id()
        
        # 获取分页参数
        limit = request.args.get('limit', default=20, type=int)
        offset = request.args.get('offset', default=0, type=int)
        
        # 获取用户收藏的帖子
        posts = job_post_bookmark_repo.get_user_bookmarked_posts(user_id, limit, offset)
        total_count = job_post_bookmark_repo.count_user_bookmarks(user_id)
        
        return jsonify({
            'success': True,
            'data': {
                'posts': posts,
                'pagination': {
                    'total': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_more': offset + len(posts) < total_count
                }
            }
        })
    except Exception as e:
        logger.error(f"Error getting bookmarked posts: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }), 500
