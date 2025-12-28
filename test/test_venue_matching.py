# coding: UTF-8
"""
    @date:  2025.04.04
    @func:  测试会议匹配在最佳合作者和代表性论文中的应用
"""
import sys
import os
import unittest
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.transform_profile import transform_data
from server.utils.conference_matcher import extract_conference_info_with_year

class TestVenueMatching(unittest.TestCase):
    def setUp(self):
        # 创建测试数据
        self.test_data = {
            "researcher": {
                "name": "Test Researcher",
                "affiliation": "Test University"
            },
            "most_frequent_collaborator": {
                "full_name": "Test Collaborator",
                "affiliation": "Collaborator University",
                "research_interests": ["AI", "Machine Learning"],
                "scholar_id": "test_id",
                "coauthored_papers": 5,
                "best_paper": {
                    "title": "A Novel Approach to CVPR 2023 Computer Vision",
                    "year": "2023",
                    "venue": "Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition",
                    "citations": 100
                }
            },
            "most_cited_paper": {
                "title": "Advances in NeurIPS 2022 Neural Networks",
                "year": "2022",
                "venue": "Advances in Neural Information Processing Systems",
                "citations": 500,
                "author_position": 1
            }
        }
        
    def test_collaborator_venue_matching(self):
        """测试最佳合作者论文的会议匹配功能"""
        # 转换数据
        transformed_data = transform_data(self.test_data)
        
        # 获取转换后的最佳合作者数据
        collaborator_data = transformed_data['researcherProfile']['dataBlocks']['closestCollaborator']
        best_paper = collaborator_data['bestCoauthoredPaper']
        
        # 验证会议匹配结果
        self.assertEqual(best_paper['fullVenue'], "Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition")
        self.assertEqual(best_paper['venue'], "CVPR 2023")
        
    def test_representative_paper_venue_matching(self):
        """测试代表性论文的会议匹配功能"""
        # 转换数据
        transformed_data = transform_data(self.test_data)
        
        # 获取转换后的代表性论文数据
        rep_paper = transformed_data['researcherProfile']['dataBlocks']['representativePaper']
        
        # 验证会议匹配结果
        self.assertEqual(rep_paper['fullVenue'], "Advances in Neural Information Processing Systems")
        self.assertEqual(rep_paper['venue'], "NeurIPS 2022")
        
    def test_venue_matching_with_title(self):
        """测试当venue不匹配时，从title中提取会议信息"""
        # 修改测试数据，使venue不包含会议信息
        test_data_copy = self.test_data.copy()
        test_data_copy['most_frequent_collaborator']['best_paper']['venue'] = "Some Journal"
        
        # 转换数据
        transformed_data = transform_data(test_data_copy)
        
        # 获取转换后的最佳合作者数据
        collaborator_data = transformed_data['researcherProfile']['dataBlocks']['closestCollaborator']
        best_paper = collaborator_data['bestCoauthoredPaper']
        
        # 验证会议匹配结果（应该从title中提取）
        self.assertEqual(best_paper['fullVenue'], "Some Journal")
        self.assertEqual(best_paper['venue'], "CVPR 2023")
        
    def test_venue_matching_with_year_addition(self):
        """测试当匹配结果没有年份时，添加论文年份"""
        # 修改测试数据，使venue只包含会议名称，不包含年份
        test_data_copy = self.test_data.copy()
        test_data_copy['most_cited_paper']['venue'] = "International Conference on Learning Representations"
        test_data_copy['most_cited_paper']['title'] = "A Study on Deep Learning"
        
        # 转换数据
        transformed_data = transform_data(test_data_copy)
        
        # 获取转换后的代表性论文数据
        rep_paper = transformed_data['researcherProfile']['dataBlocks']['representativePaper']
        
        # 验证会议匹配结果（应该添加年份）
        self.assertEqual(rep_paper['fullVenue'], "International Conference on Learning Representations")
        self.assertEqual(rep_paper['venue'], "ICLR 2022")
        
    def test_extract_conference_info_with_year(self):
        """测试extract_conference_info_with_year函数"""
        # 测试各种会议名称格式
        test_cases = [
            ("Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition", "CVPR"),
            ("Advances in Neural Information Processing Systems", "NeurIPS"),
            ("International Conference on Learning Representations", "ICLR"),
            ("CVPR 2023", "CVPR 2023"),
            ("NeurIPS 2022", "NeurIPS 2022"),
            ("ICLR'24", "ICLR 2024"),
            ("Some Random Journal", "Some Random Journal")
        ]
        
        for input_text, expected_output in test_cases:
            result = extract_conference_info_with_year(input_text)
            # 如果预期输出不包含年份，则只比较前缀部分
            if not any(char.isdigit() for char in expected_output):
                self.assertTrue(result.startswith(expected_output), 
                               f"Failed for {input_text}: expected to start with {expected_output}, got {result}")
            else:
                self.assertEqual(result, expected_output, 
                               f"Failed for {input_text}: expected {expected_output}, got {result}")

if __name__ == "__main__":
    unittest.main()
