# coding: utf-8
"""
    @date: 2025-04-10
    @author: sam
    @func: 处理用户输入的scholar信息，可以是人名机构、scholar id或完整url
"""

import re
import os
from typing import Union, Tuple


def filter_user_input(user_input: str) -> Union[str, Tuple[str, bool]]:
    """
    处理用户输入的scholar信息:
    1. 如果是人名和机构，返回(输入内容, True)
    2. 如果是scholar id，直接返回id
    3. 如果是完整url，提取并返回user id

    Args:
        user_input (str): 用户输入的信息

    Returns:
        Union[str, Tuple[str, bool]]: 
        - 如果是scholar id或url，返回scholar id字符串
        - 如果是姓名机构，返回(输入内容, True)的元组
    """
    
    # 如果是完整的Google Scholar URL
    if re.match(r'https://scholar.google.com/citations\?user=', user_input):
        # 提取user=和&之间的内容
        match = re.search(r'user=([^&]+)', user_input)
        return match.group(1) if match else user_input, False
    
    # 如果只是scholar id (通常是字母数字组合加连字符，以AAAAJ结尾)
    elif re.match(r'^[a-zA-Z0-9_-]+AAAAJ$', user_input):
        return user_input, False
    
    # 其他情况（人名和机构）返回元组
    else:
        return user_input, True


if __name__ == "__main__":
    # URL格式
    input1 = "https://scholar.google.com/citations?user=y1vvxWYAAAAJ&hl=en&oi=ao"
    print("URL输入:", filter_user_input(input1))  # 输出: y1vvxWYAAAAJ

    # Scholar ID格式
    input2 = "Y-ql3zMAAAAJ"
    print("ID输入:", filter_user_input(input2))  # 输出: Y-ql3zMAAAAJ

    # 人名和机构
    input3 = "John Smith, Stanford University"
    print("姓名机构输入:", filter_user_input(input3)[0], filter_user_input(input3)[1])  # 输出: ('John Smith, Stanford University', True)
