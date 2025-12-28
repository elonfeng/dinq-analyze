try:
    import openreview
except Exception:  # noqa: BLE001
    openreview = None
from datetime import datetime, timedelta
import json
import re
import requests
from typing import Optional

from server.utils.conference_matcher import ConferenceMatcher

# 1. 初始化客户端
client = None


def get_user_basic_info(user_id_or_email):
    client = openreview.api.OpenReviewClient(
        baseurl='https://api2.openreview.net',  # API V2
        username='samuel.gao023@gmail.com',  # 替换为你的 OpenReview 用户名
        password='Gaodh199241'
    )
    """
    获取用户基本信息
    user_id_or_email: 用户ID (如 ~FirstName_LastName1) 或邮箱
    """
    try:
        # 获取用户资料
        profile = client.get_profile(user_id_or_email)
        areas = profile.content.get('expertise')
        areas_result = []
        if areas:  # 如果 expertise 为空或不存在
            for kw_obj in areas:
                areas_result.extend(kw_obj.get('keywords', []))  # 提取 keywords 里的列
        # 基本信息
        user_info = {
            'profile_id': profile.id,
            'name': profile.content.get('names', [{}])[0].get('fullname', 'N/A'),
            'emails': profile.content.get('emails', []),
            'affiliations': profile.content.get('history', []),
            'areas': areas_result
        }

        return user_info

    except Exception as e:
        print(f"获取用户资料失败: {e}")
        return None


def parse_paper_details(note, current_user_id):
    """
    解析单篇论文的详细信息
    """
    try:
        paper_info = {
            'id': note.id,
            'title': note.content.get('title', {}).get('value', 'N/A'),
            'authors': note.content.get('authors', {}).get('value', []),
            'abstract': note.content.get('abstract', {}).get('value', 'N/A'),
            'keywords': note.content.get('keywords', {}).get('value', []),
            'venue': 'Unknown',
            'publication_date': None,
            'creation_year': None
        }

        # 解析时间
        if hasattr(note, 'cdate') and note.cdate:
            creation_timestamp = note.cdate / 1000
            creation_date = datetime.fromtimestamp(creation_timestamp)
            paper_info['publication_date'] = creation_date.strftime('%Y-%m-%d')
            paper_info['creation_year'] = creation_date.year


        matcher = ConferenceMatcher()
        venueid = note.content.get('venueid', {}).get('value',"")
        matched_conf = matcher.match_conference(venueid.lower())
        paper_info['venue'] = matched_conf



        return paper_info

    except Exception as e:
        print(f"解析论文详情失败: {e}")
        return None


def get_user_papers(user_id, limit=1000):
    """
    获取用户的论文信息 - 根据官方文档优化
    """
    try:
        print(f"🔍 正在搜索用户 {user_id} 的论文...")

        # 通过content.authorids查找
        notes_by_authorids = []
        try:
            notes_by_authorids = client.get_all_notes(
                content={'authorids': user_id}
            )
            print(f"   通过authorids找到: {len(notes_by_authorids)} 条记录")
        except Exception as e:
            print(f"   authorids查询失败: {e}")

        # 去重
        all_notes = notes_by_authorids
        seen_ids = set()
        unique_notes = []
        for note in all_notes:
            if note.id not in seen_ids:
                unique_notes.append(note)
                seen_ids.add(note.id)

        print(f"   去重后总计: {len(unique_notes)} 条记录")

        # 统计论文数据
        current_year = datetime.now().year
        one_year_ago = datetime.now() - timedelta(days=365)


        papers_last_year = 0
        accepted_papers = []
        parsed_papers = []

        for note in unique_notes:
            # 检查是否为被接受的论文
            if hasattr(note, 'content') and note.content.get('venueid'):
                venue_id = note.content.get('venueid', {}).get('value', '')
                if venue_id and 'rejected' not in venue_id.lower() and 'submission' not in venue_id.lower():
                    accepted_papers.append(note)
        total_papers = len(accepted_papers)
        for acnote in accepted_papers:
            # 检查论文创建时间
            if acnote.pdate:
                paper_date = datetime.fromtimestamp(acnote.cdate / 1000)
                if paper_date >= one_year_ago:
                    papers_last_year += 1
            # 解析论文详情
            parsed_paper = parse_paper_details(acnote, user_id)
            if parsed_paper:
                parsed_papers.append(parsed_paper)

        return {
            'total_papers': total_papers,
            'papers_last_year': papers_last_year,
            'parsed_papers': parsed_papers,
        }

    except Exception as e:
        print(f"获取论文信息失败: {e}")
        return None


