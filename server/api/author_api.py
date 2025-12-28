from flask import Blueprint, jsonify, request
from src.utils.author_repository import author_repo

# Twitter 爬虫依赖
import tweepy
import os

author_bp = Blueprint('author', __name__)

# 获取所有作者
@author_bp.route('/api/author/list', methods=['GET'])
def get_authors():
    result = author_repo.get_authors()
    return jsonify(result)

# 搜索作者，先查本地，没有再查 Twitter
@author_bp.route('/api/author/search', methods=['GET'])
def search_authors():
    query = request.args.get('query', '')
    result = author_repo.search_authors(query)
    if result.get('authors'):
        return jsonify(result)
    # 本地无结果，查 Twitter
    twitter_authors = []
    try:
        # 你需要在环境变量中配置 Twitter API key/secret/token
        client = tweepy.Client(
            bearer_token=os.environ.get('TWITTER_BEARER_TOKEN'),
            consumer_key=os.environ.get('TWITTER_API_KEY'),
            consumer_secret=os.environ.get('TWITTER_API_SECRET'),
            access_token=os.environ.get('TWITTER_ACCESS_TOKEN'),
            access_token_secret=os.environ.get('TWITTER_ACCESS_TOKEN_SECRET'),
        )
        users = client.search_users(query=query, max_results=5)
        for user in users.data:
            twitter_authors.append({
                "username": user.username,
                "display_name": user.name,
                "avatar": user.profile_image_url,
                "verified": user.verified,
                "bio": user.description,
            })
    except Exception as e:
        return jsonify({"success": False, "error": f"Twitter search failed: {str(e)}"})
    return jsonify({"success": True, "authors": twitter_authors})

# 新增作者
@author_bp.route('/api/author', methods=['POST'])
def add_author():
    data = request.get_json() or {}
    result = author_repo.add_author(data)
    return jsonify(result)

# 获取单个作者
@author_bp.route('/api/author/<int:author_id>', methods=['GET'])
def get_author(author_id):
    result = author_repo.get_author(author_id)
    return jsonify(result) 