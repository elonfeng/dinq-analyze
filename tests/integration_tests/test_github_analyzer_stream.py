#!/usr/bin/env python3
"""
GitHub分析器流式API测试

测试GitHub分析器的Server-Sent Events (SSE)流式输出功能
"""

import sys
import os
import json
import requests
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def test_github_analyzer_stream():
    """测试GitHub分析器流式API"""
    
    # 测试配置
    base_url = "http://localhost:5001"
    test_username = "octocat"  # GitHub的官方测试用户
    test_user_id = "LtXQ0x62DpOB88r1x3TL329FbHk1"  # 测试用户ID
    
    print("🌊 开始GitHub分析器流式API测试...")
    print(f"📍 服务器地址: {base_url}")
    print(f"👤 测试GitHub用户: {test_username}")
    print(f"🔑 测试用户ID: {test_user_id}")
    print("-" * 60)
    
    try:
        # 发送流式分析请求
        headers = {
            "Content-Type": "application/json",
            "Userid": test_user_id,
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache"
        }
        data = {"username": test_username}
        
        print(f"📤 发送流式分析请求...")
        start_time = time.time()
        
        # 使用stream=True来接收流式数据
        response = requests.post(
            f"{base_url}/api/github/analyze-stream",
            headers=headers,
            json=data,
            stream=True,
            timeout=300  # 5分钟超时
        )
        
        if response.status_code != 200:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"📄 响应内容: {response.text}")
            return False
        
        print(f"✅ 连接成功，开始接收流式数据...")
        print("=" * 60)
        
        # 解析流式数据
        message_count = 0
        progress_steps = []
        final_result = None
        
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith('data: '):
                try:
                    # 解析JSON数据
                    json_data = line[6:]  # 移除 'data: ' 前缀
                    if json_data.strip():
                        data = json.loads(json_data)
                        message_count += 1
                        
                        # 处理不同类型的消息
                        msg_type = data.get('type', 'unknown')
                        
                        if msg_type == 'start':
                            print(f"🚀 {data.get('message', '')}")
                            print(f"   用户名: {data.get('username', '')}")
                            
                        elif msg_type == 'progress':
                            step = data.get('step', '')
                            message = data.get('message', '')
                            progress_steps.append(step)
                            
                            # 使用不同的图标表示不同的步骤
                            if 'check' in step or 'init' in step:
                                icon = "🔍"
                            elif 'fetch' in step or 'start' in step:
                                icon = "📥"
                            elif 'success' in step or 'complete' in step:
                                icon = "✅"
                            elif 'failed' in step or 'error' in step:
                                icon = "❌"
                            elif 'ai' in step:
                                icon = "🤖"
                            elif 'cache' in step:
                                icon = "💾"
                            else:
                                icon = "⏳"
                            
                            print(f"{icon} [{step}] {message}")
                            
                            # 如果有额外数据，显示它
                            if 'data' in data:
                                extra_data = data['data']
                                if isinstance(extra_data, dict):
                                    for key, value in extra_data.items():
                                        print(f"   {key}: {value}")
                        
                        elif msg_type == 'complete':
                            end_time = time.time()
                            duration = end_time - start_time
                            
                            print("🎉 分析完成!")
                            print(f"⏱️  总耗时: {duration:.2f}秒")
                            print(f"📊 消息数量: {message_count}")
                            print(f"🔄 进度步骤: {len(progress_steps)}")
                            
                            final_result = data.get('data', {})
                            from_cache = data.get('from_cache', False)
                            
                            if from_cache:
                                print("💾 结果来源: 缓存")
                            else:
                                print("🔄 结果来源: 新分析")
                            
                            # 显示分析结果摘要
                            if final_result:
                                user_info = final_result.get('user', {})
                                overview = final_result.get('overview', {})
                                
                                print("\n📋 分析结果摘要:")
                                print(f"   👤 用户: {user_info.get('name', 'N/A')} (@{user_info.get('login', 'N/A')})")
                                print(f"   🏢 公司: {user_info.get('company', 'N/A')}")
                                print(f"   📍 位置: {user_info.get('location', 'N/A')}")
                                print(f"   ⭐ 星标: {overview.get('stars', 'N/A')}")
                                print(f"   📦 仓库: {overview.get('repositories', 'N/A')}")
                                print(f"   🔧 PR数: {overview.get('pull_requests', 'N/A')}")
                                print(f"   💼 工作经验: {overview.get('work_experience', 'N/A')} 年")
                                
                                # 显示AI分析结果
                                valuation = final_result.get('valuation_and_level', {})
                                role_model = final_result.get('role_model', {})
                                
                                if valuation:
                                    print(f"   💰 级别: {valuation.get('level', 'N/A')}")
                                    print(f"   💵 薪资: {valuation.get('salary_range', 'N/A')}")
                                
                                if role_model:
                                    print(f"   🎯 角色模型: {role_model.get('name', 'N/A')}")
                                    print(f"   📊 相似度: {role_model.get('similarity_score', 'N/A')}")
                                
                                # 显示使用统计
                                usage_info = data.get('usage_info', {})
                                if usage_info:
                                    print(f"\n📈 使用统计:")
                                    print(f"   剩余次数: {usage_info.get('remaining_uses', 'N/A')}")
                                    print(f"   总使用量: {usage_info.get('total_usage', 'N/A')}")
                                    print(f"   月度限制: {usage_info.get('limit', 'N/A')}")
                            
                        elif msg_type == 'error':
                            print(f"❌ 错误: {data.get('error', '')}")
                            if 'details' in data:
                                print(f"   详情: {data['details']}")
                            return False
                            
                        elif msg_type == 'heartbeat':
                            # 心跳消息，不显示
                            pass
                        
                        else:
                            print(f"❓ 未知消息类型: {msg_type}")
                            print(f"   内容: {data}")
                
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON解析错误: {e}")
                    print(f"   原始数据: {line}")
                except Exception as e:
                    print(f"⚠️ 处理消息时出错: {e}")
                    print(f"   原始数据: {line}")
        
        print("=" * 60)
        print("✅ 流式API测试完成!")
        
        # 验证结果
        if final_result:
            print("🎯 验证结果:")
            required_fields = ['user', 'overview', 'valuation_and_level', 'role_model']
            for field in required_fields:
                if field in final_result:
                    print(f"   ✅ {field}: 存在")
                else:
                    print(f"   ❌ {field}: 缺失")
        
        return True
        
    except requests.exceptions.Timeout:
        print("⏰ 请求超时")
        return False
    except requests.exceptions.ConnectionError:
        print("🔌 连接错误，请确保服务器正在运行")
        return False
    except Exception as e:
        print(f"💥 测试过程中发生异常: {e}")
        return False

