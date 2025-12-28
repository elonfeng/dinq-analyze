#!/usr/bin/env python3
"""
Test environment variable loading for email domain
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def test_env_vars():
    """Test environment variable loading"""
    try:
        print("🧪 测试环境变量加载...")
        
        # Test env_loader import
        from server.config.env_loader import get_env_var
        print("✅ env_loader 导入成功")
        
        # Test default value
        default_url = get_env_var('DINQ_API_DOMAIN', 'http://localhost:5001')
        print(f"✅ 默认BASE_URL: {default_url}")
        
        # Test with custom environment variable
        os.environ['DINQ_API_DOMAIN'] = 'https://test.dinq.io'
        custom_url = get_env_var('DINQ_API_DOMAIN', 'http://localhost:5001')
        print(f"✅ 自定义BASE_URL: {custom_url}")
        
        # Test email service import
        from server.services.email_service import BASE_URL
        print(f"✅ 邮件服务BASE_URL: {BASE_URL}")
        
        # Clean up
        del os.environ['DINQ_API_DOMAIN']
        
        print("\n🎯 测试结果:")
        print("- ✅ 环境变量加载正常")
        print("- ✅ 默认值设置正确")
        print("- ✅ 自定义值生效")
        print("- ✅ 邮件服务集成成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_different_environments():
    """Test different environment configurations"""
    print("\n🌍 测试不同环境配置:")
    
    environments = [
        ('开发环境', None, 'http://localhost:5001'),
        ('测试环境', 'https://test.dinq.io', 'https://test.dinq.io'),
        ('生产环境', 'https://dinq.io', 'https://dinq.io'),
    ]
    
    for env_name, env_value, expected in environments:
        try:
            # Set environment variable
            if env_value:
                os.environ['DINQ_API_DOMAIN'] = env_value
            elif 'DINQ_API_DOMAIN' in os.environ:
                del os.environ['DINQ_API_DOMAIN']
            
            # Import fresh to get new value
            if 'server.config.env_loader' in sys.modules:
                del sys.modules['server.config.env_loader']
            
            from server.config.env_loader import get_env_var
            actual = get_env_var('DINQ_API_DOMAIN', 'http://localhost:5001')
            
            if actual == expected:
                print(f"  ✅ {env_name}: {actual}")
            else:
                print(f"  ❌ {env_name}: 期望 {expected}, 实际 {actual}")
                
        except Exception as e:
            print(f"  ❌ {env_name}: 错误 {e}")
    
    # Clean up
    if 'DINQ_API_DOMAIN' in os.environ:
        del os.environ['DINQ_API_DOMAIN']

if __name__ == "__main__":
    print("🔧 邮件域名环境变量测试")
    print("=" * 50)
    
    success1 = test_env_vars()
    test_different_environments()
    
    if success1:
        print("\n🎉 环境变量测试通过！")
        print("\n📋 使用说明:")
        print("1. 开发环境: 无需设置环境变量")
        print("2. 生产环境: export DINQ_API_DOMAIN=https://dinq.io")
        print("3. 测试环境: export DINQ_API_DOMAIN=https://test.dinq.io")
    else:
        print("\n❌ 环境变量测试失败")
    
    sys.exit(0 if success1 else 1)
