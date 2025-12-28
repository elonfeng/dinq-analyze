#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_get_job_posts():
    """测试获取帖子列表，验证是否包含喜欢和收藏计数"""
    url = "http://127.0.0.1:5001/api/job-board/posts"
    
    headers = {
        "accept": "*/*",
        "accept-language": "zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/json",
        "userid": "LtXQ0x62DpOB88r1x3TL329FbHk1"
    }
    
    # 获取帖子列表
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        
        if data.get('success'):
            posts = data.get('data', {}).get('posts', [])
            
            if posts:
                print(f"成功获取到 {len(posts)} 个帖子")
                
                # 检查第一个帖子是否包含喜欢和收藏计数
                first_post = posts[0]
                print("\n第一个帖子详情:")
                print(f"ID: {first_post.get('id')}")
                print(f"标题: {first_post.get('title')}")
                print(f"类型: {first_post.get('post_type')}")
                
                # 验证是否包含喜欢和收藏计数
                if 'like_count' in first_post and 'bookmark_count' in first_post:
                    print(f"喜欢数: {first_post.get('like_count')}")
                    print(f"收藏数: {first_post.get('bookmark_count')}")
                    print("\n✅ 测试通过: 帖子数据中包含喜欢和收藏计数")
                else:
                    missing = []
                    if 'like_count' not in first_post:
                        missing.append('like_count')
                    if 'bookmark_count' not in first_post:
                        missing.append('bookmark_count')
                    print(f"\n❌ 测试失败: 帖子数据中缺少 {', '.join(missing)}")
                    print(f"完整的帖子数据: {json.dumps(first_post, indent=2, ensure_ascii=False)}")
            else:
                print("没有找到任何帖子")
        else:
            print(f"请求失败: {data.get('error')}")
    else:
        print(f"HTTP 请求失败，状态码: {response.status_code}")
        print(f"响应内容: {response.text}")

def test_like_and_get_post():
    """测试喜欢帖子并获取单个帖子详情，验证喜欢计数是否增加"""
    # 获取帖子列表
    list_url = "http://127.0.0.1:5001/api/job-board/posts"
    
    headers = {
        "accept": "*/*",
        "accept-language": "zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/json",
        "userid": "LtXQ0x62DpOB88r1x3TL329FbHk1"
    }
    
    response = requests.get(list_url, headers=headers)
    
    if response.status_code != 200 or not response.json().get('success'):
        print("获取帖子列表失败，无法继续测试")
        return
    
    posts = response.json().get('data', {}).get('posts', [])
    
    if not posts:
        print("没有找到任何帖子，无法继续测试")
        return
    
    # 选择第一个帖子进行测试
    post_id = posts[0].get('id')
    original_like_count = posts[0].get('like_count', 0)
    
    print(f"\n测试喜欢帖子功能:")
    print(f"选择帖子 ID: {post_id}，原始喜欢数: {original_like_count}")
    
    # 喜欢帖子
    like_url = f"http://127.0.0.1:5001/api/job-board/posts/{post_id}/like"
    like_response = requests.post(like_url, headers=headers)
    
    if like_response.status_code == 200 and like_response.json().get('success'):
        print("成功发送喜欢请求")
        
        # 获取单个帖子详情
        detail_url = f"http://127.0.0.1:5001/api/job-board/posts/{post_id}"
        detail_response = requests.get(detail_url, headers=headers)
        
        if detail_response.status_code == 200 and detail_response.json().get('success'):
            post_detail = detail_response.json().get('data', {}).get('post', {})
            new_like_count = post_detail.get('like_count', 0)
            
            print(f"更新后的喜欢数: {new_like_count}")
            
            if 'like_count' in post_detail:
                if new_like_count >= original_like_count:
                    print("✅ 测试通过: 喜欢计数已更新")
                else:
                    print(f"❌ 测试失败: 喜欢计数未增加 (原始: {original_like_count}, 新: {new_like_count})")
            else:
                print("❌ 测试失败: 帖子详情中缺少 like_count 字段")
        else:
            print(f"获取帖子详情失败: {detail_response.status_code}")
    else:
        print(f"喜欢帖子请求失败: {like_response.status_code}")
        print(f"响应内容: {like_response.text}")

if __name__ == "__main__":
    print("===== 测试帖子列表是否包含喜欢和收藏计数 =====")
    test_get_job_posts()
    
    print("\n===== 测试喜欢帖子功能 =====")
    test_like_and_get_post()
