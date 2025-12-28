#!/usr/bin/env python3
"""
Trace Logger使用示例

这个文件展示了如何在DINQ项目中使用新的trace logger功能
"""

import sys
import os
import time
import threading
from typing import Optional

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import trace context utilities
from server.utils.trace_context import (
    TraceContext, 
    get_trace_logger, 
    propagate_trace_to_thread,
    start_trace,
    get_current_trace_id,
    end_trace
)

def example_basic_usage():
    """基本使用示例"""
    print("📝 基本使用示例")
    print("-" * 30)
    
    # 获取trace-aware logger
    logger = get_trace_logger(__name__)
    
    # 开始一个新的trace
    trace_id = start_trace()
    print(f"开始trace: {trace_id}")
    
    # 记录一些日志（自动包含trace ID）
    logger.info("这是一条信息日志")
    logger.warning("这是一条警告日志")
    logger.error("这是一条错误日志")
    
    # 结束trace
    end_trace()
    print("trace结束")

def example_function_with_tracing():
    """带有追踪的函数示例"""
    logger = get_trace_logger(__name__)
    
    logger.info("函数开始执行")
    
    try:
        # 模拟一些工作
        time.sleep(0.1)
        
        # 模拟一个可能出错的操作
        result = 10 / 2  # 正常情况
        
        logger.info(f"计算结果: {result}")
        return result
        
    except Exception as e:
        logger.error(f"函数执行失败: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("函数执行完成")

def example_with_custom_trace_id():
    """使用自定义trace ID的示例"""
    print(f"\n🎯 自定义Trace ID示例")
    print("-" * 30)
    
    # 使用自定义trace ID
    custom_trace_id = "custom123"
    start_trace(custom_trace_id)
    
    logger = get_trace_logger(__name__)
    logger.info(f"使用自定义trace ID: {custom_trace_id}")
    
    # 验证trace ID
    current_id = get_current_trace_id()
    print(f"当前trace ID: {current_id}")
    
    # 调用其他函数
    result = example_function_with_tracing()
    logger.info(f"函数返回结果: {result}")
    
    end_trace()

def worker_function(worker_id: int):
    """工作线程函数"""
    logger = get_trace_logger(__name__)
    
    logger.info(f"工作线程 {worker_id} 开始")
    
    # 模拟一些工作
    time.sleep(0.2)
    
    logger.info(f"工作线程 {worker_id} 完成")
    return f"worker_{worker_id}_result"

def example_multithreading():
    """多线程示例"""
    print(f"\n🧵 多线程示例")
    print("-" * 30)
    
    # 开始主trace
    main_trace_id = start_trace("main_thread")
    logger = get_trace_logger(__name__)
    
    logger.info("主线程开始，准备启动工作线程")
    
    # 启动多个工作线程
    threads = []
    for i in range(3):
        # 使用propagate_trace_to_thread确保trace ID传播到新线程
        thread = threading.Thread(
            target=propagate_trace_to_thread(worker_function),
            args=(i,)
        )
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    logger.info("所有工作线程完成")
    end_trace()

def example_error_handling():
    """错误处理示例"""
    print(f"\n🚨 错误处理示例")
    print("-" * 30)
    
    start_trace("error_demo")
    logger = get_trace_logger(__name__)
    
    logger.info("开始错误处理演示")
    
    try:
        # 模拟一个会出错的操作
        result = 10 / 0  # 这会引发ZeroDivisionError
        
    except ZeroDivisionError as e:
        # 记录错误（包含完整的堆栈跟踪）
        logger.error(f"除零错误: {str(e)}", exc_info=True)
        
    except Exception as e:
        # 记录其他错误
        logger.error(f"未知错误: {str(e)}", exc_info=True)
        
    finally:
        logger.info("错误处理演示完成")
        end_trace()

def example_performance_monitoring():
    """性能监控示例"""
    print(f"\n⏱️ 性能监控示例")
    print("-" * 30)
    
    start_trace("perf_demo")
    logger = get_trace_logger(__name__)
    
    logger.info("开始性能监控演示")
    
    # 监控一个操作的执行时间
    start_time = time.time()
    
    try:
        # 模拟一个耗时操作
        logger.info("开始执行耗时操作")
        time.sleep(0.5)  # 模拟500ms的操作
        
        duration = time.time() - start_time
        logger.info(f"操作完成，耗时: {duration:.3f}秒")
        
        # 根据性能设置不同的日志级别
        if duration > 1.0:
            logger.warning(f"操作耗时过长: {duration:.3f}秒")
        elif duration > 0.5:
            logger.info(f"操作耗时正常: {duration:.3f}秒")
        else:
            logger.debug(f"操作耗时较短: {duration:.3f}秒")
            
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"操作失败，耗时: {duration:.3f}秒，错误: {str(e)}")
        
    finally:
        end_trace()

