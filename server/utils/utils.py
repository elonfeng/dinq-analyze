import re
from typing import List, Optional, Dict
from difflib import SequenceMatcher

def extract_paper_title(paper_info):
    """
    Extract the paper title from paper information.

    Args:
        paper_info: Could be a string (paper title) or a dictionary containing paper details

    Returns:
        str: Clean paper title
    """
    # Handle None input
    if paper_info is None:
        return ""

    # Handle dictionary input (from best_paper)
    if isinstance(paper_info, dict):
        title = paper_info.get('title', '')
    # Handle string input
    elif isinstance(paper_info, str):
        title = paper_info
    else:
        # Convert to string for any other type
        title = str(paper_info)

    # Split at first occurrence of '(' if exists and take the first part
    parts = title.split('(', 1)
    return parts[0].strip()


def fuzzy_match_name(name1, name_list):
    """
    模糊匹配作者名字，支持不同的名字格式

    Args:
        name1 (str): 要匹配的名字
        name_list (list): 候选名字列表或单个名字

    Returns:
        str: 最匹配的名字, 如果没有匹配则返回None
    """
    # 如果name_list是字符串，转换为列表
    if isinstance(name_list, str):
        name_list = [name_list]

    # 过滤掉无效的名字
    name_list = [name for name in name_list if name and name != "..." and name.strip() != ""]

    # 如果过滤后列表为空，返回None
    if not name_list:
        return None
    def clean_name(name):
        # 移除引用数字 [n] 和空白字符
        name = re.sub(r'\[\d+\]', '', name.strip())
        return name.lower()


    def normalize_name(name):
        # 移除多余的空格和点
        name = name.strip().replace('.', ' ').replace('  ', ' ')
        parts = name.split()

        # 提取姓氏（最后一个部分）
        last_name = parts[-1] if parts else ''

        # 提取所有首字母
        initials = ''.join(p[0].upper() for p in parts[:-1])

        # 返回标准化的信息
        return {
            'full': name.lower(),
            'last_name': last_name.lower(),
            'initials': initials,
            'first_initial': initials[0] if initials else ''
        }

    def match_score(n1, n2):
        # 如果完全相同，返回最高分
        if n1['full'] == n2['full']:
            return 100

        score = 0

        # 姓氏必须匹配
        if n1['last_name'] != n2['last_name']:
            return 0

        # 姓氏匹配加分
        score += 50

        # 检查首字母匹配
        if n1['initials'] and n2['initials']:
            # 如果都有多个首字母且匹配
            if n1['initials'] == n2['initials']:
                score += 40
            # 如果至少第一个首字母匹配
            elif n1['first_initial'] == n2['first_initial']:
                score += 30
        elif n1['first_initial'] == n2['first_initial']:
            score += 30

        return score

    if not name1 or not name_list:
        return None

    name1 = clean_name(name1)
    name1_norm = normalize_name(name1)
    best_match = None
    best_match_original = None  # 保存原始大小写的名字
    best_score = 0

    for name2 in name_list:
        if not name2:
            continue

        name2_original = name2  # 保存原始名字
        name2 = clean_name(name2)
        name2_norm = normalize_name(name2)
        score = match_score(name1_norm, name2_norm)

        if score > best_score:
            best_score = score
            best_match = name2
            best_match_original = name2_original  # 保存原始大小写

    # 只有当匹配分数超过阈值时才返回结果（返回原始大小写）
    return best_match_original if best_score >= 50 else None


def has_chinese(text):
    """
    检查文本中是否包含中文字符

    Args:
        text (str): 需要检查的文本

    Returns:
        bool: 是否包含中文字符
    """
    # 方法1：使用正则表达式
    return bool(re.search(r'[\u4e00-\u9fff]', text))

    # 方法2：使用unicode范围判断
    # for char in text:
    #     if '\u4e00' <= char <= '\u9fff':
    #         return True
    # return False

