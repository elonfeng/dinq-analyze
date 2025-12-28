import logging
from src.models.db import TalentMove, TalentMoveLike
from src.utils.db_utils import get_db_session
from sqlalchemy import desc, and_, or_, func
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class TalentMoveRepository:
    def add_move(self, move_data: dict):
        try:
            with get_db_session() as session:
                person_name = move_data.get('person_name', '')
                
                # 根据person_name查找最新记录
                from datetime import datetime, timedelta
                
                latest_move = session.query(TalentMove).filter_by(
                    person_name=person_name
                ).order_by(TalentMove.created_at.desc()).first()
                
                if latest_move:
                    # 计算新记录的created_at和数据库最新记录的created_at的差值
                    new_created_at = move_data.get('created_at')
                    if new_created_at:
                        time_diff = new_created_at - latest_move.created_at
                        if time_diff.days <= 30:
                            # 相距1个月以内，只更新那些传入值不为空的字段
                            update_fields = {}
                            for key, value in move_data.items():
                                if key in ['person_name', 'from_company', 'to_company', 'salary', 'talent_description', 'avatar_url','post_image_url','tweet_url', 'query', 'age', 'work_experience', 'education', 'major_achievement']:
                                    if value and value != '':
                                        update_fields[key] = value
                                elif key == 'created_at':
                                    # created_at是DateTime类型，只要传入的值不为空就更新
                                    if value:
                                        update_fields[key] = value
                            
                            if update_fields:
                                for key, value in update_fields.items():
                                    setattr(latest_move, key, value)
                                session.commit()
                            return
                
                # 没有找到记录或相距超过1个月，创建新记录
                if person_name:
                    # 移除 id 字段，让数据库自动生成
                    move_data_without_id = {k: v for k, v in move_data.items() if k != 'id'}
                    move = TalentMove(**move_data_without_id)
                    session.add(move)
                    session.commit()
         
        except Exception as e:
            logger.error(f"Error adding talent move: {e}")

    def get_last_tweet_time(self, query: str):
        with get_db_session() as session:
            last = session.query(TalentMove).filter(TalentMove.query==query).order_by(TalentMove.created_at.desc()).first()
            return last.created_at if last else None
    
    def get_all_moves_paginated(self, page: int = 1, page_size: int = 20, 
                               person_name: Optional[str] = None,
                               from_company: Optional[str] = None,
                               to_company: Optional[str] = None,
                               query: Optional[str] = None,
                               user_id: Optional[str] = None) -> Tuple[List[Dict], int]:
        """
        分页查询人才流动信息
        
        Args:
            page: 页码，从1开始
            page_size: 每页大小
            person_name: 按人员姓名筛选
            from_company: 按来源公司筛选
            to_company: 按目标公司筛选
            query: 按查询关键词筛选
            user_id: 当前用户ID（用于获取点赞状态）
            
        Returns:
            Tuple[List[Dict], int]: (数据列表, 总记录数)
        """
        try:
            with get_db_session() as session:
                # 构建查询条件
                filters = []
                if person_name:
                    filters.append(TalentMove.person_name.ilike(f"%{person_name}%"))
                if from_company:
                    filters.append(TalentMove.from_company.ilike(f"%{from_company}%"))
                if to_company:
                    filters.append(TalentMove.to_company.ilike(f"%{to_company}%"))
                if query:
                    filters.append(TalentMove.query.ilike(f"%{query}%"))
                
                # 构建查询
                query_obj = session.query(TalentMove)
                if filters:
                    query_obj = query_obj.filter(and_(*filters))
                
                # 获取总记录数
                # total_count = query_obj.count()
                total_count = 0
                
                # 分页查询
                offset = (page - 1) * page_size
                moves = query_obj.order_by(desc(TalentMove.created_at)).offset(offset).limit(page_size).all()
                
                # 转换为字典列表
                result = []
                for move in moves:
                    move_dict = {
                        'id': move.id,
                        'person_name': move.person_name,
                        'from_company': move.from_company,
                        'to_company': move.to_company,
                        'salary': move.salary,
                        'avatar_url': move.avatar_url,
                        'post_image_url': move.post_image_url,
                        'tweet_url': move.tweet_url,
                        'query': move.query,
                        'created_at': move.created_at.isoformat() if move.created_at else None,
                        'talent_description': move.talent_description,
                        'age': move.age,
                        'work_experience': move.work_experience,
                        'education': move.education,
                        'major_achievement': move.major_achievement,
                        'like': move.like_count or 0,  # 直接使用冗余字段
                        'from_company_logo_url': move.from_company_logo_url,
                        'to_company_logo_url': move.to_company_logo_url
                    }
                    result.append(move_dict)
                
                # 添加点赞信息
                # result = self._add_like_info_to_moves(result, user_id)
                
                return result, total_count
                
        except Exception as e:
            logger.error(f"Error getting paginated moves: {e}")
            return [], 0
    
    def get_latest_move_by_person(self, person_name: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """
        获取指定人员的最新人才流动信息
        
        Args:
            person_name: 人员姓名
            user_id: 当前用户ID（用于获取点赞状态）
            
        Returns:
            Optional[Dict]: 最新的人才流动信息，如果没有则返回None
        """
        try:
            with get_db_session() as session:
                move = session.query(TalentMove).filter(
                    TalentMove.person_name.ilike(f"%{person_name}%")
                ).order_by(desc(TalentMove.created_at)).first()
                
                if move:
                    move_dict = {
                        'id': move.id,
                        'person_name': move.person_name,
                        'from_company': move.from_company,
                        'to_company': move.to_company,
                        'salary': move.salary,
                        'avatar_url': move.avatar_url,
                        'post_image_url': move.post_image_url,
                        'tweet_url': move.tweet_url,
                        'query': move.query,
                        'created_at': move.created_at.isoformat() if move.created_at else None,
                        'talent_description': move.talent_description,
                        'age': move.age,
                        'work_experience': move.work_experience,
                        'education': move.education,
                        'major_achievement': move.major_achievement,
                        'like': move.like_count or 0,  # 直接使用冗余字段
                        'from_company_logo_url': move.from_company_logo_url,
                        'to_company_logo_url': move.to_company_logo_url
                    }
                    
                    # 添加点赞信息
                    move_dict = self._add_like_info_to_moves([move_dict], user_id)[0]
                    return move_dict
                return None
                
        except Exception as e:
            logger.error(f"Error getting latest move for person {person_name}: {e}")
            return None
    
    def get_move_by_id(self, move_id: int, user_id: Optional[str] = None) -> Optional[Dict]:
        """
        根据ID获取人才流动信息
        
        Args:
            move_id: 记录ID
            user_id: 当前用户ID（用于获取点赞状态）
            
        Returns:
            Optional[Dict]: 人才流动信息，如果没有则返回None
        """
        try:
            with get_db_session() as session:
                move = session.query(TalentMove).filter(TalentMove.id == move_id).first()
                
                if move:
                    move_dict = {
                        'id': move.id,
                        'person_name': move.person_name,
                        'from_company': move.from_company,
                        'to_company': move.to_company,
                        'salary': move.salary,
                        'avatar_url': move.avatar_url,
                        'post_image_url': move.post_image_url,
                        'tweet_url': move.tweet_url,
                        'query': move.query,
                        'created_at': move.created_at.isoformat() if move.created_at else None,
                        'talent_description': move.talent_description,
                        'age': move.age,
                        'work_experience': move.work_experience,
                        'education': move.education,
                        'major_achievement': move.major_achievement,
                        'like': move.like_count or 0,  # 直接使用冗余字段
                        'from_company_logo_url': move.from_company_logo_url,
                        'to_company_logo_url': move.to_company_logo_url
                    }
                    
                    # 添加点赞信息
                    # move_dict = self._add_like_info_to_moves([move_dict], user_id)[0]
                    return move_dict
                return None
                
        except Exception as e:
            logger.error(f"Error getting move by id {move_id}: {e}")
            return None
    
    def search_moves(self, keyword: str, page: int = 1, page_size: int = 20, user_id: Optional[str] = None) -> Tuple[List[Dict], int]:
        """
        搜索人才流动信息
        
        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页大小
            user_id: 当前用户ID（用于获取点赞状态）
            
        Returns:
            Tuple[List[Dict], int]: (数据列表, 总记录数)
        """
        try:
            with get_db_session() as session:
                # 构建搜索条件
                search_filter = or_(
                    TalentMove.person_name.ilike(f"%{keyword}%"),
                    TalentMove.from_company.ilike(f"%{keyword}%"),
                    TalentMove.to_company.ilike(f"%{keyword}%"),
                    TalentMove.talent_description.ilike(f"%{keyword}%"),
                    TalentMove.query.ilike(f"%{keyword}%")
                )
                
                # 构建查询
                query_obj = session.query(TalentMove).filter(search_filter)
                
                # 获取总记录数
                total_count = query_obj.count()
                
                # 分页查询
                offset = (page - 1) * page_size
                moves = query_obj.order_by(desc(TalentMove.created_at)).offset(offset).limit(page_size).all()
                
                # 转换为字典列表
                result = []
                for move in moves:
                    move_dict = {
                        'id': move.id,
                        'person_name': move.person_name,
                        'from_company': move.from_company,
                        'to_company': move.to_company,
                        'salary': move.salary,
                        'avatar_url': move.avatar_url,
                        'post_image_url': move.post_image_url,
                        'tweet_url': move.tweet_url,
                        'query': move.query,
                        'created_at': move.created_at.isoformat() if move.created_at else None,
                        'talent_description': move.talent_description,
                        'age': move.age,
                        'work_experience': move.work_experience,
                        'education': move.education,
                        'major_achievement': move.major_achievement,
                        'like': move.like_count or 0,  # 直接使用冗余字段
                        'from_company_logo_url': move.from_company_logo_url,
                        'to_company_logo_url': move.to_company_logo_url
                    }
                    result.append(move_dict)
                
                # 添加点赞信息
                result = self._add_like_info_to_moves(result, user_id)
                
                return result, total_count
                
        except Exception as e:
            logger.error(f"Error searching moves with keyword {keyword}: {e}")
            return [], 0
    
    def get_statistics(self) -> Dict:
        """
        获取人才流动统计信息
        
        Returns:
            Dict: 统计信息
        """
        try:
            with get_db_session() as session:
                # 总记录数
                total_count = session.query(TalentMove).count()
                
                # 按公司统计
                from_company_stats = session.query(
                    TalentMove.from_company, 
                    session.query(TalentMove).filter(TalentMove.from_company == TalentMove.from_company).count()
                ).group_by(TalentMove.from_company).all()
                
                to_company_stats = session.query(
                    TalentMove.to_company, 
                    session.query(TalentMove).filter(TalentMove.to_company == TalentMove.to_company).count()
                ).group_by(TalentMove.to_company).all()
                
                return {
                    'total_moves': total_count,
                    'from_company_stats': dict(from_company_stats),
                    'to_company_stats': dict(to_company_stats)
                }
                
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                'total_moves': 0,
                'from_company_stats': {},
                'to_company_stats': {}
            } 
    
    def toggle_like(self, talent_move_id: int, user_id: str) -> Dict:
        """
        切换点赞状态
        
        Args:
            talent_move_id: 人才流动记录ID
            user_id: 用户ID
            
        Returns:
            Dict: 包含操作结果和点赞状态
        """
        try:
            with get_db_session() as session:
                # 检查记录是否存在
                talent_move = session.query(TalentMove).filter(TalentMove.id == talent_move_id).first()
                if not talent_move:
                    return {
                        'success': False,
                        'error': '记录不存在'
                    }
                
                # 检查是否已经点赞
                existing_like = session.query(TalentMoveLike).filter(
                    and_(
                        TalentMoveLike.talent_move_id == talent_move_id,
                        TalentMoveLike.user_id == user_id
                    )
                ).first()
                
                if existing_like:
                    # 取消点赞
                    session.delete(existing_like)
                    # 减少点赞数量
                    talent_move.like_count = max(0, talent_move.like_count - 1)
                    action = 'unliked'
                else:
                    # 添加点赞
                    new_like = TalentMoveLike(
                        talent_move_id=talent_move_id,
                        user_id=user_id
                    )
                    session.add(new_like)
                    # 增加点赞数量
                    talent_move.like_count += 1
                    action = 'liked'
                
                session.commit()
                
                return {
                    'success': True,
                    'action': action,
                    'like_count': talent_move.like_count,
                    'is_liked': action == 'liked'
                }
                
        except Exception as e:
            logger.error(f"Error toggling like for talent_move_id {talent_move_id}, user_id {user_id}: {e}")
            return {
                'success': False,
                'error': '操作失败'
            }
    
    def get_like_count(self, talent_move_id: int) -> int:
        """
        获取指定记录的点赞数
        
        Args:
            talent_move_id: 人才流动记录ID
            
        Returns:
            int: 点赞数
        """
        try:
            with get_db_session() as session:
                talent_move = session.query(TalentMove).filter(TalentMove.id == talent_move_id).first()
                return talent_move.like_count if talent_move else 0
        except Exception as e:
            logger.error(f"Error getting like count for talent_move_id {talent_move_id}: {e}")
            return 0
    
    def is_liked_by_user(self, talent_move_id: int, user_id: str) -> bool:
        """
        检查用户是否已点赞指定记录
        
        Args:
            talent_move_id: 人才流动记录ID
            user_id: 用户ID
            
        Returns:
            bool: 是否已点赞
        """
        try:
            with get_db_session() as session:
                like = session.query(TalentMoveLike).filter(
                    and_(
                        TalentMoveLike.talent_move_id == talent_move_id,
                        TalentMoveLike.user_id == user_id
                    )
                ).first()
                return like is not None
        except Exception as e:
            logger.error(f"Error checking like status for talent_move_id {talent_move_id}, user_id {user_id}: {e}")
            return False
    
    def _add_like_info_to_moves(self, moves: List[Dict], user_id: Optional[str] = None) -> List[Dict]:
        """
        为人才流动记录添加点赞信息
        
        Args:
            moves: 人才流动记录列表
            user_id: 当前用户ID（可选）
            
        Returns:
            List[Dict]: 添加了点赞信息的记录列表
        """
        try:
            if not moves:
                return moves
                
            # 如果提供了用户ID，批量查询用户点赞状态
            if user_id:
                move_ids = [move['id'] for move in moves]
                
                with get_db_session() as session:
                    # 批量查询用户点赞的记录ID
                    liked_move_ids = session.query(TalentMoveLike.talent_move_id).filter(
                        and_(
                            TalentMoveLike.talent_move_id.in_(move_ids),
                            TalentMoveLike.user_id == user_id
                        )
                    ).all()
                    
                    # 转换为set便于快速查找
                    liked_move_id_set = {row[0] for row in liked_move_ids}
                    
                    # 为每条记录设置点赞状态
                    for move in moves:
                        move['isLiked'] = move['id'] in liked_move_id_set
            else:
                # 没有用户ID，所有记录都设为未点赞
                for move in moves:
                    move['isLiked'] = False
                    
        except Exception as e:
            logger.error(f"Error adding like info to moves: {e}")
            # 出错时设置默认值
            for move in moves:
                move['isLiked'] = False
            
        return moves 
    