def test_stream_error_cases():
    """测试流式API的错误情况"""
    base_url = "http://localhost:5001"
    test_user_id = "LtXQ0x62DpOB88r1x3TL329FbHk1"
    
    print("\n🧪 测试流式API错误情况...")
    
    # 测试无效用户名
    print("1️⃣ 测试无效GitHub用户名...")
    try:
        headers = {
            "Content-Type": "application/json",
            "Userid": test_user_id,
            "Accept": "text/event-stream"
        }
        data = {"username": "this_user_definitely_does_not_exist_12345"}
        
        response = requests.post(
            f"{base_url}/api/github/analyze-stream",
            headers=headers,
            json=data,
            stream=True,
            timeout=30
        )
        
        if response.status_code == 200:
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith('data: '):
                    json_data = line[6:]
                    if json_data.strip():
                        data = json.loads(json_data)
                        if data.get('type') == 'error':
                            print("✅ 正确处理了无效用户名")
                            break
        else:
            print(f"⚠️ 意外的响应状态: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")

if __name__ == "__main__":
    print("🌊 启动GitHub分析器流式API测试")
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
        success = test_github_analyzer_stream()
        
        # 运行错误情况测试
        test_stream_error_cases()
        
        if success:
            print("\n🎉 所有流式API测试完成!")
        else:
            print("\n❌ 部分测试失败，请检查配置和日志")
            
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
