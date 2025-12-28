#!/usr/bin/env python3
"""
测试Trace ID功能

这个脚本测试全局请求追踪系统是否正常工作
"""

import sys
import os
import requests
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def test_trace_id_generation():
    """测试trace ID生成功能"""
    print("🔍 测试Trace ID生成功能")
    print("-" * 30)
    
    try:
        from server.utils.trace_context import TraceContext
        
        # 测试生成多个trace ID
        trace_ids = [TraceContext.generate_trace_id() for _ in range(5)]
        
        print(f"生成的Trace IDs: {trace_ids}")
        
        # 验证唯一性
        if len(set(trace_ids)) == len(trace_ids):
            print("✅ Trace ID唯一性测试通过")
        else:
            print("❌ Trace ID唯一性测试失败")
        
        # 验证长度
        if all(len(tid) == 8 for tid in trace_ids):
            print("✅ Trace ID长度测试通过")
        else:
            print("❌ Trace ID长度测试失败")
            
    except ImportError as e:
        print(f"❌ 导入失败: {e}")

def test_trace_context():
    """测试trace context功能"""
    print(f"\n🧪 测试Trace Context功能")
    print("-" * 30)
    
    try:
        from server.utils.trace_context import TraceContext
        
        # 测试设置和获取
        test_trace_id = "test1234"
        TraceContext.set_trace_id(test_trace_id)
        
        retrieved_id = TraceContext.get_trace_id()
        if retrieved_id == test_trace_id:
            print("✅ Trace ID设置和获取测试通过")
        else:
            print(f"❌ Trace ID设置和获取测试失败: 期望 {test_trace_id}, 得到 {retrieved_id}")
        
        # 测试清除
        TraceContext.clear_trace_id()
        cleared_id = TraceContext.get_trace_id()
        if cleared_id is None:
            print("✅ Trace ID清除测试通过")
        else:
            print(f"❌ Trace ID清除测试失败: 期望 None, 得到 {cleared_id}")
            
    except ImportError as e:
        print(f"❌ 导入失败: {e}")

def test_thread_isolation():
    """测试线程隔离功能"""
    print(f"\n🧵 测试线程隔离功能")
    print("-" * 30)
    
    try:
        from server.utils.trace_context import TraceContext
        
        results = {}
        
        def thread_worker(thread_id):
            # 每个线程设置不同的trace ID
            trace_id = f"thread{thread_id}"
            TraceContext.set_trace_id(trace_id)
            
            # 模拟一些工作
            time.sleep(0.1)
            
            # 获取trace ID
            retrieved_id = TraceContext.get_trace_id()
            results[thread_id] = retrieved_id
        
        # 启动多个线程
        threads = []
        for i in range(3):
            thread = threading.Thread(target=thread_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证结果
        print(f"线程结果: {results}")
        
        expected = {0: "thread0", 1: "thread1", 2: "thread2"}
        if results == expected:
            print("✅ 线程隔离测试通过")
        else:
            print(f"❌ 线程隔离测试失败: 期望 {expected}, 得到 {results}")
            
    except ImportError as e:
        print(f"❌ 导入失败: {e}")

def test_trace_logger():
    """测试trace logger功能"""
    print(f"\n📝 测试Trace Logger功能")
    print("-" * 30)
    
    try:
        from server.utils.trace_context import TraceContext, get_trace_logger
        
        # 设置trace ID
        test_trace_id = "log12345"
        TraceContext.set_trace_id(test_trace_id)
        
        # 获取trace logger
        trace_logger = get_trace_logger("test_module")
        
        # 记录一些日志
        trace_logger.info("这是一条测试日志消息")
        trace_logger.warning("这是一条警告消息")
        trace_logger.error("这是一条错误消息")
        
        print("✅ Trace Logger测试完成 - 请检查日志文件中的trace ID")
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")

def test_http_requests():
    """测试HTTP请求中的trace ID"""
    print(f"\n🌐 测试HTTP请求中的Trace ID")
    print("-" * 30)
    
    # 测试环境
    environments = [
        ("本地开发", "http://localhost:5001"),
        # ("生产环境", "https://www.dinq.io"),  # 可选，如果服务器正在运行
    ]
    
    for env_name, base_url in environments:
        print(f"\n测试环境: {env_name}")
        print(f"URL: {base_url}")
        
        # 测试不同的端点
        endpoints = [
            "/api/top-talents",
            "/api/file-types",
        ]
        
        for endpoint in endpoints:
            test_endpoint_trace_id(base_url, endpoint)

def test_endpoint_trace_id(base_url: str, endpoint: str):
    """测试单个端点的trace ID"""
    url = f"{base_url}{endpoint}"
    
    try:
        print(f"  📡 测试端点: {endpoint}")
        
        # 发送请求（不带自定义trace ID）
        response1 = requests.get(url, timeout=10)
        trace_id1 = response1.headers.get('X-Trace-ID')
        
        # 发送请求（带自定义trace ID）
        custom_trace_id = "custom123"
        response2 = requests.get(url, headers={'X-Trace-ID': custom_trace_id}, timeout=10)
        trace_id2 = response2.headers.get('X-Trace-ID')
        
        print(f"    自动生成的Trace ID: {trace_id1}")
        print(f"    自定义Trace ID: {trace_id2}")
        
        # 验证结果
        if trace_id1 and len(trace_id1) == 8:
            print("    ✅ 自动生成的Trace ID格式正确")
        else:
            print(f"    ❌ 自动生成的Trace ID格式错误: {trace_id1}")
        
        if trace_id2 == custom_trace_id:
            print("    ✅ 自定义Trace ID传递正确")
        else:
            print(f"    ❌ 自定义Trace ID传递错误: 期望 {custom_trace_id}, 得到 {trace_id2}")
            
    except requests.exceptions.ConnectionError:
        print(f"    🔌 连接失败 - 服务器可能未运行")
    except requests.exceptions.Timeout:
        print(f"    ⏰ 请求超时")
    except Exception as e:
        print(f"    ❌ 错误: {e}")

def test_concurrent_requests():
    """测试并发请求的trace ID隔离"""
    print(f"\n🚀 测试并发请求的Trace ID隔离")
    print("-" * 30)
    
    base_url = "http://localhost:5001"
    endpoint = "/api/file-types"
    url = f"{base_url}{endpoint}"
    
    def make_request(request_id):
        """发送单个请求"""
        custom_trace_id = f"req{request_id:03d}"
        try:
            response = requests.get(url, headers={'X-Trace-ID': custom_trace_id}, timeout=10)
            returned_trace_id = response.headers.get('X-Trace-ID')
            return {
                'request_id': request_id,
                'sent_trace_id': custom_trace_id,
                'returned_trace_id': returned_trace_id,
                'status_code': response.status_code,
                'success': returned_trace_id == custom_trace_id
            }
        except Exception as e:
            return {
                'request_id': request_id,
                'sent_trace_id': custom_trace_id,
                'returned_trace_id': None,
                'status_code': None,
                'success': False,
                'error': str(e)
            }
    
    try:
        # 使用线程池发送并发请求
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request, i) for i in range(10)]
            results = [future.result() for future in futures]
        
        # 分析结果
        successful = sum(1 for r in results if r['success'])
        total = len(results)
        
        print(f"并发请求结果: {successful}/{total} 成功")
        
        # 显示详细结果
        for result in results:
            status = "✅" if result['success'] else "❌"
            print(f"  {status} 请求{result['request_id']:02d}: {result['sent_trace_id']} -> {result['returned_trace_id']}")
        
        if successful == total:
            print("✅ 并发请求Trace ID隔离测试通过")
        else:
            print(f"❌ 并发请求Trace ID隔离测试失败: {successful}/{total}")
            
    except Exception as e:
        print(f"❌ 并发测试失败: {e}")