def example_external_service_call():
    """外部服务调用示例"""
    print(f"\n🌐 外部服务调用示例")
    print("-" * 30)
    
    start_trace("external_call")
    logger = get_trace_logger(__name__)
    
    # 模拟调用外部服务
    service_url = "https://api.example.com/data"
    current_trace_id = get_current_trace_id()
    
    logger.info(f"准备调用外部服务: {service_url}")
    logger.info(f"传递trace ID: {current_trace_id}")
    
    try:
        # 在实际代码中，这里会是真正的HTTP请求
        # headers = {'X-Trace-ID': current_trace_id}
        # response = requests.get(service_url, headers=headers)
        
        # 模拟响应
        time.sleep(0.1)
        logger.info("外部服务调用成功")
        
    except Exception as e:
        logger.error(f"外部服务调用失败: {str(e)}")
        
    finally:
        end_trace()

def example_context_information():
    """上下文信息示例"""
    print(f"\n📋 上下文信息示例")
    print("-" * 30)
    
    start_trace("context_demo")
    logger = get_trace_logger(__name__)
    
    # 记录带有额外上下文信息的日志
    logger.info("用户操作", extra={
        'user_id': 'user123',
        'action': 'file_upload',
        'file_size': 1024,
        'file_type': 'image/png'
    })
    
    logger.warning("资源使用警告", extra={
        'memory_usage': '85%',
        'cpu_usage': '70%',
        'disk_usage': '60%'
    })
    
    logger.error("业务逻辑错误", extra={
        'error_code': 'INVALID_INPUT',
        'user_input': 'invalid_data',
        'validation_rules': ['required', 'format', 'length']
    })
    
    end_trace()

def main():
    """主函数 - 运行所有示例"""
    print("🔧 Trace Logger使用示例")
    print("=" * 50)
    
    # 运行各种示例
    example_basic_usage()
    example_with_custom_trace_id()
    example_multithreading()
    example_error_handling()
    example_performance_monitoring()
    example_external_service_call()
    example_context_information()
    
    print(f"\n📋 示例总结")
    print("=" * 50)
    
    summary = [
        "1. 基本使用:",
        "   - 使用 get_trace_logger(__name__) 获取logger",
        "   - 使用 start_trace() 开始新的trace",
        "   - 使用 end_trace() 结束trace",
        "",
        "2. 自定义trace ID:",
        "   - 使用 start_trace(custom_id) 设置自定义ID",
        "   - 使用 get_current_trace_id() 获取当前ID",
        "",
        "3. 多线程支持:",
        "   - 使用 propagate_trace_to_thread() 传播trace到新线程",
        "   - 每个线程保持独立的trace context",
        "",
        "4. 错误处理:",
        "   - 使用 exc_info=True 记录完整堆栈跟踪",
        "   - trace ID自动包含在错误日志中",
        "",
        "5. 性能监控:",
        "   - 记录操作开始和结束时间",
        "   - 根据性能设置不同日志级别",
        "",
        "6. 外部服务:",
        "   - 传递trace ID到外部服务",
        "   - 记录服务调用的开始和结果",
        "",
        "7. 上下文信息:",
        "   - 使用 extra 参数添加结构化信息",
        "   - 便于日志分析和监控"
    ]
    
    for item in summary:
        print(item)
    
    print(f"\n📚 更多信息:")
    print("- 详细文档: docs/system/REQUEST_TRACING_SYSTEM.md")
    print("- 测试脚本: tests/verification/test_trace_id_functionality.py")
    print("- 快速测试: tests/verification/quick_trace_test.sh")

if __name__ == "__main__":
    main()
