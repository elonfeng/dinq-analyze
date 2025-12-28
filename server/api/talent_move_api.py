"""
人才流动API接口

提供人才流动信息的查询和新增功能
"""

from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta
import logging
import json
import hashlib
import os
import uuid
from typing import Dict, Any, List, Optional
from werkzeug.utils import secure_filename
from server.utils.auth import require_auth
from src.utils.talent_move_repository import TalentMoveRepository
from talent_transfer_agent.ai_talent_analyzer import enhance_talent_info_with_websearch

# 配置日志
logger = logging.getLogger(__name__)

def convert_linkedin_to_talent_move_format(linkedin_profile: Dict[str, Any], from_company: str, to_company: str) -> Dict[str, Any]:
    """
    将LinkedIn profile数据转换为talent_move需要的格式

    Args:
        linkedin_profile: LinkedIn profile数据
        from_company: 原公司
        to_company: 新公司

    Returns:
        转换后的talent_move格式数据
    """
    try:
        # 基础信息
        person_name = linkedin_profile.get('fullName', '')
        if not person_name:
            person_name = f"{linkedin_profile.get('firstName', '')} {linkedin_profile.get('lastName', '')}".strip()

        # 头像URL
        avatar_url = linkedin_profile.get('profilePic', '') or linkedin_profile.get('profilePicHighQuality', '')

        # 工作经历转换
        work_experience = []
        for exp in linkedin_profile.get('experiences', []):
            company_name = exp.get('subtitle', '').split('·')[0].strip() if exp.get('subtitle') else ''
            position = exp.get('title', '')
            duration = exp.get('caption', '')
            location = exp.get('metadata', '')
            company_logo = exp.get('logo', '')

            # 处理breakdown情况（多个子职位）- 只取第一个子分支
            if exp.get('breakdown') and exp.get('subComponents') and len(exp.get('subComponents', [])) > 0:
                first_sub = exp.get('subComponents', [])[0]  # 只取第一个子分支
                work_experience.append({
                    'company': company_name,
                    'position': first_sub.get('title', position),  # 使用第一个子分支的职位
                    'duration': first_sub.get('caption', duration),
                    'location': location,
                    'company_logo_url': company_logo  # 直接使用LinkedIn的logo
                })
            else:
                work_experience.append({
                    'company': company_name,
                    'position': position,
                    'duration': duration,
                    'location': location,
                    'company_logo_url': company_logo  # 直接使用LinkedIn的logo
                })

        # 教育背景转换
        education = []
        for edu in linkedin_profile.get('educations', []):
            education.append({
                'school': edu.get('title', ''),
                'degree': edu.get('subtitle', ''),
                'time': edu.get('caption', ''),
                'school_logo_url': edu.get('logo', '')  # 直接使用LinkedIn的logo
            })

        # 人才描述
        headline = linkedin_profile.get('headline', '')
        about = linkedin_profile.get('about', '')
        talent_description = headline
        if about:
            talent_description += f". {about}..."

        return {
            'person_name': person_name,
            'avatar_url': avatar_url,
            'talent_description': talent_description,
            'work_experience': json.dumps(work_experience, ensure_ascii=False),
            'education': json.dumps(education, ensure_ascii=False)
        }

    except Exception as e:
        logger.error(f"Error converting LinkedIn profile to talent move format: {e}")
        return {}

# 内存缓存类
class MemoryCache:
    def __init__(self):
        self._cache = {}
    
    def _generate_key(self, *args, **kwargs):
        """生成缓存key"""
        # 将所有参数转换为字符串并排序
        key_parts = []
        for arg in args:
            key_parts.append(str(arg))
        
        # 添加kwargs参数
        for key, value in sorted(kwargs.items()):
            key_parts.append(f"{key}:{value}")
        
        # 使用hashlib生成固定长度的key
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()
    
    def get(self, key):
        """获取缓存值"""
        if key in self._cache:
            value, expire_time = self._cache[key]
            if datetime.now() < expire_time:
                return value
            else:
                # 过期了，删除缓存
                del self._cache[key]
        return None
    
    def set(self, key, value, expire_hours=24):
        """设置缓存值"""
        expire_time = datetime.now() + timedelta(hours=expire_hours)
        self._cache[key] = (value, expire_time)
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
    
    def size(self):
        """获取缓存大小"""
        return len(self._cache)

