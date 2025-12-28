# coding: UTF-8
"""
    @date:  2025.07.03
    @func:  测试新添加的生命科学和经济学领域期刊匹配功能
"""
import sys
import os
import unittest

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.utils.conference_matcher import ConferenceMatcher, extract_conference_info, extract_conference_info_with_year, extract_conference_info_tuple

class TestLifeSciencesJournals(unittest.TestCase):
    def setUp(self):
        self.matcher = ConferenceMatcher()

    def test_life_sciences_conferences_basic_matching(self):
        """测试生命科学会议基本匹配"""
        test_cases = [
            # 计算生物学会议
            ("RECOMB", "RECOMB"),
            ("RECOMB 2024", "RECOMB"),
            ("Research in Computational Molecular Biology", "RECOMB"),
            ("International Conference on Research in Computational Molecular Biology", "RECOMB"),
            ("27th Annual RECOMB", "RECOMB"),
            
            ("ISMB", "ISMB"),
            ("ISMB 2023", "ISMB"),
            ("Intelligent Systems for Molecular Biology", "ISMB"),
            ("International Conference on Intelligent Systems for Molecular Biology", "ISMB"),
            ("ISMB'24", "ISMB"),
            ("31st Annual ISMB", "ISMB"),
        ]

        for input_text, expected_conf in test_cases:
            result = self.matcher.match_conference(input_text)
            self.assertEqual(result, expected_conf, f"Failed to match conference for: {input_text}")

    def test_life_sciences_journals_basic_matching(self):
        """测试生命科学期刊基本匹配"""
        test_cases = [
            # 综合性顶级期刊
            ("Nature Methods", "Nature Methods"),
            ("Nat Methods", "Nature Methods"),
            ("Nature Communications", "Nature Communications"),
            ("Nat Commun", "Nature Communications"),
            ("eLife", "eLife"),
            ("eLife 2024", "eLife"),
            
            # 生物信息学期刊
            ("Genome Biology", "Genome Biology"),
            ("Genome Biol", "Genome Biology"),
            ("PLoS Computational Biology", "PLoS Computational Biology"),
            ("PLOS Comput Biol", "PLoS Computational Biology"),
            ("PLOS Computational Biology", "PLoS Computational Biology"),
            
            # 分子生物学期刊
            ("Molecular Cell", "Molecular Cell"),
            ("Mol Cell", "Molecular Cell"),
            ("Genes & Development", "Genes & Development"),
            ("Genes and Development", "Genes & Development"),
            ("Genes Dev", "Genes & Development"),
            ("Current Biology", "Current Biology"),
            ("Curr Biol", "Current Biology"),
            
            # 其他专业期刊
            ("Structure", "Structure"),
            ("Structure 2023", "Structure"),
            ("Cell Systems", "Cell Systems"),
            ("Cell Syst", "Cell Systems"),
            ("Molecular Systems Biology", "Molecular Systems Biology"),
            ("Mol Syst Biol", "Molecular Systems Biology"),
            ("Genome Research", "Genome Research"),
            ("Genome Res", "Genome Research"),
            ("Protein Science", "Protein Science"),
            ("Protein Sci", "Protein Science"),
            ("Cancer Cell", "Cancer Cell"),
            ("Nature Biomedical Engineering", "Nature Biomedical Engineering"),
            ("Nat Biomed Eng", "Nature Biomedical Engineering"),
            
            # 预印本
            ("bioRxiv", "bioRxiv"),
            ("bioRxiv 2024", "bioRxiv"),
        ]

        for input_text, expected_journal in test_cases:
            result = self.matcher.match_conference(input_text)
            self.assertEqual(result, expected_journal, f"Failed to match journal for: {input_text}")

    def test_life_sciences_with_year_extraction(self):
        """测试生命科学期刊带年份匹配"""
        test_cases = [
            ("Nature Methods 2024", "Nature Methods 2024"),
            ("Genome Biology 2023", "Genome Biology 2023"),
            ("RECOMB 2024", "RECOMB 2024"),
            ("Current Biology 2022", "Current Biology 2022"),
            ("bioRxiv 2025", "bioRxiv 2025"),
            ("Cell Systems 2023", "Cell Systems 2023"),
        ]

        for input_text, expected_output in test_cases:
            result = self.matcher.match_conference_with_year(input_text)
            print(f"Testing Life Sciences: {input_text} -> Got: {result}")

    def test_life_sciences_publication_processing(self):
        """测试生命科学期刊在publication processing中的表现"""
        publications = [
            {"venue": "Nature Methods 2024", "title": "Novel Sequencing Technology"},
            {"venue": "RECOMB", "title": "Algorithm for Genome Assembly"},
            {"venue": "Genome Biology", "title": "CRISPR Gene Editing"},
            {"venue": "Molecular Cell", "title": "Protein Folding Study"},
            {"venue": "bioRxiv 2023", "title": "Preprint on Gene Expression"},
            {"venue": "Current Biology", "title": "Evolutionary Biology Research"},
            {"venue": "Structure 2024", "title": "Protein Structure Analysis"},
        ]

        processed_count = 0
        for pub in publications:
            result = self.matcher.process_publication(pub)
            print(f"Processing Life Sciences: {pub['venue']} -> Result: {result}")
            if result:
                processed_count += 1

        print(f"Life Sciences total processed: {processed_count}")