def fuzzy_match_name_improved(scholar_name: str, paper_authors: list) -> str:
    """
    改进的高精度姓名匹配方法
    
    Args:
        scholar_name: 谷歌学术上的名字 (例如: "Yang Jianchao")
        paper_authors: 论文作者列表 (例如: ["J Yang", "Y Ma"])
        
    Returns:
        str: 匹配到的作者名字，如果没有匹配则返回None
    """

    def clean_name(name: str) -> str:
        """清理和标准化姓名"""
        if not name:
            return ""
        # 移除引用标记和特殊字符
        name = re.sub(r'\[\d+\]', '', name)
        name = re.sub(r'[^a-zA-Z0-9\s.\-]', '', name)
        name = re.sub(r'\.+', '.', name)
        name = re.sub(r'\s+', ' ', name)
        return name.strip()

    def parse_name_features(name: str) -> Dict:
        """提取姓名特征"""
        cleaned = clean_name(name)
        if not cleaned:
            return {}

        # 分割姓名部分（保留点号用于识别中间名）
        raw_parts = cleaned.split()
        parts = []
        middle_names = []

        for p in raw_parts:
            if '.' in p and len(p) <= 3:  # 识别中间名，如 "Q."
                middle_char = p.replace('.', '')
                middle_names.append(middle_char)
                parts.append(middle_char)  # 保存为单字符
            elif '-' in p:
                parts.extend(p.split('-'))
            else:
                parts.append(p)

        if not parts:
            return {}

        features = {
            'original': name,
            'parts': [p.lower() for p in parts if p],  # 过滤掉空字符串
            'initials': [p[0].upper() for p in parts if p and len(p) > 0],  # 安全提取首字母
            'full_words': [p.lower() for p in parts if len(p) > 1],
            'single_chars': [p.upper() for p in parts if len(p) == 1],
            'part_count': len(parts),
            'middle_names': [m.upper() for m in middle_names]  # 新增：中间名列表，统一大写
        }

        return features

    def is_abbreviation_match(full_name_features: Dict, abbrev_features: Dict) -> bool:
        """检查是否为缩写匹配"""
        # 获取完整姓名的首字母
        full_initials = ''.join(full_name_features['initials'])
        abbrev_chars = ''.join(abbrev_features['single_chars'])

        # 检查缩写是否是完整姓名首字母的子串
        if abbrev_chars in full_initials:
            # 检查是否有共同的完整单词（通常是姓氏）
            common_words = set(full_name_features['full_words']) & set(abbrev_features['full_words'])
            return len(common_words) > 0

        return False

    def is_middle_name_abbreviation(full_name_features: Dict, abbrev_features: Dict) -> bool:
        """检查中间名缩写匹配"""
        # 获取完整姓名的首字母
        full_initials = ''.join(full_name_features['initials'])
        abbrev_chars = ''.join(abbrev_features['single_chars'])

        # 检查缩写是否是完整姓名首字母的子串
        if abbrev_chars in full_initials:
            # 检查是否有共同的完整单词（通常是姓氏）
            common_words = set(full_name_features['full_words']) & set(abbrev_features['full_words'])
            return len(common_words) > 0

        return False

    def calculate_precision_score(f1: Dict, f2: Dict) -> float:
        """计算匹配分数"""
        if not f1 or not f2:
            return 0.0

        score = 0.0
        max_score = 100  # 降低总分，提高比例

        # 1. 完全匹配检查
        parts1_set = set(f1['parts'])
        parts2_set = set(f2['parts'])
        if parts1_set == parts2_set:
            return 1.0

        # 2. 缩写匹配检查
        if is_abbreviation_match(f1, f2) or is_abbreviation_match(f2, f1):
            return 0.85  # 直接返回高分

        # 3. 常规匹配逻辑
        # 完整单词匹配
        word_score = 0
        if f1['full_words'] and f2['full_words']:
            full_word_overlap = len(set(f1['full_words']).intersection(set(f2['full_words'])))
            total_full_words = len(set(f1['full_words']).union(set(f2['full_words'])))
            if total_full_words > 0:
                word_score = 40 * (full_word_overlap / total_full_words)

        score += word_score

        # 首字母匹配
        initials1 = set(f1['initials'])
        initials2 = set(f2['initials'])
        initial_score = 0

        if initials1 and initials2:
            initial_overlap = len(initials1.intersection(initials2))
            total_initials = max(len(initials1), len(initials2))
            initial_score = 30 * (initial_overlap / total_initials)

        score += initial_score

        # 结构一致性
        structure_score = 0
        if f1['part_count'] == f2['part_count']:
            structure_score = 10
        elif abs(f1['part_count'] - f2['part_count']) == 1:
            structure_score = 5

        score += structure_score

        final_score = score / max_score if max_score > 0 else 0.0

        return final_score

    # 主匹配逻辑
    if not scholar_name or not paper_authors:
        return None

    # 获取目标作者的特征
    target_features = parse_name_features(scholar_name)
    if not target_features:
        return None

    best_match = None
    best_score = 0.0

    # 遍历所有作者，找到最佳匹配
    for author in paper_authors:
        author_features = parse_name_features(author)
        if not author_features:
            continue

        score = calculate_precision_score(target_features, author_features)

        # 更新最佳匹配
        if score > best_score:
            best_score = score
            best_match = author

    # 只有当匹配分数超过阈值时才返回结果
    return best_match if best_score >= 0.5 else None