def test_log_file_trace_ids():
    """检查日志文件中的trace ID"""
    print(f"\n📄 检查日志文件中的Trace ID")
    print("-" * 30)
    
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
        return
    
    print(f"📁 日志文件: {log_file}")
    
    try:
        # 读取最后几行日志
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 查找包含trace ID的日志行
        trace_lines = []
        for line in lines[-50:]:  # 检查最后50行
            if '[' in line and ']' in line:
                # 提取trace ID部分
                start = line.find('[') + 1
                end = line.find(']')
                if start > 0 and end > start:
                    trace_id = line[start:end]
                    if trace_id != 'no-trace':
                        trace_lines.append((trace_id, line.strip()))
        
        if trace_lines:
            print(f"✅ 找到 {len(trace_lines)} 条包含Trace ID的日志")
            print("最近的几条日志:")
            for trace_id, line in trace_lines[-5:]:
                print(f"  [{trace_id}] {line[-100:]}")  # 显示最后100个字符
        else:
            print("❌ 未找到包含Trace ID的日志")
            
    except Exception as e:
        print(f"❌ 读取日志文件失败: {e}")

def main():
    """主函数"""
    print("🔧 Trace ID功能测试工具")
    print("=" * 50)
    
    # 运行各种测试
    test_trace_id_generation()
    test_trace_context()
    test_thread_isolation()
    test_trace_logger()
    test_http_requests()
    test_concurrent_requests()
    test_log_file_trace_ids()
    
    print(f"\n📋 测试总结")
    print("=" * 50)
    
    summary = [
        "1. Trace ID生成和管理:",
        "   - 每个请求都会获得唯一的8位trace ID",
        "   - 支持自定义trace ID传递",
        "   - 线程间完全隔离",
        "",
        "2. 日志集成:",
        "   - 所有日志自动包含trace ID",
        "   - 支持请求上下文信息",
        "   - 便于问题追踪和调试",
        "",
        "3. HTTP集成:",
        "   - 请求头支持X-Trace-ID",
        "   - 响应头返回trace ID",
        "   - 并发请求完全隔离",
        "",
        "4. 使用方法:",
        "   - 查看日志文件中的[trace-id]标记",
        "   - 使用X-Trace-ID头传递自定义ID",
        "   - 在代码中使用get_trace_logger()获取trace-aware logger"
    ]
    
    for item in summary:
        print(item)

if __name__ == "__main__":
    main()