def call_ai_api(prompt: str) -> Optional[str]:
    """Call AI API to get response"""
    try:
        from server.llm.gateway import openrouter_chat
        from server.config.llm_models import get_model

        content = openrouter_chat(
            task="openreview.select_paper",
            model=get_model("fast", task="openreview.select_paper"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )

        if content:
            content = str(content).strip()

            # Extract JSON from response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1

            if start_idx != -1 and end_idx > start_idx:
                return content[start_idx:end_idx]

        print("AI API call failed: empty response")
        return None

    except Exception as e:
        print(f"Error calling AI API: {e}")
        return None


def select_representative_paper_ai(papers, user_name):
    """
    使用AI选择最具代表性的论文

    Args:
        papers: 论文列表，每个论文包含以下字段:
                {
                    'id': note.id,
                    'title': str,
                    'authors': List[str],
                    'author_ids': List[str],
                    'abstract': str,
                    'keywords': List[str],
                    'venue': str,
                    'publication_date': Optional[str],
                    'creation_year': Optional[int]
                }
        user_name: 用户名

    Returns:
        JSON格式: {"index": int, "title": str, "reason": str}
        - index: 代表论文在数组中的下标
        - title: 代表论文的标题
        - reason: 选择该论文的原因
    """
    if not papers:
        return None


    # 准备论文数据供AI分析
    papers_for_ai = []
    for i, paper in enumerate(papers):
        paper_summary = {
            "index": i,
            "title": paper.get('title', 'N/A'),
            "abstract": paper.get('abstract', 'N/A')[:500] + "..." if len(
                paper.get('abstract', '')) > 500 else paper.get('abstract', 'N/A'),
            "venue": paper.get('venue', 'Unknown'),
            "publication_date": paper.get('publication_date', 'Unknown'),
            "status": paper.get('status', 'Unknown'),
            "keywords": paper.get('keywords', 'N/A'),
            "year": paper.get('creation_year', 'Unknown')
        }
        papers_for_ai.append(paper_summary)

    # 🔧 修复：改为英文prompt
    prompt = f"""
As an academic evaluation expert, please select the most representative paper from the following {len(papers_for_ai)} papers for this researcher.

Researcher Name: {user_name}

Paper List:
{json.dumps(papers_for_ai, indent=2, ensure_ascii=False)}

Please evaluate based on these criteria:
1. Academic Impact: Reputation and impact factor of the publication venue
2. Innovation: Novelty and originality of the research content
3. Technical Contribution: Advanced methodology and technical depth
4. Practical Value: Application prospects and practical significance
5. Completeness: Completeness of research work and paper quality

Please return the analysis result in JSON format:
{{
    "index": selected paper index (integer),
    "title": "exact title of the selected paper",
    "reason": "brief explanation of why this paper is most representative (2-3 sentences)"
}}
"""

    # 调用AI API
    ai_response = call_ai_api(prompt)

    if ai_response:
        try:
            analysis = json.loads(ai_response)
            selected_index = analysis.get('index', 0)
            selected_title = analysis.get('title', '')
            selection_reason = analysis.get('reason', '')

            if 0 <= selected_index < len(papers):
                print(f"   🎯 AI selected paper at index {selected_index}")
                print(f"   🏆 Title: {selected_title}")
                print(f"   💡 Reason: {selection_reason}")

                # 返回指定格式的JSON
                return {
                    "index": selected_index,
                    "title": selected_title,
                    "reason": selection_reason
                }
            else:
                print(f"   ⚠️ AI returned index {selected_index} out of range, using fallback")
        except json.JSONDecodeError as e:
            print(f"   ⚠️ AI response format error: {e}, using fallback")
    else:
        print("   ⚠️ AI API call failed, using fallback")

    # 备选方案：返回第一篇论文
    print("   🔄 Using fallback selection mechanism...")
    if papers:
        fallback_paper = papers[0]
        return {
            "index": 0,
            "title": fallback_paper.get('title', 'N/A'),
            "reason": "Selected as the first available paper due to AI analysis failure."
        }

    return None


def select_representative_paper_fallback(papers, user_name):
    """
    AI API失败时的备选方案
    """
    if not papers:
        return None

    scored_papers = []

    for paper in papers:
        score = 0
        reasons = []

        # 发表状态加分
        if paper.get('status') == 'Published':
            score += 10
            reasons.append("Published")

        # 会议质量加分
        venue = paper.get('venue', '').lower()
        top_venues = ['iclr', 'neurips', 'icml', 'aaai', 'ijcai', 'cvpr', 'iccv', 'eccv']
        for top_venue in top_venues:
            if top_venue in venue:
                score += 15
                reasons.append(f"Top venue({top_venue.upper()})")
                break

        # 摘要长度和质量
        abstract = paper.get('abstract', '')
        if abstract and abstract != 'N/A' and len(abstract) > 500:
            score += 5
            reasons.append("Detailed abstract")

        # 时间因素
        if paper.get('creation_year'):
            current_year = datetime.now().year
            year_diff = current_year - paper['creation_year']
            if year_diff <= 2:
                score += 5
                reasons.append("Recent work")

        scored_papers.append({
            'paper': paper,
            'score': score,
            'reasons': reasons
        })

    # 按分数排序
    scored_papers.sort(key=lambda x: x['score'], reverse=True)

    if scored_papers:
        best_paper = scored_papers[0]
        print(f"   📈 Fallback criteria: {', '.join(best_paper['reasons'])}")
        print(f"   🏆 Fallback representative work: {best_paper['paper']['title']}")
        return best_paper['paper']

    return papers[0] if papers else None  # 至少返回第一篇


def format_representative_paper(paper):
    """
    格式化代表作信息
    """
    if not paper:
        return "No representative work available"

    # 格式化作者列表
    authors_str = ", ".join(paper['formatted_authors'])

    # 格式化发表信息
    publication_info = []
    if paper.get('venue') and paper['venue'] != 'Unknown':
        publication_info.append(paper['venue'])
    if paper.get('publication_date'):
        publication_info.append(paper['publication_date'])

    publication_str = " | ".join(publication_info) if publication_info else "Publication info pending"

    representative_work = {
        'title': paper['title'],
        'authors': authors_str,
        'publication': publication_str,
        'status': paper.get('status', 'Unknown'),
        'abstract_preview': paper.get('abstract', 'N/A')[:200] + "..." if paper.get('abstract') and len(
            paper.get('abstract', '')) > 200 else paper.get('abstract', 'N/A'),
        'ai_analysis': paper.get('ai_analysis', {})  # 包含AI分析结果
    }

    return representative_work




def analyze_openreview_profile(user_identifier):
    """
    获取用户的综合数据
    """
    if openreview is None:
        print("OpenReview client not available; returning None")
        return None
    print(f"正在获取用户 {user_identifier} 的信息...")

    # 获取基本信息
    basic_info = get_user_basic_info(user_identifier)
    if not basic_info:
        print("❌ Failed to get basic user info")
        return None

    # 获取论文信息
    papers_info = get_user_papers(basic_info['profile_id'])
    if not papers_info:
        print("⚠️ Failed to get papers info, using empty data")
        papers_info = {
            'total_papers': 0,
            'papers_last_year': 0,
            'accepted_papers': 0,
            'parsed_papers': []
        }

    # 提取研究领域
    research_areas = basic_info['areas'][:10] if basic_info['areas'] else []


    # 选择代表作
    representative_paper = None
    if papers_info['parsed_papers']:
        try:
            selected_paper = select_representative_paper_ai(
                papers_info['parsed_papers'][:10],
                basic_info['name']
            )
            # 根据AI返回的结构化数据获取对应的论文
            if selected_paper and isinstance(selected_paper, dict) and 'index' in selected_paper:
                # AI返回了结构化数据，根据index获取对应论文
                paper_index = selected_paper.get('index', 0)
                parsed_papers = papers_info['parsed_papers']

                if 0 <= paper_index < len(parsed_papers):
                    representative_paper = parsed_papers[paper_index]
                    # 将AI的分析结果添加到论文信息中

                else:
                    representative_paper = parsed_papers[0]

            else:
                representative_paper = "No papers available"
        except Exception as e:
            print(f"⚠️ Failed to select representative paper: {e}")
            representative_paper = "Failed to select representative work"

    # 综合结果
    result = {
        'name': basic_info['name'],
        'total_papers': papers_info['total_papers'],
        'papers_last_year': papers_info['papers_last_year'],
        'expertise_areas': research_areas,
        'representative_work': representative_paper
    }

    return result