def test_fuzzy_match_name_improved():
    """测试名字匹配功能"""
    test_cases = [
        # 中间名缩写匹配
        ("Yang Jianchao", ["J Yan", "A Lo", "J Yang"]),
        ("Albert Q. Jiang", ["AQ Jiang", "A Lo", "W Li"]),
        ("Minh P. Vo", ["MP Vo", "J Smith", "K Lee"]),
        ("Diederik P. Kingma", ["DP Kingma", "J Doe"]),
        ("Michael U. Gutmann", ["MU Gutmann", "A Smith"]),

        # 双名字缩写匹配
        ("Jong Wook Kim", ["JW Kim", "H Park", "S Lee"]),
        ("Chieh-Hsin Lai", ["CH Lai", "B Zhang"]),
        ("Patrick von Platen", ["PV Platen", "P Platen"]),

        # 简单首字母缩写匹配
        ("Daiheng Gao", ["D Gao", "DH Gao", "A Li"]),
        ("Wenxuan Tan", ["W Tan", "WX Tan", "B Liu"]),
        ("Hugo Touvron", ["H Touvron", "HT Touvron", "C Wang"]),
        ("Shilin Lu", ["S Lu", "SL Lu", "M Chen"]),
        ("Jing Yang", ["J Yang", "JY Yang", "X Zhou"]),
        ("Yao Feng", ["Y Feng", "YF Feng", "L Wang"]),
        ("Thomas Wolf", ["T Wolf", "TW Wolf", "R Smith"]),
        ("Andrew Ng", ["A Ng", "AN Ng", "B Johnson"]),
        ("Andrej Karpathy", ["A Karpathy", "AK Karpathy", "D Brown"]),
        ("Jonathan Ho", ["J Ho", "JH Ho", "P Davis"]),
        ("Qixing Huang", ["Q Huang", "QX Huang", "S Miller"]),
        ("Minhyuk Sung", ["M Sung", "MH Sung", "T Wilson"]),
        ("Taiji Suzuki", ["T Suzuki", "TS Suzuki", "K Moore"]),

        # 复杂姓名匹配
        ("Vasileios Choutas", ["V Choutas", "VC Choutas", "Vasileios C"]),
        ("Angjoo Kanazawa", ["A Kanazawa", "AK Kanazawa", "Angjoo K"]),
        ("Christoph Lassner", ["C Lassner", "CL Lassner", "Christoph L"]),
        ("Miika Aittala", ["M Aittala", "MA Aittala", "Miika A"]),
        ("Anastasia Dubrovina", ["A Dubrovina", "AD Dubrovina", "Anastasia D"]),
        ("Aapo Hyvärinen", ["A Hyvärinen", "AH Hyvärinen", "Aapo H"]),
        ("Urs Köster", ["U Köster", "UK Köster", "Urs K"]),

        # 带特殊标记的姓名
        ("Ping Luo (羅平)", ["P Luo", "PL Luo", "Ping Luo"]),
        ("Zhanpeng Zhang (张展鹏)", ["Z Zhang", "ZP Zhang", "Zhanpeng Zhang"]),
        ("Wei Liu, AAAS/IEEE/IAPR Fellow", ["W Liu", "WL Liu", "Wei Liu"]),

        # 实际论文场景模拟
        ("Albert Q. Jiang", ["A Lo", "AQ Jiang", "W Li", "M Jamnik"]),
        ("Jong Wook Kim", ["S Park", "JW Kim", "H Lee", "K Choi"]),
        ("Thomas Wolf", ["P Miller", "T Wolf", "A Davis", "B Wilson"]),
        ("Diederik P. Kingma", ["M Taylor", "DP Kingma", "S Anderson", "L White"]),

        # 边界情况和顺序问题
        ("Jing Yang", ["Yang J", "Y Jing", "J Yang"]),
        ("Yao Feng", ["Feng Y", "F Yao", "Y Feng"]),
        ("Hugo Touvron", ["H Touvron", "Hugo T", "HT Touvron"]),

        # 不应该匹配的情况
        ("Albert Q. Jiang", ["B Smith", "C Johnson", "D Brown"]),
        ("Jong Wook Kim", ["JH Park", "SW Lee", "KW Choi"]),
        ("Thomas Wolf", ["T Williams", "W Thomas", "Tom Wolf"]),
    ]

    for target_name, author_list in test_cases:
        print(f"\n目标作者: {target_name}")
        print(f"作者列表: {author_list}")
        result = fuzzy_match_name_improved(target_name, author_list)
        print(f"匹配结果: {result}")
        print("-" * 50)

if __name__ == "__main__":
    test_fuzzy_match_name_improved()