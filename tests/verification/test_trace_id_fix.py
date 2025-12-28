#!/usr/bin/env python3
"""
测试Trace ID修复效果

这个脚本测试修复后的logger是否正确包含trace ID
"""

import sys
import os
import time
import threading
from typing import List

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def test_trace_logger_imports():
    """测试trace logger导入是否正常"""
    print("🔍 测试Trace Logger导入")
    print("-" * 30)
    
    modules_to_test = [
        'server.services.scholar.scholar_service',
        'server.api.scholar.data_retriever',
        'server.services.scholar.data_fetcher',
        'src.utils.scholar_cache',
        'server.api.scholar.db_cache',
        'server.services.scholar.analyzer',
        'server.api.scholar.stream_processor',
    ]
    
    success_count = 0
    for module_name in modules_to_test:
        try:
            module = __import__(module_name, fromlist=['logger'])
            logger = getattr(module, 'logger', None)
            
            if logger:
                # 检查是否是TraceLoggerAdapter
                from server.utils.trace_context import TraceLoggerAdapter
                if isinstance(logger, TraceLoggerAdapter):
                    print(f"  ✅ {module_name}: 使用TraceLoggerAdapter")
                    success_count += 1
                else:
                    print(f"  ⚠️  {module_name}: 使用普通logger")
            else:
                print(f"  ❌ {module_name}: 未找到logger")
                
        except ImportError as e:
            print(f"  ❌ {module_name}: 导入失败 - {e}")
        except Exception as e:
            print(f"  ❌ {module_name}: 错误 - {e}")
    
    print(f"\n成功率: {success_count}/{len(modules_to_test)} ({success_count/len(modules_to_test)*100:.1f}%)")

def test_trace_id_in_logs():
    """测试日志中是否包含trace ID"""
    print(f"\n📝 测试日志中的Trace ID")
    print("-" * 30)
    
    # 设置trace ID
    from server.utils.trace_context import TraceContext, get_trace_logger
    
    test_trace_id = "test1234"
    TraceContext.set_trace_id(test_trace_id)
    
    # 测试不同模块的logger
    test_modules = [
        ('scholar_service', 'server.services.scholar'),
        ('data_retriever', 'server.api.scholar.data_retriever'),
        ('data_fetcher', 'server.services.scholar.data_fetcher'),
        ('scholar_cache', 'scholar_cache'),
    ]
    
    for module_name, logger_name in test_modules:
        try:
            logger = get_trace_logger(logger_name)
            logger.info(f"测试来自 {module_name} 的日志消息")
            print(f"  ✅ {module_name}: 日志已记录")
        except Exception as e:
            print(f"  ❌ {module_name}: 错误 - {e}")
    
    # 清除trace ID
    TraceContext.clear_trace_id()