# 创建缓存实例
cache = MemoryCache()

def get_company_logo_url(company_name):
    """获取公司logo URL"""
    if not company_name:
        return None
    
    # 转换公司名为文件名格式（小写，空格转下划线）
    filename = company_name.lower().replace(' ', '_')
    
    # 检查当前目录下的 images/company 文件夹
    import os
    import glob
    
    company_images_dir = os.path.join(os.getcwd(), 'images', 'company')
    if os.path.exists(company_images_dir):
        # 查找匹配的图片文件
        pattern = os.path.join(company_images_dir, f"{filename}.*")
        matching_files = glob.glob(pattern)
        if matching_files:
            # 获取第一个匹配的文件
            file_path = matching_files[0]
            file_name = os.path.basename(file_path)
            return f"https://api.dinq.io/images/company/{file_name}"
    
    return None

def get_school_logo_url(school_name):
    """获取学校logo URL"""
    if not school_name:
        return None
    
    # 转换学校名为文件名格式（小写，空格转下划线）
    filename = school_name.lower().replace(' ', '_')
    
    # 检查当前目录下的 images/school 文件夹
    import os
    import glob
    
    school_images_dir = os.path.join(os.getcwd(), 'images', 'school')
    if os.path.exists(school_images_dir):
        # 查找匹配的图片文件
        pattern = os.path.join(school_images_dir, f"{filename}.*")
        matching_files = glob.glob(pattern)
        if matching_files:
            # 获取第一个匹配的文件
            file_path = matching_files[0]
            file_name = os.path.basename(file_path)
            return f"https://api.dinq.io/images/school/{file_name}"
    
    return None

# 创建蓝图
talent_move_bp = Blueprint('talent_move', __name__, url_prefix='/api/talent-move')

# 创建repository实例
repo = TalentMoveRepository()

@talent_move_bp.route('/list', methods=['GET'])
def get_talent_moves():
    """
    分页查询人才流动信息
    
    Query Parameters:
    - page: 页码 (默认: 1)
    - page_size: 每页大小 (默认: 20)
    - person_name: 按人员姓名筛选
    - from_company: 按来源公司筛选
    - to_company: 按目标公司筛选
    - query: 按查询关键词筛选
    """
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        person_name = request.args.get('person_name')
        from_company = request.args.get('from_company')
        to_company = request.args.get('to_company')
        query = request.args.get('query')
        
        # 获取当前用户ID
 
        
        # 参数验证
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        
        # 生成缓存key
        cache_key = cache._generate_key(
            'list',
            page=page,
            page_size=page_size,
            person_name=person_name,
            from_company=from_company,
            to_company=to_company,
            query=query
        )
        
        # 尝试从缓存获取
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"从缓存获取人才流动列表数据: {cache_key}")
            return jsonify(cached_result)
        
        # 缓存未命中，查询数据库
        moves, total_count = repo.get_all_moves_paginated(
            page=page,
            page_size=page_size,
            person_name=person_name,
            from_company=from_company,
            to_company=to_company,
            query=query
        )
        
        # 计算分页信息
        total_pages = (total_count + page_size - 1) // page_size
        
        result = {
            'success': True,
            'data': {
                'moves': moves,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': total_pages
                }
            }
        }
        
        # 存入缓存
        cache.set(cache_key, result, expire_hours=24)
        logger.info(f"将人才流动列表数据存入缓存: {cache_key}")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting talent moves: {e}")
        return jsonify({
            'success': False,
            'error': '获取人才流动信息失败'
        }), 500

