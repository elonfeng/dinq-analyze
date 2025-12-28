#!/usr/bin/env python
# coding: UTF-8
"""
测试 Scholar PK API
"""

import sys
import os
import json
import requests
import time

USER_ID = os.getenv("DINQ_TEST_USER_ID") or f"test_user_{int(time.time())}"

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def test_scholar_pk_api():
    """测试 Scholar PK API"""
    # API 端点
    url = "http://localhost:5001/api/scholar-pk"
    
    # 测试用例
    test_cases = [
        {
            "name": "使用 Scholar ID",
            "data": {
                "researcher1": "Y-ql3zMAAAAJ",  # Daiheng Gao
                "researcher2": "iYN86KEAAAAJ"   # Ian Goodfellow
            }
        },
        {
            "name": "使用研究者姓名",
            "data": {
                "researcher1": "Daiheng Gao",
                "researcher2": "Ian Goodfellow"
            }
        },
        {
            "name": "混合使用 ID 和姓名",
            "data": {
                "researcher1": "Y-ql3zMAAAAJ",  # Daiheng Gao
                "researcher2": "Ian Goodfellow"
            }
        }
    ]
    
    # 运行测试
    for test_case in test_cases:
        print(f"\n测试: {test_case['name']}")
        print(f"请求数据: {test_case['data']}")
        
        try:
            # 发送 POST 请求
            response = requests.post(
                url,
                json=test_case["data"],
                headers={"Userid": USER_ID},
                stream=True,
            )
            
            # 检查响应状态码
            if response.status_code == 200:
                print("请求成功，开始接收流式响应...")
                
                # 处理流式响应
                for line in response.iter_lines():
                    if line:
                        # 解析 SSE 消息
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]  # 去掉 'data: ' 前缀
                            try:
                                data = json.loads(data_str)
                                
                                # 根据消息类型处理
                                if 'type' in data:
                                    if data['type'] == 'thinkTitle':
                                        print(f"\n=== {data['content']} ===")
                                    elif data['type'] == 'thinkContent' or data['type'] == 'pkState':
                                        print(f"- {data['content']}")
                                    elif data['type'] == 'pkData':
                                        print("\n=== PK 数据 ===")
                                        pk_data = data['content']
                                        researcher1 = pk_data['researcher1']
                                        researcher2 = pk_data['researcher2']
                                        print(f"研究者 1: {researcher1['name']} (引用: {researcher1['total_citations']}, H指数: {researcher1['h_index']})")
                                        print(f"研究者 2: {researcher2['name']} (引用: {researcher2['total_citations']}, H指数: {researcher2['h_index']})")
                                        print(f"Roast: {pk_data['roast']}")
                                    elif data['type'] == 'finalContent':
                                        print("\n=== 最终结果 ===")
                                        print(data['content'])
                            except json.JSONDecodeError:
                                print(f"无法解析 JSON: {data_str}")
                
                print("\n响应结束")
            else:
                print(f"请求失败，状态码: {response.status_code}")
                print(f"错误信息: {response.text}")
        
        except Exception as e:
            print(f"发生错误: {str(e)}")
        
        # 暂停一下，避免请求过快
        time.sleep(2)

def main():
    """主函数"""
    print("\n=== Scholar PK API 测试 ===\n")
    print("确保服务器正在运行 (python -m server.app)，然后按 Enter 键继续...")
    if sys.stdin.isatty():
        input()
    else:
        print("检测到非交互环境，自动继续...\n")
    
    # 运行测试
    test_scholar_pk_api()
    
    print("\n测试完成")

if __name__ == "__main__":
    main()