def test_thread_trace_propagation():
    """测试线程中的trace ID传播"""
    print(f"\n🧵 测试线程Trace ID传播")
    print("-" * 30)
    
    from server.utils.trace_context import TraceContext, get_trace_logger, propagate_trace_to_thread
    
    # 设置主线程的trace ID
    main_trace_id = "main5678"
    TraceContext.set_trace_id(main_trace_id)
    
    results = []
    
    def worker_function(worker_id):
        """工作线程函数"""
        logger = get_trace_logger(f'test_worker_{worker_id}')
        current_trace_id = TraceContext.get_trace_id()
        
        logger.info(f"工作线程 {worker_id} 开始，trace ID: {current_trace_id}")
        
        results.append({
            'worker_id': worker_id,
            'trace_id': current_trace_id,
            'expected': main_trace_id
        })
    
    # 启动多个线程
    threads = []
    for i in range(3):
        # 使用propagate_trace_to_thread确保trace ID传播
        thread = threading.Thread(target=propagate_trace_to_thread(worker_function), args=(i,))
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    # 检查结果
    success_count = 0
    for result in results:
        worker_id = result['worker_id']
        trace_id = result['trace_id']
        expected = result['expected']
        
        if trace_id == expected:
            print(f"  ✅ 工作线程 {worker_id}: trace ID正确传播 ({trace_id})")
            success_count += 1
        else:
            print(f"  ❌ 工作线程 {worker_id}: trace ID传播失败 (期望: {expected}, 实际: {trace_id})")
    
    print(f"\n线程传播成功率: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
    
    # 清除trace ID
    TraceContext.clear_trace_id()

def test_scholar_service_integration():
    """测试scholar service的trace ID集成"""
    print(f"\n🎓 测试Scholar Service集成")
    print("-" * 30)
    
    from server.utils.trace_context import TraceContext, get_trace_logger
    
    # 设置trace ID
    test_trace_id = "scholar99"
    TraceContext.set_trace_id(test_trace_id)
    
    try:
        # 测试scholar service的logger
        from server.services.scholar.scholar_service import logger as scholar_logger
        scholar_logger.info("测试Scholar Service的trace ID集成")
        print("  ✅ Scholar Service logger测试成功")
        
        # 测试data retriever的logger
        from server.api.scholar.data_retriever import logger as retriever_logger
        retriever_logger.info("测试Data Retriever的trace ID集成")
        print("  ✅ Data Retriever logger测试成功")
        
        # 测试data fetcher的logger
        from server.services.scholar.data_fetcher import logger as fetcher_logger
        fetcher_logger.info("测试Data Fetcher的trace ID集成")
        print("  ✅ Data Fetcher logger测试成功")
        
    except Exception as e:
        print(f"  ❌ Scholar Service集成测试失败: {e}")
    
    # 清除trace ID
    TraceContext.clear_trace_id()

def check_log_files():
    """检查日志文件中的trace ID"""
    print(f"\n📄 检查日志文件")
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
        print("  ❌ 未找到日志文件")
        return
    
    print(f"  📁 日志文件: {log_file}")
    
    try:
        # 读取最后几行日志
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 查找包含trace ID的日志行
        trace_lines = []
        test_lines = []
        
        for line in lines[-100:]:  # 检查最后100行
            if '[' in line and ']' in line:
                # 提取trace ID部分
                start = line.find('[') + 1
                end = line.find(']')
                if start > 0 and end > start:
                    trace_id = line[start:end]
                    if trace_id != 'no-trace':
                        trace_lines.append((trace_id, line.strip()))
                        
                        # 检查是否是测试产生的日志
                        if any(test_word in line for test_word in ['test', '测试', 'Test']):
                            test_lines.append((trace_id, line.strip()))
        
        if trace_lines:
            print(f"  ✅ 找到 {len(trace_lines)} 条包含Trace ID的日志")
            if test_lines:
                print(f"  ✅ 找到 {len(test_lines)} 条测试相关的日志")
                print("  最近的测试日志:")
                for trace_id, line in test_lines[-3:]:
                    print(f"    [{trace_id}] {line[-80:]}")  # 显示最后80个字符
            else:
                print("  ⚠️  未找到测试相关的日志")
        else:
            print("  ❌ 未找到包含Trace ID的日志")
            
    except Exception as e:
        print(f"  ❌ 读取日志文件失败: {e}")

def main():
    """主函数"""
    print("🔧 Trace ID修复效果测试")
    print("=" * 50)
    
    # 运行各种测试
    test_trace_logger_imports()
    test_trace_id_in_logs()
    test_thread_trace_propagation()
    test_scholar_service_integration()
    check_log_files()
    
    print(f"\n📋 测试总结")
    print("=" * 50)
    
    summary = [
        "1. Logger导入测试:",
        "   - 检查各模块是否正确使用TraceLoggerAdapter",
        "   - 确保fallback机制正常工作",
        "",
        "2. 日志记录测试:",
        "   - 验证trace ID正确包含在日志中",
        "   - 测试不同模块的logger行为",
        "",
        "3. 线程传播测试:",
        "   - 验证trace ID在线程间正确传播",
        "   - 测试propagate_trace_to_thread函数",
        "",
        "4. Scholar Service集成测试:",
        "   - 测试关键模块的trace ID集成",
        "   - 验证实际使用场景",
        "",
        "5. 日志文件检查:",
        "   - 检查日志文件中的trace ID格式",
        "   - 查找测试产生的日志条目",
        "",
        "修复效果:",
        "- 如果大部分测试显示✅，说明修复成功",
        "- 如果仍有❌，需要进一步检查相关模块",
        "- 查看日志文件确认trace ID正确显示"
    ]
    
    for item in summary:
        print(item)

if __name__ == "__main__":
    main()