class TestEconomicsJournals(unittest.TestCase):
    def setUp(self):
        self.matcher = ConferenceMatcher()

    def test_economics_top5_journals(self):
        """测试经济学'五大'期刊匹配"""
        test_cases = [
            # Top 5 经济学期刊
            ("American Economic Review", "American Economic Review"),
            ("AER", "American Economic Review"),
            ("Am Econ Rev", "American Economic Review"),
            
            ("Quarterly Journal of Economics", "Quarterly Journal of Economics"),
            ("QJE", "Quarterly Journal of Economics"),
            ("Q J Econ", "Quarterly Journal of Economics"),
            
            ("Journal of Political Economy", "Journal of Political Economy"),
            ("JPE", "Journal of Political Economy"),
            ("J Polit Econ", "Journal of Political Economy"),
            
            ("Econometrica", "Econometrica"),
            ("Econometrica 2024", "Econometrica"),
            
            ("Review of Economic Studies", "Review of Economic Studies"),
            ("REStud", "Review of Economic Studies"),
            ("Rev Econ Stud", "Review of Economic Studies"),
        ]

        for input_text, expected_journal in test_cases:
            result = self.matcher.match_conference(input_text)
            self.assertEqual(result, expected_journal, f"Failed to match Top 5 journal for: {input_text}")

    def test_economics_applied_journals(self):
        """测试经济学应用领域期刊匹配"""
        test_cases = [
            # 金融学期刊
            ("Journal of Finance", "Journal of Finance"),
            ("J Finance", "Journal of Finance"),
            ("Journal of Financial Economics", "Journal of Financial Economics"),
            ("JFE", "Journal of Financial Economics"),
            ("J Financ Econ", "Journal of Financial Economics"),
            ("Review of Financial Studies", "Review of Financial Studies"),
            ("RFS", "Review of Financial Studies"),
            ("Rev Financ Stud", "Review of Financial Studies"),
            
            # 专业领域期刊
            ("Journal of Labor Economics", "Journal of Labor Economics"),
            ("JOLE", "Journal of Labor Economics"),
            ("J Labor Econ", "Journal of Labor Economics"),
            
            ("Journal of Public Economics", "Journal of Public Economics"),
            ("J Public Econ", "Journal of Public Economics"),
            
            ("Journal of International Economics", "Journal of International Economics"),
            ("JIE", "Journal of International Economics"),
            ("J Int Econ", "Journal of International Economics"),
            
            ("Journal of Development Economics", "Journal of Development Economics"),
            ("JDE", "Journal of Development Economics"),
            ("J Dev Econ", "Journal of Development Economics"),
            
            ("Journal of Urban Economics", "Journal of Urban Economics"),
            ("JUE", "Journal of Urban Economics"),
            ("J Urban Econ", "Journal of Urban Economics"),
            
            ("Journal of Health Economics", "Journal of Health Economics"),
            ("JHE", "Journal of Health Economics"),
            ("J Health Econ", "Journal of Health Economics"),
        ]

        for input_text, expected_journal in test_cases:
            result = self.matcher.match_conference(input_text)
            self.assertEqual(result, expected_journal, f"Failed to match applied journal for: {input_text}")

    def test_economics_other_top_journals(self):
        """测试其他顶级经济学期刊匹配"""
        test_cases = [
            # 其他综合性期刊
            ("Review of Economics and Statistics", "Review of Economics and Statistics"),
            ("REstat", "Review of Economics and Statistics"),
            ("Rev Econ Stat", "Review of Economics and Statistics"),
            
            ("Economic Journal", "Economic Journal"),
            ("Econ J", "Economic Journal"),
            
            ("European Economic Review", "European Economic Review"),
            ("Eur Econ Rev", "European Economic Review"),
            
            ("Journal of the European Economic Association", "Journal of the European Economic Association"),
            ("JEEA", "Journal of the European Economic Association"),
            ("J Eur Econ Assoc", "Journal of the European Economic Association"),
            
            # 计量经济学期刊
            ("Journal of Econometrics", "Journal of Econometrics"),
            ("J Econom", "Journal of Econometrics"),
            
            ("Econometric Theory", "Econometric Theory"),
            ("Econom Theory", "Econometric Theory"),
            
            # 商学院相关期刊
            ("Management Science", "Management Science"),
            ("Manag Sci", "Management Science"),
            
            ("Operations Research", "Operations Research"),
            ("Oper Res", "Operations Research"),
        ]

        for input_text, expected_journal in test_cases:
            result = self.matcher.match_conference(input_text)
            self.assertEqual(result, expected_journal, f"Failed to match other journal for: {input_text}")

    def test_economics_working_papers(self):
        """测试经济学Working Paper匹配"""
        test_cases = [
            ("NBER Working Paper", "NBER Working Paper"),
            ("NBER WP", "NBER Working Paper"),
            ("National Bureau of Economic Research Working Paper", "NBER Working Paper"),
            ("NBER Working Paper No. 12345", "NBER Working Paper"),
            
            ("SSRN", "SSRN"),
            ("Social Science Research Network", "SSRN"),
            ("SSRN 2024", "SSRN"),
            
            ("RePEc", "RePEc"),
            ("Research Papers in Economics", "RePEc"),
            ("ideas.repec.org", "RePEc"),
        ]

        for input_text, expected_platform in test_cases:
            result = self.matcher.match_conference(input_text)
            self.assertEqual(result, expected_platform, f"Failed to match working paper for: {input_text}")

    def test_economics_with_year_extraction(self):
        """测试经济学期刊带年份匹配"""
        test_cases = [
            ("American Economic Review 2024", "American Economic Review 2024"),
            ("QJE 2023", "Quarterly Journal of Economics 2023"),
            ("Journal of Finance 2022", "Journal of Finance 2022"),
            ("NBER Working Paper 2024", "NBER Working Paper 2024"),
            ("Econometrica 2025", "Econometrica 2025"),
        ]

        for input_text, expected_output in test_cases:
            result = self.matcher.match_conference_with_year(input_text)
            print(f"Testing Economics: {input_text} -> Got: {result}")

    def test_economics_publication_processing(self):
        """测试经济学期刊在publication processing中的表现"""
        publications = [
            {"venue": "American Economic Review 2024", "title": "Macroeconomic Policy"},
            {"venue": "QJE", "title": "Labor Market Study"},
            {"venue": "Journal of Finance", "title": "Asset Pricing"},
            {"venue": "NBER Working Paper 2023", "title": "Economic Growth"},
            {"venue": "Review of Financial Studies", "title": "Corporate Finance"},
            {"venue": "Journal of Labor Economics", "title": "Wage Inequality"},
            {"venue": "SSRN", "title": "Behavioral Economics"},
        ]

        processed_count = 0
        for pub in publications:
            result = self.matcher.process_publication(pub)
            print(f"Processing Economics: {pub['venue']} -> Result: {result}")
            if result:
                processed_count += 1

        print(f"Economics total processed: {processed_count}")

    def test_edge_cases_all_fields(self):
        """测试所有领域的边界情况"""
        edge_cases = [
            # 生命科学
            ("nature methods", "Nature Methods"),  # 小写
            ("GENOME BIOLOGY", "Genome Biology"),  # 大写
            ("recomb 2024", "RECOMB"),  # 会议小写
            
            # 经济学
            ("american economic review", "American Economic Review"),  # 小写
            ("ECONOMETRICA", "Econometrica"),  # 大写
            ("nber working paper", "NBER Working Paper"),  # 小写
            
            # 不匹配的情况
            ("Random Life Science Journal", "Random Life Science Journal"),
            ("Unknown Economics Paper", "Unknown Economics Paper"),
        ]

        for input_text, expected in edge_cases:
            result = self.matcher.match_conference(input_text)
            self.assertEqual(result, expected, f"Edge case failed for: {input_text}")

