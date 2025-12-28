import logging
from typing import Dict, Any
from sqlalchemy.exc import SQLAlchemyError
from src.models.db import Author
from src.utils.db_utils import get_db_session

logger = logging.getLogger(__name__)

class AuthorRepository:
    def get_authors(self) -> Dict[str, Any]:
        try:
            with get_db_session() as session:
                authors = session.query(Author).all()
                author_list = [
                    {
                        "id": a.id,
                        "username": a.username,
                        "display_name": a.display_name,
                        "avatar": a.avatar,
                        "verified": a.verified,
                        "bio": a.bio,
                    }
                    for a in authors
                ]
                return {"success": True, "authors": author_list}
        except SQLAlchemyError as e:
            logger.error(f"DB error: {str(e)}")
            return {"success": False, "error": str(e)}

    def search_authors(self, query: str) -> Dict[str, Any]:
        try:
            with get_db_session() as session:
                q = f"%{query}%"
                authors = session.query(Author).filter(
                    (Author.username.ilike(q)) | (Author.display_name.ilike(q))
                ).all()
                author_list = [
                    {
                        "id": a.id,
                        "username": a.username,
                        "display_name": a.display_name,
                        "avatar": a.avatar,
                        "verified": a.verified,
                        "bio": a.bio,
                    }
                    for a in authors
                ]
                return {"success": True, "authors": author_list}
        except SQLAlchemyError as e:
            logger.error(f"DB error: {str(e)}")
            return {"success": False, "error": str(e)}

    def add_author(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with get_db_session() as session:
                author = Author(
                    username=data.get('username'),
                    display_name=data.get('display_name'),
                    avatar=data.get('avatar'),
                    verified=data.get('verified', False),
                    bio=data.get('bio', '')
                )
                session.add(author)
                session.commit()
                return {"success": True, "author_id": author.id}
        except SQLAlchemyError as e:
            logger.error(f"DB error: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_author(self, author_id: int) -> Dict[str, Any]:
        try:
            with get_db_session() as session:
                author = session.query(Author).filter(Author.id == author_id).first()
                if not author:
                    return {"success": False, "error": "Author not found"}
                return {
                    "success": True,
                    "author": {
                        "id": author.id,
                        "username": author.username,
                        "display_name": author.display_name,
                        "avatar": author.avatar,
                        "verified": author.verified,
                        "bio": author.bio,
                    }
                }
        except SQLAlchemyError as e:
            logger.error(f"DB error: {str(e)}")
            return {"success": False, "error": str(e)}

author_repo = AuthorRepository() 