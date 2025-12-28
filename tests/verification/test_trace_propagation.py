#!/usr/bin/env python3
"""
测试trace ID传播是否正常工作

这个脚本测试trace ID在线程间的传播
"""

import sys
import os
import threading
import time

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def test_basic_trace_propagation():
    """测试基本的trace传播"""
    print("🔍 测试基本Trace传播")
    print("-" * 30)
    
    try:
        from server.utils.trace_context import TraceContext, get_trace_logger, propagate_trace_to_thread
        
        # 设置主线程的trace ID
        main_trace_id = "test123"
        TraceContext.set_trace_id(main_trace_id)
        
        print(f"主线程设置trace ID: {main_trace_id}")
        
        # 验证主线程的trace ID
        current_id = TraceContext.get_trace_id()
        print(f"主线程当前trace ID: {current_id}")
        
        if current_id != main_trace_id:
            print("❌ 主线程trace ID设置失败")
            return False
        
        # 测试线程传播
        result_container = {'trace_id': None, 'logger_test': False}
        
        def worker_function():
            """工作线程函数"""
            # 获取线程中的trace ID
            thread_trace_id = TraceContext.get_trace_id()
            result_container['trace_id'] = thread_trace_id
            
            # 测试logger是否包含trace ID
            logger = get_trace_logger('test_worker')
            logger.info("测试工作线程中的日志")
            result_container['logger_test'] = True
            
            print(f"工作线程trace ID: {thread_trace_id}")
        
        # 使用propagate_trace_to_thread创建线程
        thread = threading.Thread(target=propagate_trace_to_thread(worker_function))
        thread.start()
        thread.join()
        
        # 检查结果
        if result_container['trace_id'] == main_trace_id:
            print("✅ Trace ID正确传播到工作线程")
        else:
            print(f"❌ Trace ID传播失败: 期望 {main_trace_id}, 实际 {result_container['trace_id']}")
            return False
        
        if result_container['logger_test']:
            print("✅ 工作线程logger测试成功")
        else:
            print("❌ 工作线程logger测试失败")
            return False
        
        # 清除trace ID
        TraceContext.clear_trace_id()
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_data_retriever_simulation():
    """模拟data_retriever的调用模式"""
    print(f"\n🔍 模拟Data Retriever调用模式")
    print("-" * 30)
    
    try:
        from server.utils.trace_context import TraceContext, get_trace_logger, propagate_trace_to_thread
        
        # 模拟HTTP请求设置trace ID
        request_trace_id = "req456"
        TraceContext.set_trace_id(request_trace_id)
        
        print(f"HTTP请求trace ID: {request_trace_id}")
        
        # 模拟data_retriever中的变量
        scholar_report = {"data": None}
        scholar_data_ready = threading.Event()
        
        def run_scholar_service():
            """模拟run_scholar_service函数"""
            try:
                # 检查trace ID
                current_trace = TraceContext.get_trace_id()
                print(f"run_scholar_service中的trace ID: {current_trace}")
                
                # 模拟创建ScholarDataFetcher（这里会调用logger）
                logger = get_trace_logger('server.services.scholar.data_fetcher')
                logger.info("DataFetcher initialization started - INFO level test")
                
                # 模拟一些工作
                time.sleep(0.1)
                
                scholar_report["data"] = {"test": "success", "trace_id": current_trace}
                
            except Exception as e:
                print(f"run_scholar_service错误: {e}")
            finally:
                scholar_data_ready.set()
        
        # 使用与data_retriever相同的方式创建线程
        try:
            scholar_thread = threading.Thread(target=propagate_trace_to_thread(run_scholar_service))
        except ImportError:
            scholar_thread = threading.Thread(target=run_scholar_service)
        
        scholar_thread.start()
        
        # 等待完成
        scholar_data_ready.wait(timeout=5)
        scholar_thread.join()
        
        # 检查结果
        if scholar_report["data"] and scholar_report["data"].get("trace_id") == request_trace_id:
            print("✅ Data Retriever模拟测试成功")
            return True
        else:
            print(f"❌ Data Retriever模拟测试失败: {scholar_report}")
            return False
        
    except Exception as e:
        print(f"❌ 模拟测试失败: {e}")
        return False

def test_scholar_service_import():
    """测试scholar service相关模块的导入"""
    print(f"\n🔍 测试Scholar Service模块导入")
    print("-" * 30)
    
    try:
        from server.utils.trace_context import TraceContext, get_trace_logger
        
        # 设置trace ID
        test_trace_id = "import789"
        TraceContext.set_trace_id(test_trace_id)
        
        print(f"设置trace ID: {test_trace_id}")
        
        # 测试导入data_fetcher（这会触发logger调用）
        from server.services.scholar.data_fetcher import ScholarDataFetcher
        print("✅ ScholarDataFetcher导入成功")
        
        # 创建实例（这会调用__init__中的logger）
        fetcher = ScholarDataFetcher(use_crawlbase=False)
        print("✅ ScholarDataFetcher实例创建成功")
        
        # 测试导入scholar_service
        from server.services.scholar.scholar_service import ScholarService
        print("✅ ScholarService导入成功")
        
        # 创建实例
        service = ScholarService(use_crawlbase=False)
        print("✅ ScholarService实例创建成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 导入测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def main():
    """主函数"""
    print("🔧 Trace ID传播测试")
    print("=" * 50)
    
    # 运行各种测试
    results = []
    
    results.append(("基本Trace传播", test_basic_trace_propagation()))
    results.append(("Data Retriever模拟", test_data_retriever_simulation()))
    results.append(("Scholar Service导入", test_scholar_service_import()))
    
    print(f"\n📋 测试结果总结")
    print("=" * 50)
    
    success_count = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            success_count += 1
    
    print(f"\n总体结果: {success_count}/{len(results)} 测试通过")
    
    if success_count == len(results):
        print("🎉 所有测试通过！Trace传播正常工作")
    else:
        print("⚠️  部分测试失败，需要进一步调试")
    
    print(f"\n📝 调试建议:")
    print("1. 检查日志文件中是否有对应的trace ID")
    print("2. 确认propagate_trace_to_thread函数正确工作")
    print("3. 验证TraceContext在不同线程中的行为")
    print("4. 检查logger初始化时的trace context状态")

if __name__ == "__main__":
    main()
