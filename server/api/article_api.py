from flask import Blueprint, jsonify, request
from src.utils.article_repository import article_repo

article_bp = Blueprint('article', __name__)

# 获取所有文章
@article_bp.route('/api/article/list', methods=['GET'])
def get_articles():
    result = article_repo.get_articles()
    return jsonify(result)

# 获取单篇文章
@article_bp.route('/api/article/<slug>', methods=['GET'])
def get_article(slug):
    result = article_repo.get_article_by_slug(slug)
    return jsonify(result)

@article_bp.route('/api/article', methods=['POST'])
def create_article():
    data = request.get_json() or {}
    result = article_repo.create_article(data)
    return jsonify(result)

@article_bp.route('/api/article/<slug>/view', methods=['POST'])
def add_article_view(slug):
    from src.utils.db_utils import get_db_session
    from src.models.db import Article
    with get_db_session() as session:
        art = session.query(Article).filter(Article.slug == slug).first()
        if not art:
            return jsonify({"success": False, "error": "Article not found"}), 404
        art.view_count = (art.view_count or 0) + 1
        session.commit()
        return jsonify({"success": True, "viewCount": art.view_count}) 