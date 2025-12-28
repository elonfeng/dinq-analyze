#!/usr/bin/env python3
"""
测试人才流动API接口
"""

import requests
import json
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

def test_api_endpoints():
    """测试API接口"""
    base_url = "http://localhost:5001/api/talent-move"
    
    print("=== 测试人才流动API接口 ===")
    
    # 1. 测试分页查询
    print("\n1. 测试分页查询...")
    try:
        response = requests.get(f"{base_url}/list", params={
            "page": 1,
            "page_size": 5
        })
        data = response.json()
        
        if data['success']:
            print(f"✅ 分页查询成功，找到 {data['data']['pagination']['total_count']} 条记录")
            if data['data']['moves']:
                move = data['data']['moves'][0]
                print(f"   第一条记录: {move['person_name']} 从 {move['from_company']} 到 {move['to_company']}")
                print(f"   点赞数: {move.get('like', 0)}, 已点赞: {move.get('isLiked', False)}")
        else:
            print(f"❌ 分页查询失败: {data.get('error', '未知错误')}")
    except Exception as e:
        print(f"❌ 分页查询异常: {e}")
    
    # 2. 测试搜索功能
    print("\n2. 测试搜索功能...")
    try:
        response = requests.get(f"{base_url}/search", params={
            "keyword": "OpenAI",
            "page": 1,
            "page_size": 5
        })
        data = response.json()
        
        if data['success']:
            print(f"✅ 搜索成功，找到 {data['data']['pagination']['total_count']} 条相关记录")
            if data['data']['moves']:
                move = data['data']['moves'][0]
                print(f"   第一条记录点赞数: {move.get('like', 0)}, 已点赞: {move.get('isLiked', False)}")
        else:
            print(f"❌ 搜索失败: {data.get('error', '未知错误')}")
    except Exception as e:
        print(f"❌ 搜索异常: {e}")
    
    # 3. 测试统计信息
    print("\n3. 测试统计信息...")
    try:
        response = requests.get(f"{base_url}/statistics")
        data = response.json()
        
        if data['success']:
            stats = data['data']
            print(f"✅ 统计信息获取成功")
            print(f"   总记录数: {stats['total_moves']}")
            print(f"   来源公司统计: {len(stats['from_company_stats'])} 个公司")
            print(f"   目标公司统计: {len(stats['to_company_stats'])} 个公司")
        else:
            print(f"❌ 统计信息获取失败: {data.get('error', '未知错误')}")
    except Exception as e:
        print(f"❌ 统计信息异常: {e}")
    
    # 4. 测试新增功能
    print("\n4. 测试新增功能...")
    try:
        new_move = {
            "person_name": "API Test Person",
            "from_company": "Test Company A",
            "to_company": "Test Company B",
            "salary": "$400K"
        }
        
        response = requests.post(f"{base_url}/add", json=new_move)
        data = response.json()
        
        if data['success']:
            print(f"✅ 新增成功")
            print(f"   人员: {data['data']['person_name']}")
            print(f"   从: {data['data']['from_company']}")
            print(f"   到: {data['data']['to_company']}")
            print(f"   AI补充年龄: {data['data']['enhanced_info']['age']}")
        else:
            print(f"❌ 新增失败: {data.get('error', '未知错误')}")
    except Exception as e:
        print(f"❌ 新增异常: {e}")
    
    # 5. 测试根据ID查询
    print("\n5. 测试根据ID查询...")
    try:
        # 先获取第一条记录的ID
        response = requests.get(f"{base_url}/list", params={"page": 1, "page_size": 1})
        data = response.json()
        
        if data['success'] and data['data']['moves']:
            move_id = data['data']['moves'][0]['id']
            
            response = requests.get(f"{base_url}/{move_id}")
            data = response.json()
            
            if data['success']:
                print(f"✅ 根据ID查询成功")
                print(f"   记录ID: {data['data']['id']}")
                print(f"   人员: {data['data']['person_name']}")
                print(f"   点赞数: {data['data'].get('like', 0)}, 已点赞: {data['data'].get('isLiked', False)}")
            else:
                print(f"❌ 根据ID查询失败: {data.get('error', '未知错误')}")
        else:
            print("⚠️ 没有记录可以测试ID查询")
    except Exception as e:
        print(f"❌ 根据ID查询异常: {e}")
    
    # 6. 测试根据人员姓名查询
    print("\n6. 测试根据人员姓名查询...")
    try:
        # 先获取一个人员姓名
        response = requests.get(f"{base_url}/list", params={"page": 1, "page_size": 1})
        data = response.json()
        
        if data['success'] and data['data']['moves']:
            person_name = data['data']['moves'][0]['person_name']
            
            response = requests.get(f"{base_url}/person/{person_name}")
            data = response.json()
            
            if data['success']:
                print(f"✅ 根据人员姓名查询成功")
                print(f"   人员: {data['data']['person_name']}")
                print(f"   从: {data['data']['from_company']}")
                print(f"   到: {data['data']['to_company']}")
                print(f"   点赞数: {data['data'].get('like', 0)}, 已点赞: {data['data'].get('isLiked', False)}")
            else:
                print(f"❌ 根据人员姓名查询失败: {data.get('error', '未知错误')}")
        else:
            print("⚠️ 没有记录可以测试人员姓名查询")
    except Exception as e:
        print(f"❌ 根据人员姓名查询异常: {e}")

