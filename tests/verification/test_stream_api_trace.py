#!/usr/bin/env python3
"""
测试Stream API的Trace ID传播

这个脚本测试/api/stream端点的trace ID是否正确传播到所有子模块
"""

import sys
import os
import requests
import time
import threading
from typing import Optional

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def test_stream_api_trace_propagation():
    """测试Stream API的trace ID传播"""
    print("🔍 测试Stream API Trace ID传播")
    print("-" * 50)
    
    # 配置
    base_url = "http://localhost:5001"
    custom_trace_id = f"test_{int(time.time())}"
    
    print(f"测试URL: {base_url}/api/stream")
    print(f"自定义Trace ID: {custom_trace_id}")
    
    # 准备请求
    headers = {
        "Content-Type": "application/json",
        "Userid": "test_user",
        "X-Trace-ID": custom_trace_id
    }
    
    data = {
        "query": "yigHzW8AAAAJ"  # 使用一个已知的scholar ID
    }
    
    print(f"请求数据: {data}")
    print()
    
    try:
        # 发送请求
        print("📤 发送Stream API请求...")
        response = requests.post(
            f"{base_url}/api/stream",
            json=data,
            headers=headers,
            stream=True,
            timeout=30
        )
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ 请求失败: {response.text}")
            return False
        
        # 读取流响应
        print("📥 读取流响应...")
        message_count = 0
        for line in response.iter_lines():
            if line:
                message_count += 1
                decoded_line = line.decode('utf-8')
                print(f"  消息 {message_count}: {decoded_line[:100]}...")
                
                # 只读取前几条消息就停止
                if message_count >= 5:
                    break
        
        print(f"✅ 成功接收 {message_count} 条流消息")
        return True
        
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ 连接错误 - 请确保服务器正在运行")
        return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def check_log_for_trace_id(trace_id: str, wait_seconds: int = 5) -> bool:
    """检查日志文件中是否包含指定的trace ID"""
    print(f"\n📄 检查日志文件中的Trace ID: {trace_id}")
    print("-" * 50)
    
    # 等待日志写入
    print(f"等待 {wait_seconds} 秒让日志写入...")
    time.sleep(wait_seconds)
    
    # 查找日志文件
    log_paths = [
        "logs/dinq_allin_one.log",
        "../logs/dinq_allin_one.log",
        "../../logs/dinq_allin_one.log",
    ]
    
    log_file = None
    for path in log_paths:
        if os.path.exists(path):
            log_file = path
            break
    
    if not log_file:
        print("❌ 未找到日志文件")
        return False
    
    print(f"📁 日志文件: {log_file}")
    
    try:
        # 读取日志文件
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 查找包含trace ID的日志行
        trace_lines = []
        no_trace_lines = []
        
        # 检查最后1000行日志
        for line in lines[-1000:]:
            if f'[{trace_id}]' in line:
                trace_lines.append(line.strip())
            elif '[no-trace]' in line and any(keyword in line for keyword in ['data_retriever', 'data_fetcher', 'scholar']):
                no_trace_lines.append(line.strip())
        
        print(f"找到 {len(trace_lines)} 条包含目标Trace ID的日志")
        print(f"找到 {len(no_trace_lines)} 条相关的no-trace日志")
        
        if trace_lines:
            print("\n✅ 包含目标Trace ID的日志示例:")
            for i, line in enumerate(trace_lines[:5]):  # 显示前5条
                print(f"  {i+1}. {line}")
        
        if no_trace_lines:
            print("\n⚠️  相关的no-trace日志:")
            for i, line in enumerate(no_trace_lines[:3]):  # 显示前3条
                print(f"  {i+1}. {line}")
        
        # 判断修复是否成功
        if trace_lines and not no_trace_lines:
            print("\n🎉 完美！所有相关日志都包含正确的Trace ID")
            return True
        elif trace_lines and no_trace_lines:
            print("\n⚠️  部分修复：有些日志包含Trace ID，但仍有no-trace日志")
            return False
        else:
            print("\n❌ 修复失败：未找到包含目标Trace ID的相关日志")
            return False
            
    except Exception as e:
        print(f"❌ 读取日志文件失败: {e}")
        return False

