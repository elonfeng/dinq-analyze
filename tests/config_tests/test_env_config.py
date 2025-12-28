#!/usr/bin/env python
# coding: UTF-8
"""
测试环境变量配置
"""

import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# 导入 dotenv 库
try:
    from dotenv import load_dotenv
    dotenv_loaded = True
except ImportError:
    dotenv_loaded = False
    print("警告: python-dotenv 未安装，无法从 .env 文件加载环境变量")

def test_env_config():
    """测试环境变量配置"""
    # 尝试加载 .env 文件
    if dotenv_loaded:
        # 加载 .env 文件
        load_dotenv()
        print("已加载 .env 文件")
    
    # 获取环境变量
    env = os.environ.get("DINQ_ENV", "development")
    domain = os.environ.get("DINQ_API_DOMAIN", "http://127.0.0.1:5001")
    
    # 打印环境变量
    print(f"\n当前环境配置:")
    print(f"DINQ_ENV = {env}")
    print(f"DINQ_API_DOMAIN = {domain}")
    
    # 根据环境变量选择不同的域名
    if env == "production":
        default_domain = "https://api.dinq.ai"
    elif env == "test":
        default_domain = "https://test-api.dinq.ai"
    else:  # development
        default_domain = "http://127.0.0.1:5001"
    
    # 如果未设置 DINQ_API_DOMAIN，使用默认值
    if "DINQ_API_DOMAIN" not in os.environ:
        domain = default_domain
        print(f"\n未设置 DINQ_API_DOMAIN，使用默认值: {domain}")
    
    # 生成示例 URL
    example_url = f"{domain}/reports/Example_Researcher_123456.json"
    print(f"\n示例报告 URL: {example_url}")
    
    # 提供使用说明
    print("\n使用说明:")
    print("1. 复制 .env.example 文件为 .env")
    print("2. 根据需要修改 .env 文件中的配置")
    print("3. 重新运行应用程序")

def main():
    """主函数"""
    print("\n=== 环境变量配置测试 ===\n")
    
    # 检查是否安装了 python-dotenv
    if not dotenv_loaded:
        print("请先安装 python-dotenv 库:")
        print("pip install python-dotenv")
        return
    
    # 运行测试
    test_env_config()
    
    print("\n测试完成")

if __name__ == "__main__":
    main()
