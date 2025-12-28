#!/usr/bin/env python3
"""
GitHub分析器集成测试

测试GitHub分析器在DINQ项目中的集成功能
"""

import sys
import os
import json
import requests
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def test_github_analyzer_api():
    """测试GitHub分析器API端点"""
    
    # 测试配置
    base_url = "http://localhost:5001"
    test_username = "octocat"  # GitHub的官方测试用户
    test_user_id = "LtXQ0x62DpOB88r1x3TL329FbHk1"  # 测试用户ID
    
    print("🧪 开始GitHub分析器集成测试...")
    print(f"📍 服务器地址: {base_url}")
    print(f"👤 测试GitHub用户: {test_username}")
    print(f"🔑 测试用户ID: {test_user_id}")
    print("-" * 50)
    
    # 测试1: 健康检查
    print("1️⃣ 测试健康检查端点...")
    try:
        response = requests.get(f"{base_url}/api/github/health", timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ 健康检查成功: {health_data['status']}")
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 健康检查异常: {e}")
        return False
    
    # 测试2: API帮助文档
    print("\n2️⃣ 测试API帮助文档...")
    try:
        response = requests.get(f"{base_url}/api/github/help", timeout=10)
        if response.status_code == 200:
            help_data = response.json()
            print(f"✅ 帮助文档获取成功: {help_data['service']}")
            print(f"📋 功能特性数量: {len(help_data.get('features', []))}")
        else:
            print(f"❌ 帮助文档获取失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 帮助文档异常: {e}")
    
    # 测试3: POST方式分析GitHub用户
    print(f"\n3️⃣ 测试POST方式分析GitHub用户: {test_username}")
    try:
        headers = {
            "Content-Type": "application/json",
            "Userid": test_user_id
        }
        data = {"username": test_username}
        
        print("📤 发送分析请求...")
        start_time = time.time()
        
        response = requests.post(
            f"{base_url}/api/github/analyze",
            headers=headers,
            json=data,
            timeout=120  # GitHub分析可能需要较长时间
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 分析成功! 耗时: {duration:.2f}秒")
            print(f"👤 用户名: {result.get('username')}")
            
            # 检查分析结果的关键字段
            data = result.get('data', {})
            if data:
                user_info = data.get('user', {})
                overview = data.get('overview', {})
                
                print(f"📊 基本信息:")
                print(f"   - 姓名: {user_info.get('name', 'N/A')}")
                print(f"   - 公司: {user_info.get('company', 'N/A')}")
                print(f"   - 位置: {user_info.get('location', 'N/A')}")
                print(f"   - 关注者: {user_info.get('followers', {}).get('totalCount', 'N/A')}")
                
                print(f"📈 统计数据:")
                print(f"   - 工作经验: {overview.get('work_experience', 'N/A')} 年")
                print(f"   - 星标数: {overview.get('stars', 'N/A')}")
                print(f"   - 仓库数: {overview.get('repositories', 'N/A')}")
                print(f"   - PR数量: {overview.get('pull_requests', 'N/A')}")
                
                # 检查AI分析结果
                if 'valuation_and_level' in data:
                    valuation = data['valuation_and_level']
                    print(f"💰 估值分析:")
                    print(f"   - 级别: {valuation.get('level', 'N/A')}")
                    print(f"   - 薪资范围: {valuation.get('salary_range', 'N/A')}")
                
                if 'role_model' in data:
                    role_model = data['role_model']
                    print(f"🎯 角色模型:")
                    print(f"   - 姓名: {role_model.get('name', 'N/A')}")
                    print(f"   - 相似度: {role_model.get('similarity_score', 'N/A')}")
                
                # 检查使用限制信息
                usage_info = result.get('usage_info', {})
                if usage_info:
                    print(f"📊 使用统计:")
                    print(f"   - 剩余次数: {usage_info.get('remaining_uses', 'N/A')}")
                    print(f"   - 重置日期: {usage_info.get('reset_date', 'N/A')}")
                
            else:
                print("⚠️ 分析结果为空")
                
        elif response.status_code == 429:
            print("⚠️ 达到使用限制")
            limit_info = response.json()
            print(f"📊 限制信息: {limit_info}")
        else:
            print(f"❌ 分析失败: {response.status_code}")
            print(f"📄 响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 分析异常: {e}")
        return False
    
    # 测试4: GET方式分析GitHub用户
    print(f"\n4️⃣ 测试GET方式分析GitHub用户: {test_username}")
    try:
        headers = {"Userid": test_user_id}
        params = {"username": test_username}
        
        response = requests.get(
            f"{base_url}/api/github/analyze",
            headers=headers,
            params=params,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ GET方式分析成功!")
            print(f"👤 用户名: {result.get('username')}")
        elif response.status_code == 429:
            print("⚠️ 达到使用限制（预期行为，因为缓存）")
        else:
            print(f"❌ GET方式分析失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ GET方式分析异常: {e}")
    
    # 测试5: 用户统计信息
    print(f"\n5️⃣ 测试用户统计信息...")
    try:
        headers = {"Userid": test_user_id}
        
        response = requests.get(
            f"{base_url}/api/github/stats",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ 统计信息获取成功!")
            print(f"📊 用户统计: {stats.get('github_analysis_stats', {})}")
        else:
            print(f"❌ 统计信息获取失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 统计信息异常: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 GitHub分析器集成测试完成!")
    return True

def test_error_cases():
    """测试错误情况"""
    base_url = "http://localhost:5001"
    test_user_id = "LtXQ0x62DpOB88r1x3TL329FbHk1"
    
    print("\n🧪 测试错误情况...")
    
    # 测试无效用户名
    print("1️⃣ 测试无效GitHub用户名...")
    try:
        headers = {
            "Content-Type": "application/json",
            "Userid": test_user_id
        }
        data = {"username": "this_user_definitely_does_not_exist_12345"}
        
        response = requests.post(
            f"{base_url}/api/github/analyze",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 404:
            print("✅ 正确处理了无效用户名")
        else:
            print(f"⚠️ 意外的响应状态: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
    
    # 测试缺少认证
    print("\n2️⃣ 测试缺少用户认证...")
    try:
        headers = {"Content-Type": "application/json"}
        data = {"username": "octocat"}
        
        response = requests.post(
            f"{base_url}/api/github/analyze",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code in [401, 403]:
            print("✅ 正确处理了缺少认证")
        else:
            print(f"⚠️ 意外的响应状态: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")

if __name__ == "__main__":
    print("🚀 启动GitHub分析器集成测试")
    print("请确保DINQ服务器正在运行 (http://localhost:5001)")
    print("请确保已配置必要的环境变量:")
    print("  - GITHUB_TOKEN")
    print("  - OPENROUTER_API_KEY") 
    print("  - CRAWLBASE_TOKEN")
    print()
    
    # 等待用户确认
    if sys.stdin.isatty():
        input("按Enter键开始测试...")
    else:
        print("检测到非交互环境，自动继续...\n")
    
    try:
        # 运行主要测试
        success = test_github_analyzer_api()
        
        # 运行错误情况测试
        test_error_cases()
        
        if success:
            print("\n🎉 所有测试完成!")
        else:
            print("\n❌ 部分测试失败，请检查配置和日志")
            
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