@talent_move_bp.route('/<int:move_id>', methods=['GET'])
@require_auth
def get_talent_move_by_id(move_id):
    """
    根据ID获取人才流动信息
    
    Path Parameters:
    - move_id: 记录ID
    """
    try:
        # 获取当前用户ID
        
        # 生成缓存key
        cache_key = cache._generate_key('detail', move_id=move_id)
        
        # 尝试从缓存获取
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"从缓存获取人才流动详情数据: {cache_key}")
            return jsonify(cached_result)
        
        # 缓存未命中，查询数据库
        move = repo.get_move_by_id(move_id)
        
        if move:
            result = {
                'success': True,
                'data': move
            }
            # 存入缓存
            cache.set(cache_key, result, expire_hours=24)
            logger.info(f"将人才流动详情数据存入缓存: {cache_key}")
            return jsonify(result)
        else:
            result = {
                'success': False,
                'error': '记录不存在'
            }
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"Error getting talent move by id {move_id}: {e}")
        return jsonify({
            'success': False,
            'error': '获取人才流动信息失败'
        }), 500





@talent_move_bp.route('/like/<int:move_id>', methods=['POST'])
@require_auth
def toggle_like(move_id):
    """
    切换点赞状态
    
    Path Parameters:
    - move_id: 人才流动记录ID
    """
    try:
        # 获取当前用户ID
        user_id = g.user_id
        
        # 调用repository切换点赞状态
        result = repo.toggle_like(move_id, user_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': f"已{'点赞' if result['action'] == 'liked' else '取消点赞'}",
                'data': {
                    'action': result['action'],
                    'like_count': result['like_count'],
                    'is_liked': result['is_liked']
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        logger.error(f"Error toggling like for move_id {move_id}: {e}")
        return jsonify({
            'success': False,
            'error': '点赞操作失败'
        }), 500

@talent_move_bp.route('/upload-avatar', methods=['POST'])
def upload_avatar():
    """
    上传头像图片
    
    Returns:
    - success: 是否成功
    - data: 包含avatar_url的响应数据
    """
    try:
        # 检查是否有文件
        if 'avatar' not in request.files:
            return jsonify({
                'success': False,
                'error': '没有上传文件'
            }), 400
        
        file = request.files['avatar']
        
        # 检查文件名是否为空
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': '没有选择文件'
            }), 400
        
        # 检查文件类型
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        if not ('.' in file.filename and 
                file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return jsonify({
                'success': False,
                'error': '不支持的文件类型，只支持: png, jpg, jpeg, gif, webp'
            }), 400
        
        # 确保avatar目录存在
        avatar_dir = os.path.join(os.getcwd(), 'images', 'avatar')
        os.makedirs(avatar_dir, exist_ok=True)
        
        # 生成安全的文件名
        filename = secure_filename(file.filename)
        # 添加唯一标识符避免文件名冲突
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        # 保存文件
        file_path = os.path.join(avatar_dir, unique_filename)
        file.save(file_path)
        
        # 生成访问URL
        avatar_url = f"https://api.dinq.io/images/avatar/{unique_filename}"
        
        logger.info(f"头像上传成功: {unique_filename}")
        
        return jsonify({
            'success': True,
            'data': {
                'avatar_url': avatar_url,
                'filename': unique_filename
            }
        })
        
    except Exception as e:
        logger.error(f"头像上传失败: {e}")
        return jsonify({
            'success': False,
            'error': '头像上传失败'
        }), 500

@talent_move_bp.route('/add', methods=['POST'])
def add_talent_move():
    """
    新增人才流动信息（异步处理，立即返回成功）
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400
        required_fields = ['person_name', 'from_company', 'to_company']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'字段 {field} 不能为空'
                }), 400
        # 立即返回成功响应
        resp = jsonify({'success': True, 'message': '已提交，后台异步处理'})
        # 启动后台任务
        from threading import Thread
        def async_add():
            try:
                person_name = data.get('person_name')
                from_company = data.get('from_company')
                to_company = data.get('to_company')
                salary = data.get('salary', '')
                avatar_url = data.get('avatar_url', '')  # 新增avatar_url参数
                query = data.get('query', 'dinq')  # 获取query字段，默认为dinq
                
                # 新增：LinkedIn数据获取
                linkedin_data = None
                linkedin_converted_data = {}  # 初始化为空字典
                try:
                    # 使用正确的LinkedInAnalyzer初始化方式
                    from server.api.linkedin_analyzer_api import get_linkedin_analyzer
                    linkedin_analyzer = get_linkedin_analyzer()

                    # 搜索LinkedIn URL
                    linkedin_results = linkedin_analyzer.search_linkedin_url(person_name)
                    if linkedin_results and len(linkedin_results) > 0:
                        linkedin_url = linkedin_results[0]['url']
                        # 获取LinkedIn档案数据
                        profile_data = linkedin_analyzer.get_linkedin_profile(linkedin_url)
                        if profile_data:
                            linkedin_data = profile_data
                            # 转换LinkedIn数据为talent_move格式
                            linkedin_converted_data = convert_linkedin_to_talent_move_format(
                                linkedin_data, from_company, to_company
                            )
                            logger.info(f"成功获取并转换LinkedIn数据: {person_name}")
                        else:
                            logger.warning(f"LinkedIn档案获取失败: {person_name}")
                            linkedin_converted_data = {}  # 确保有默认值
                    else:
                        logger.warning(f"未找到LinkedIn URL: {person_name}")
                        linkedin_converted_data = {}  # 确保有默认值
                except Exception as e:
                    logger.error(f"LinkedIn数据获取失败: {person_name}, 错误: {e}")
                    linkedin_converted_data = {}  # 确保有默认值
                
                # 头像获取逻辑：优先使用LinkedIn头像，其次使用用户上传的头像
                final_avatar_url = avatar_url  # 默认使用用户上传的头像
                if linkedin_converted_data.get('avatar_url'):
                    final_avatar_url = linkedin_converted_data['avatar_url']
                    logger.info(f"使用LinkedIn头像: {person_name}")
                elif avatar_url:
                    logger.info(f"使用用户上传头像: {person_name}")
                else:
                    logger.info(f"无头像数据: {person_name}")
                
                enhanced_info = enhance_talent_info_with_websearch(
                    person_name=person_name,
                    from_company=from_company,
                    to_company=to_company,
                    salary=salary,
                    tweet_text=f"{person_name} moved from {from_company} to {to_company}",
                    linkedin_data=linkedin_data
                )

                # 确保enhanced_info不为None
                if enhanced_info is None:
                    enhanced_info = {
                        'salary': salary,
                        'talent_description': f"{person_name} moved from {from_company} to {to_company}",
                        'age': 30,
                        'education': '[{"school": "Unknown University", "major": "Unknown", "time": "Unknown"}]',
                        'work_experience': f'[{{"company": "{from_company}", "position": "Unknown Position", "duration": "Unknown"}}]',
                        'major_achievement': f'[{{"title": "Career Move", "description": "{person_name} moved from {from_company} to {to_company}"}}]'
                    }
                    logger.warning(f"AI增强失败，使用默认数据: {person_name}")

                # 获取公司logo URL
                from_company_logo_url = get_company_logo_url(from_company) or ""
                to_company_logo_url = get_company_logo_url(to_company) or ""

                # 处理教育信息：优先使用LinkedIn转换数据，其次使用AI数据
                import json
                # 确保linkedin_converted_data不为None
                if linkedin_converted_data is None:
                    linkedin_converted_data = {}

                if linkedin_converted_data.get('education'):
                    education_data = linkedin_converted_data['education']
                    logger.info(f"使用LinkedIn教育数据: {person_name}")
                else:
                    # 使用AI数据并添加logo
                    education_data = enhanced_info.get('education', '[{"school": "Top University", "major": "Computer Science", "time": "2015-2019"}]')
                    try:
                        education_list = json.loads(education_data)
                        for edu in education_list:
                            if 'school' in edu:
                                school_logo_url = get_school_logo_url(edu['school'])
                                if school_logo_url:
                                    edu['school_logo_url'] = school_logo_url
                        education_data = json.dumps(education_list)
                        logger.info(f"使用AI教育数据: {person_name}")
                    except:
                        pass  # 如果JSON解析失败，保持原样

                # 处理工作经验信息：优先使用LinkedIn转换数据，其次使用AI数据
                if linkedin_converted_data.get('work_experience'):
                    work_experience_data = linkedin_converted_data['work_experience']
                    logger.info(f"使用LinkedIn工作经历数据: {person_name}")
                else:
                    # 使用AI数据并添加logo
                    work_experience_data = enhanced_info.get('work_experience', f'[{{"from": "2020", "to": "2024", "company": "{from_company}", "position": "Senior Position"}}]')
                    try:
                        work_list = json.loads(work_experience_data)
                        for work in work_list:
                            if 'company' in work:
                                company_logo_url = get_company_logo_url(work['company'])
                                if company_logo_url:
                                    work['company_logo_url'] = company_logo_url
                        work_experience_data = json.dumps(work_list)
                        logger.info(f"使用AI工作经历数据: {person_name}")
                    except:
                        pass  # 如果JSON解析失败，保持原样

                # 构建人才描述：优先使用LinkedIn转换数据
                if linkedin_converted_data.get('talent_description'):
                    talent_description = linkedin_converted_data['talent_description']
                    logger.info(f"使用LinkedIn人才描述: {person_name}")
                else:
                    talent_description = enhanced_info.get('talent_description', f"{person_name} moved from {from_company} to {to_company}")
                    logger.info(f"使用AI人才描述: {person_name}")

                move_data = {
                    "person_name": person_name,
                    "from_company": from_company,
                    "to_company": to_company,
                    "salary": enhanced_info.get('salary', salary),
                    "avatar_url": final_avatar_url,
                    "post_image_url": "",
                    "tweet_url": "",
                    "created_at": datetime.now(),
                    "query": query,
                    "talent_description": talent_description,
                    "age": enhanced_info.get('age', 30),
                    "work_experience": work_experience_data,
                    "education": education_data,
                    "major_achievement": enhanced_info.get('major_achievement', f'[{{"title": "Career Move", "description": "{person_name} moved from {from_company} to {to_company}"}}]'),
                    "from_company_logo_url": from_company_logo_url,
                    "to_company_logo_url": to_company_logo_url
                }
                repo.add_move(move_data)
                
                # 清空缓存，确保新数据能及时显示
                cache.clear()
                logger.info(f"异步添加人才流动信息: {person_name} 从 {from_company} 到 {to_company}，缓存已清空")
            except Exception as e:
                logger.error(f"异步添加人才流动信息失败: {e}")
        Thread(target=async_add).start()
        return resp
    except Exception as e:
        logger.error(f"Error adding talent move: {e}")
        return jsonify({
            'success': False,
            'error': '添加人才流动信息失败'
        }), 500

@talent_move_bp.route('/cache/status', methods=['GET'])
def get_cache_status():
    """
    获取缓存状态信息
    """
    try:
        return jsonify({
            'success': True,
            'data': {
                'cache_size': cache.size(),
                'cache_type': 'memory'
            }
        })
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        return jsonify({
            'success': False,
            'error': '获取缓存状态失败'
        }), 500

@talent_move_bp.route('/cache/clear', methods=['POST'])
def clear_cache():
    """
    清空缓存
    """
    try:
        cache.clear()
        logger.info("缓存已清空")
        return jsonify({
            'success': True,
            'message': '缓存已清空'
        })
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({
            'success': False,
            'error': '清空缓存失败'
        }), 500

# 注册蓝图
def init_app(app):
    """初始化应用"""
    app.register_blueprint(talent_move_bp) 