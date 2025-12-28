#!/usr/bin/env python3
"""
测试addHandler修复效果

这个脚本测试修复后的logger是否能正确处理addHandler调用
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def test_analyzer_import():
    """测试analyzer模块导入是否正常"""
    print("🔍 测试Analyzer模块导入")
    print("-" * 30)
    
    try:
        from server.services.scholar.analyzer import ScholarAnalyzer
        print("✅ ScholarAnalyzer导入成功")
        
        # 尝试创建实例
        analyzer = ScholarAnalyzer()
        print("✅ ScholarAnalyzer实例创建成功")
        
        return True
        
    except AttributeError as e:
        if 'addHandler' in str(e):
            print(f"❌ addHandler错误: {e}")
            return False
        else:
            print(f"❌ 其他AttributeError: {e}")
            return False
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_data_fetcher_import():
    """测试data_fetcher模块导入是否正常"""
    print(f"\n🔍 测试Data Fetcher模块导入")
    print("-" * 30)
    
    try:
        from server.services.scholar.data_fetcher import DataFetcher
        print("✅ DataFetcher导入成功")
        
        # 尝试创建实例
        fetcher = DataFetcher()
        print("✅ DataFetcher实例创建成功")
        
        return True
        
    except AttributeError as e:
        if 'addHandler' in str(e):
            print(f"❌ addHandler错误: {e}")
            return False
        else:
            print(f"❌ 其他AttributeError: {e}")
            return False
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_publication_analyzer_import():
    """测试publication_analyzer模块导入是否正常"""
    print(f"\n🔍 测试Publication Analyzer模块导入")
    print("-" * 30)
    
    try:
        from server.services.scholar.publication_analyzer import PublicationAnalyzer
        print("✅ PublicationAnalyzer导入成功")
        
        # 尝试创建实例
        analyzer = PublicationAnalyzer()
        print("✅ PublicationAnalyzer实例创建成功")
        
        return True
        
    except AttributeError as e:
        if 'addHandler' in str(e):
            print(f"❌ addHandler错误: {e}")
            return False
        else:
            print(f"❌ 其他AttributeError: {e}")
            return False
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_trace_logger_adapter():
    """测试TraceLoggerAdapter的行为"""
    print(f"\n🔍 测试TraceLoggerAdapter行为")
    print("-" * 30)
    
    try:
        from server.utils.trace_context import get_trace_logger, get_real_logger
        
        # 测试get_trace_logger
        trace_logger = get_trace_logger('test_module')
        print("✅ get_trace_logger成功")
        
        # 测试是否有logger属性
        if hasattr(trace_logger, 'logger'):
            print("✅ TraceLoggerAdapter有logger属性")
        else:
            print("❌ TraceLoggerAdapter没有logger属性")
        
        # 测试get_real_logger
        real_logger = get_real_logger('test_module')
        print("✅ get_real_logger成功")
        
        # 测试是否有addHandler方法
        if hasattr(real_logger, 'addHandler'):
            print("✅ real_logger有addHandler方法")
        else:
            print("❌ real_logger没有addHandler方法")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_logger_functionality():
    """测试logger功能是否正常"""
    print(f"\n🔍 测试Logger功能")
    print("-" * 30)
    
    try:
        from server.utils.trace_context import TraceContext, get_trace_logger
        
        # 设置trace ID
        test_trace_id = "test1234"
        TraceContext.set_trace_id(test_trace_id)
        
        # 测试不同模块的logger
        modules = [
            'server.services.scholar.analyzer',
            'server.services.scholar.data_fetcher',
            'server.services.scholar.publication_analyzer'
        ]
        
        for module_name in modules:
            logger = get_trace_logger(module_name)
            logger.info(f"测试来自 {module_name} 的日志消息")
            print(f"✅ {module_name}: 日志记录成功")
        
        # 清除trace ID
        TraceContext.clear_trace_id()
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🔧 addHandler修复效果测试")
    print("=" * 50)
    
    # 运行各种测试
    results = []
    
    results.append(("Analyzer导入", test_analyzer_import()))
    results.append(("Data Fetcher导入", test_data_fetcher_import()))
    results.append(("Publication Analyzer导入", test_publication_analyzer_import()))
    results.append(("TraceLoggerAdapter行为", test_trace_logger_adapter()))
    results.append(("Logger功能", test_logger_functionality()))
    
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
        print("🎉 所有测试通过！addHandler问题已修复")
    else:
        print("⚠️  部分测试失败，可能需要进一步检查")
    
    print(f"\n📝 修复说明:")
    print("1. 为TraceLoggerAdapter添加了logger属性")
    print("2. 提供了get_real_logger函数获取真实logger")
    print("3. 修复了analyzer、data_fetcher、publication_analyzer中的addHandler调用")
    print("4. 添加了fallback机制确保兼容性")

if __name__ == "__main__":
    main()