def test_like_functionality():
    """测试点赞功能"""
    base_url = "http://localhost:5001/api/talent-move"
    
    print("\n=== 测试点赞功能 ===")
    
    # 1. 测试获取记录列表（包含点赞信息）
    print("\n1. 测试获取记录列表（包含点赞信息）...")
    try:
        response = requests.get(f"{base_url}/list", params={"page": 1, "page_size": 3})
        data = response.json()
        
        if data['success'] and data['data']['moves']:
            moves = data['data']['moves']
            print(f"✅ 获取到 {len(moves)} 条记录")
            
            for i, move in enumerate(moves):
                print(f"   记录{i+1}: {move['person_name']} - 点赞数: {move.get('like', 0)}, 已点赞: {move.get('isLiked', False)}")
            
            # 选择第一条记录进行点赞测试
            test_move = moves[0]
            move_id = test_move['id']
            initial_likes = test_move.get('like', 0)
            initial_is_liked = test_move.get('isLiked', False)
            
            print(f"\n   选择记录进行点赞测试: {test_move['person_name']} (ID: {move_id})")
            print(f"   初始状态: {initial_likes} 个赞, 已点赞: {initial_is_liked}")
            
            # 2. 测试点赞
            print("\n2. 测试点赞...")
            response = requests.post(f"{base_url}/like/{move_id}")
            data = response.json()
            
            if data['success']:
                print(f"✅ 点赞成功: {data['message']}")
                print(f"   操作: {data['data']['action']}")
                print(f"   点赞数: {data['data']['like_count']}")
                print(f"   已点赞: {data['data']['is_liked']}")
                
                # 3. 测试取消点赞
                print("\n3. 测试取消点赞...")
                response = requests.post(f"{base_url}/like/{move_id}")
                data = response.json()
                
                if data['success']:
                    print(f"✅ 取消点赞成功: {data['message']}")
                    print(f"   操作: {data['data']['action']}")
                    print(f"   点赞数: {data['data']['like_count']}")
                    print(f"   已点赞: {data['data']['is_liked']}")
                else:
                    print(f"❌ 取消点赞失败: {data.get('error', '未知错误')}")
            else:
                print(f"❌ 点赞失败: {data.get('error', '未知错误')}")
        else:
            print("⚠️ 没有记录可以测试点赞功能")
    except Exception as e:
        print(f"❌ 点赞功能测试异常: {e}")

def test_error_handling():
    """测试错误处理"""
    base_url = "http://localhost:5001/api/talent-move"
    
    print("\n=== 测试错误处理 ===")
    
    # 1. 测试无效的ID
    print("\n1. 测试无效ID...")
    try:
        response = requests.get(f"{base_url}/999999")
        data = response.json()
        
        if not data['success'] and response.status_code == 404:
            print("✅ 无效ID处理正确")
        else:
            print(f"❌ 无效ID处理异常: {data}")
    except Exception as e:
        print(f"❌ 无效ID测试异常: {e}")
    
    # 2. 测试空搜索关键词
    print("\n2. 测试空搜索关键词...")
    try:
        response = requests.get(f"{base_url}/search", params={"keyword": ""})
        data = response.json()
        
        if not data['success'] and response.status_code == 400:
            print("✅ 空搜索关键词处理正确")
        else:
            print(f"❌ 空搜索关键词处理异常: {data}")
    except Exception as e:
        print(f"❌ 空搜索关键词测试异常: {e}")
    
    # 3. 测试无效的新增数据
    print("\n3. 测试无效的新增数据...")
    try:
        invalid_data = {
            "person_name": "",  # 空字段
            "from_company": "Test Company"
            # 缺少必需字段
        }
        
        response = requests.post(f"{base_url}/add", json=invalid_data)
        data = response.json()
        
        if not data['success'] and response.status_code == 400:
            print("✅ 无效新增数据处理正确")
        else:
            print(f"❌ 无效新增数据处理异常: {data}")
    except Exception as e:
        print(f"❌ 无效新增数据测试异常: {e}")
    
    # 4. 测试对不存在的记录点赞
    print("\n4. 测试对不存在的记录点赞...")
    try:
        response = requests.post(f"{base_url}/like/999999")
        data = response.json()
        
        if not data['success'] and response.status_code == 400:
            print("✅ 不存在记录点赞处理正确")
        else:
            print(f"❌ 不存在记录点赞处理异常: {data}")
    except Exception as e:
        print(f"❌ 不存在记录点赞测试异常: {e}")

def main():
    """主函数"""
    print("开始测试人才流动API接口...")
    print("请确保服务器正在运行: python server/app.py")
    print()
    
    # 测试正常功能
    test_api_endpoints()
    
    # 测试点赞功能
    test_like_functionality()
    
    # 测试错误处理
    test_error_handling()
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    main() 