class TestCombinedFields(unittest.TestCase):
    def setUp(self):
        self.matcher = ConferenceMatcher()

    def test_mixed_publication_processing(self):
        """测试混合领域的publication processing"""
        publications = [
            # 计算机科学 (已有)
            {"venue": "NeurIPS 2024", "title": "Deep Learning"},
            {"venue": "CVPR", "title": "Computer Vision"},
            
            # 医学 (已有)
            {"venue": "Nature Medicine", "title": "Gene Therapy"},
            {"venue": "NEJM 2024", "title": "Clinical Trial"},
            
            # 生命科学 (新增)
            {"venue": "Nature Methods 2024", "title": "Sequencing Technology"},
            {"venue": "RECOMB", "title": "Computational Biology"},
            
            # 经济学 (新增)
            {"venue": "American Economic Review 2024", "title": "Economic Policy"},
            {"venue": "Journal of Finance", "title": "Asset Pricing"},
        ]

        total_processed = 0
        by_field = {"CS": 0, "Medical": 0, "Life Sciences": 0, "Economics": 0}
        
        for pub in publications:
            result = self.matcher.process_publication(pub)
            if result:
                total_processed += 1
                venue = result[0]
                # 简单分类
                if venue in ['NeurIPS', 'CVPR']:
                    by_field["CS"] += 1
                elif venue in ['Nature Medicine', 'NEJM']:
                    by_field["Medical"] += 1
                elif venue in ['Nature Methods', 'RECOMB']:
                    by_field["Life Sciences"] += 1
                elif venue in ['American Economic Review', 'Journal of Finance']:
                    by_field["Economics"] += 1
            
            print(f"Mixed Processing: {pub['venue']} -> Result: {result}")

        print(f"Total processed: {total_processed}")
        print(f"By field: {by_field}")

if __name__ == "__main__":
    # 运行所有测试
    unittest.main(verbosity=2)