import logging
from typing import Dict, Any
from sqlalchemy.exc import SQLAlchemyError
from src.models.db import Article, Author, ArticleAuthor
from src.utils.db_utils import get_db_session
import datetime
import flask

logger = logging.getLogger(__name__)

class ArticleRepository:
    def get_articles(self) -> Dict[str, Any]:
        try:
            with get_db_session() as session:
                articles = session.query(Article).all()
                result = []
                for art in articles:
                    author_links = session.query(ArticleAuthor).filter(ArticleAuthor.article_id == art.id).all()
                    authors = []
                    for link in author_links:
                        author = session.query(Author).filter(Author.id == link.author_id).first()
                        if author:
                            authors.append({
                                "username": author.username,
                                "displayName": author.display_name,
                                "avatar": author.avatar,
                                "verified": author.verified,
                                "bio": author.bio,
                            })
                    result.append({
                        "id": art.id,
                        "title": art.title,
                        "content": art.content,
                        "teaser": art.teaser,
                        "publishedAt": art.published_at.isoformat() if art.published_at else None,
                        "updatedAt": art.updated_at.isoformat() if art.updated_at else None,
                        "slug": art.slug,
                        "authors": authors,
                        "viewCount": art.view_count,
                    })
                return {"success": True, "articles": result}
        except SQLAlchemyError as e:
            logger.error(f"DB error: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_article_by_slug(self, slug: str) -> Dict[str, Any]:
        try:
            with get_db_session() as session:
                art = session.query(Article).filter(Article.slug == slug).first()
                if not art:
                    return {"success": False, "error": "Article not found"}
                # 直接用 authors 字段
                authors = [a.strip() for a in (art.authors or '').split(',') if a.strip()]
                return {
                    "success": True,
                    "article": {
                        "id": art.id,
                        "title": art.title,
                        "content": art.content,
                        "teaser": art.teaser,
                        "publishedAt": art.published_at.isoformat() if art.published_at else None,
                        "updatedAt": art.updated_at.isoformat() if art.updated_at else None,
                        "slug": art.slug,
                        "authors": authors,
                        "viewCount": art.view_count,
                    }
                }
        except SQLAlchemyError as e:
            logger.error(f"DB error: {str(e)}")
            return {"success": False, "error": str(e)}

    def create_article(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with get_db_session() as session:
                title = data.get('title')
                content = data.get('content')
                teaser = data.get('teaser')
                slug = data.get('slug') or f"article-{int(datetime.datetime.now().timestamp())}"
                authors = data.get('authors', '')  # 直接存字符串
                now = datetime.datetime.now()
                article = Article(
                    title=title,
                    content=content,
                    teaser=teaser,
                    published_at=now,
                    updated_at=now,
                    slug=slug,
                    authors=authors
                )
                session.add(article)
                session.commit()
                return {"success": True, "id": article.slug}
        except Exception as e:
            logger.error(f"Create article error: {str(e)}")
            return {"success": False, "error": str(e)}

article_repo = ArticleRepository() 