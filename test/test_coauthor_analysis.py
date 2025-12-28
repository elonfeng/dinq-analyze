# coding: UTF-8
"""
    @date:  2025.04.04
    @func:  测试合作者分析功能
"""
import sys
import os
import unittest
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.services.scholar.analyzer import ScholarAnalyzer

# 设置日志记录
logging.basicConfig(level=logging.DEBUG)

class TestCoauthorAnalysis(unittest.TestCase):
    def setUp(self):
        self.analyzer = ScholarAnalyzer()
        
        # 创建测试数据
        self.test_data = {
            "name": "Test Researcher",
            "abbreviated_name": "T. Researcher",
            "papers": [
                {
                    "title": "A Novel Approach to CVPR Computer Vision",
                    "year": "2023",
                    "venue": "Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition",
                    "citations": 100,
                    "authors": ["Test Researcher", "Collaborator One", "Collaborator Two"]
                },
                {
                    "title": "Advances in NeurIPS Neural Networks",
                    "year": "2022",
                    "venue": "Advances in Neural Information Processing Systems",
                    "citations": 50,
                    "authors": ["Collaborator One", "Test Researcher"]
                },
                {
                    "title": "ICLR Paper on Deep Learning",
                    "year": "2021",
                    "venue": "International Conference on Learning Representations",
                    "citations": 200,
                    "authors": ["Collaborator Two", "Test Researcher", "Collaborator Three"]
                }
            ]
        }
        
    def test_coauthor_analysis(self):
        """测试合作者分析功能"""
        # 运行合作者分析
        result = self.analyzer.analyze_coauthors(self.test_data)
        
        # 验证结果
        self.assertIsNotNone(result)
        self.assertEqual(result['total_coauthors'], 3)
        
        # 验证最频繁合作者
        top_coauthors = result['top_coauthors']
        self.assertEqual(len(top_coauthors), 3)
        
        # 验证合作者排序（按合作论文数量）
        self.assertEqual(top_coauthors[0]['name'], "Collaborator One")
        self.assertEqual(top_coauthors[0]['coauthored_papers'], 2)
        
        # 验证最佳论文
        best_paper = top_coauthors[0]['best_paper']
        self.assertEqual(best_paper['title'], "A Novel Approach to CVPR Computer Vision")
        self.assertEqual(best_paper['citations'], 100)
        
        # 验证会议匹配
        self.assertEqual(best_paper['venue'], "CVPR 2023")
        self.assertEqual(best_paper['original_venue'], 
                         "Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition")
        
    def test_empty_data(self):
        """测试空数据处理"""
        result = self.analyzer.analyze_coauthors(None)
        self.assertIsNone(result)
        
        result = self.analyzer.analyze_coauthors({})
        self.assertIsNone(result)
        
    def test_no_papers(self):
        """测试没有论文的情况"""
        data = {"name": "Test Researcher", "papers": []}
        result = self.analyzer.analyze_coauthors(data)
        self.assertIsNotNone(result)
        self.assertEqual(result['total_coauthors'], 0)
        self.assertEqual(len(result['top_coauthors']), 0)

if __name__ == "__main__":
    unittest.main()
