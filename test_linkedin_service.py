#!/usr/bin/env python3
"""
LinkedIn分析器测试脚本
"""

import asyncio
import json
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server.linkedin_analyzer.analyzer import LinkedInAnalyzer

# 测试配置
TEST_CONFIG = {
    "tavily": {
        "api_key": "tvly-dev-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # 请替换为实际的API密钥
    },
    "scrapingdog": {
        "api_key": "6879d42f3014d358eedfdcec"
    }
}

def progress_callback(step, message):
    """进度回调函数"""
    print(f"[{step}] {message}")

async def test_linkedin_analyzer():
    """测试LinkedIn分析器"""
    print("开始测试LinkedIn分析器...")
    
    # 创建LinkedIn分析器实例
    linkedin_analyzer = LinkedInAnalyzer(TEST_CONFIG)
    
    try:
        # 测试人名
        test_names = [
            "Elon Musk",
            "Mark Zuckerberg", 
            "Satya Nadella"
        ]
        
        for name in test_names:
            print(f"\n{'='*50}")
            print(f"测试分析: {name}")
            print(f"{'='*50}")
            
            # 执行完整的LinkedIn分析
            result = await linkedin_analyzer.analyze_with_progress(name, progress_callback)
            
            if result:
                print(f"✅ 分析成功!")
                print(f"LinkedIn URL: {result.get('linkedin_url', 'N/A')}")
                
                # 显示LinkedIn搜索结果
                linkedin_results = result.get('linkedin_search_results', [])
                if linkedin_results:
                    print(f"找到 {len(linkedin_results)} 个LinkedIn资料:")
                    for i, res in enumerate(linkedin_results[:3], 1):
                        print(f"  {i}. {res.get('title', 'N/A')} - {res.get('url', 'N/A')} (score: {res.get('score', 0):.3f})")
                
                extracted = result.get('extracted_info', {})
                print(f"姓名: {extracted.get('full_name', 'N/A')}")
                print(f"职位: {extracted.get('current_position', 'N/A')}")
                print(f"公司: {extracted.get('current_company', 'N/A')}")
                print(f"位置: {extracted.get('location', 'N/A')}")
                
                # 显示工作经验
                work_exp = extracted.get('work_experience', [])
                if work_exp:
                    print(f"工作经验 ({len(work_exp)} 项):")
                    for i, exp in enumerate(work_exp[:3], 1):
                        print(f"  {i}. {exp.get('title', 'N/A')} at {exp.get('company', 'N/A')}")
                
                # 显示技能
                skills = extracted.get('skills', [])
                if skills:
                    print(f"技能 ({len(skills)} 项): {', '.join(skills[:5])}")
                
                # 保存结果到文件
                filename = f"linkedin_analysis_{name.replace(' ', '_').lower()}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"结果已保存到: {filename}")
                
            else:
                print(f"❌ 分析失败: 未找到 {name} 的LinkedIn资料")
        
        print(f"\n{'='*50}")
        print("测试完成!")
        print(f"{'='*50}")
        
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 关闭分析器
        linkedin_analyzer.close()

if __name__ == "__main__":
    # 检查API密钥
    if TEST_CONFIG["tavily"]["api_key"] == "tvly-dev-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx":
        print("⚠️  请先设置正确的Tavily API密钥!")
        print("请在TEST_CONFIG中更新tavily.api_key")
        sys.exit(1)
    
    # 运行测试
    asyncio.run(test_linkedin_analyzer()) 