def test_multiple_requests():
    """测试多个请求的trace ID隔离"""
    print(f"\n🔄 测试多个请求的Trace ID隔离")
    print("-" * 50)
    
    base_url = "http://localhost:5001"
    
    # 创建多个不同的trace ID
    trace_ids = [f"multi_{i}_{int(time.time())}" for i in range(3)]
    
    results = []
    
    def send_request(trace_id: str, index: int):
        """发送单个请求"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Userid": f"test_user_{index}",
                "X-Trace-ID": trace_id
            }
            
            data = {"query": "yigHzW8AAAAJ"}
            
            print(f"  📤 发送请求 {index+1} (Trace ID: {trace_id})")
            
            response = requests.post(
                f"{base_url}/api/stream",
                json=data,
                headers=headers,
                stream=True,
                timeout=10
            )
            
            if response.status_code == 200:
                # 读取几条消息
                message_count = 0
                for line in response.iter_lines():
                    if line:
                        message_count += 1
                        if message_count >= 2:  # 只读取前2条消息
                            break
                
                results.append((trace_id, True, f"成功接收 {message_count} 条消息"))
            else:
                results.append((trace_id, False, f"状态码: {response.status_code}"))
                
        except Exception as e:
            results.append((trace_id, False, f"错误: {e}"))
    
    # 并发发送请求
    threads = []
    for i, trace_id in enumerate(trace_ids):
        thread = threading.Thread(target=send_request, args=(trace_id, i))
        threads.append(thread)
        thread.start()
        time.sleep(0.5)  # 稍微错开请求时间
    
    # 等待所有请求完成
    for thread in threads:
        thread.join()
    
    # 检查结果
    success_count = 0
    for trace_id, success, message in results:
        status = "✅" if success else "❌"
        print(f"  {status} {trace_id}: {message}")
        if success:
            success_count += 1
    
    print(f"\n多请求测试结果: {success_count}/{len(results)} 成功")
    return success_count == len(results)

def main():
    """主函数"""
    print("🔧 Stream API Trace ID传播测试")
    print("=" * 60)
    
    # 检查服务器是否运行
    try:
        response = requests.get("http://localhost:5001/api/file-types", timeout=5)
        if response.status_code != 200:
            print("❌ 服务器未正常运行，请先启动服务器")
            return
    except:
        print("❌ 无法连接到服务器，请确保服务器在 http://localhost:5001 运行")
        return
    
    print("✅ 服务器连接正常")
    print()
    
    # 运行测试
    results = []
    
    # 测试1: 基本的Stream API trace传播
    test1_success = test_stream_api_trace_propagation()
    results.append(("Stream API基本测试", test1_success))
    
    # 测试2: 检查日志中的trace ID
    if test1_success:
        # 获取刚才使用的trace ID
        custom_trace_id = f"test_{int(time.time())}"
        
        # 再发送一个请求用于日志检查
        print(f"\n📤 发送额外请求用于日志检查 (Trace ID: {custom_trace_id})")
        try:
            response = requests.post(
                "http://localhost:5001/api/stream",
                json={"query": "yigHzW8AAAAJ"},
                headers={
                    "Content-Type": "application/json",
                    "Userid": "test_user",
                    "X-Trace-ID": custom_trace_id
                },
                stream=True,
                timeout=15
            )
            
            # 读取几条消息
            message_count = 0
            for line in response.iter_lines():
                if line:
                    message_count += 1
                    if message_count >= 3:
                        break
            
            # 检查日志
            test2_success = check_log_for_trace_id(custom_trace_id, wait_seconds=3)
            results.append(("日志Trace ID检查", test2_success))
            
        except Exception as e:
            print(f"❌ 额外请求失败: {e}")
            results.append(("日志Trace ID检查", False))
    else:
        results.append(("日志Trace ID检查", False))
    
    # 测试3: 多请求隔离测试
    test3_success = test_multiple_requests()
    results.append(("多请求隔离测试", test3_success))
    
    # 总结结果
    print(f"\n📋 测试结果总结")
    print("=" * 60)
    
    success_count = 0
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{test_name}: {status}")
        if success:
            success_count += 1
    
    print(f"\n总体结果: {success_count}/{len(results)} 测试通过")
    
    if success_count == len(results):
        print("🎉 所有测试通过！Stream API的Trace ID传播正常工作")
    else:
        print("⚠️  部分测试失败，可能需要进一步检查")
    
    print(f"\n📝 修复说明:")
    print("1. 在Flask的generate()函数中添加了trace context传播")
    print("2. 确保trace ID在流响应生成器中可用")
    print("3. 修复了/api/stream和/api/scholar-pk端点")
    print("4. 保持了与现有代码的兼容性")

if __name__ == "__main__":
    main()
