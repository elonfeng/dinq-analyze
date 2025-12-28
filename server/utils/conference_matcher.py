# coding: UTF-8
"""
    @date:  2025.04.04
    @func:  conference matcher to miscellaneous conferences.
"""
import re

class ConferenceMatcher:
    def __init__(self):
        # 定义会议名称的匹配模式
        self.conference_patterns = {
            # 计算机科学领域 -----------------------------
            # AI & ML
            'NeurIPS': [
                r'(?i)neural information processing systems?',  # 基本匹配
                r'(?i)proceedings of (?:the\s+)?neural information processing systems',  # Proceedings格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?conference on neural information processing systems?',
                r'(?i)^neurips(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 简单格式带年份和页码
                r'(?i)neurips[\'\"]?\d{2}',  # NeurIPS'23 格式
                r'(?i)\[neurips[\'\"]?\d{2}\]',  # [NeurIPS'23] 格式
                r'(?i)neurips.*\d{4}',  # 宽松匹配带年份
                r'(?i)advances in neural information processing systems \d+',  # 匹配 "Advances in neural information processing systems 33" 格式
                r'(?i)advances in neural information processing systems.*\d{4}',  # 匹配带年份的格式
                r'(?i)nips'  # 历史名称
            ],
            'ICML': [
                r'(?i)international conference on machine learning',  # 基本匹配
                r'(?i)proceedings of (?:the\s+)?international conference on machine learning',  # Proceedings格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?international conference on machine learning',
                r'(?i)^icml(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 简单格式带年份和页码
                r'(?i)icml[\'\"]?\d{2}',  # ICML'23 格式
                r'(?i)\[icml[\'\"]?\d{2}\]',  # [ICML'23] 格式
                r'(?i)icml.*\d{4}.*(?:best\s+paper)?'  # 带年份和可能的best paper标记
            ],
            'ICLR': [
                r'(?i)international conference on learning representations',  # 基本匹配
                r'(?i)proceedings of (?:the\s+)?international conference on learning representations',  # Proceedings格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?international conference on learning representations',
                r'(?i)^iclr(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 简单格式带年份和页码
                r'(?i)iclr[\'\"]?\d{2}',  # ICLR'23 格式
                r'(?i)\[iclr[\'\"]?\d{2}\]',  # [ICLR'23] 格式
                r'(?i)iclr.*\d{4}'  # 宽松匹配带年份
            ],
            'AAAI': [
                r'(?i)association for the advancement of artificial intelligence',
                r'(?i)proceedings of the aaai conference on artificial intelligence',  # proceedings格式
                r'(?i)(?:the\s+)?(?:\d+(?:st|nd|rd|th)|\w+(?:-\w+)?)\s*aaai conference',  # 匹配 "The Thirty-Eighth AAAI Conference" 格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?aaai conference',
                r'(?i)aaai conference on artificial intelligence.*\d{4}',  # 带年份的格式
                r'(?i)^aaai(?:\s*-\s*\d{2})?(?:\s+\d{4})?$',  # 匹配 "AAAI-24" 格式
                r'(?i)^aaai(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'  # 匹配简单格式，包括年份和页码
            ],
            'IJCAI': [
                r'(?i)international joint conference(?:s)? on artificial intelligence',
                r'(?i)proceedings of the (?:\d+(?:st|nd|rd|th)|\w+)(?:\s*-\s*\w+)?\s*international joint conference',  # 匹配 "Proceedings of the Thirty-Third International Joint Conference" 格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?ijcai',
                r'(?i)^ijcai(?:\s*\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'  # 匹配简单格式，包括年份和页码
            ],
            'AAMAS': [  # 新增AAMAS会议匹配
                r'(?i)international conference on autonomous agents and multiagent systems?',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?aamas',
                r'(?i)^aamas(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 匹配 "AAMAS, 2444-2446, 2024" 格式
                r'(?i)^aamas(?:\s+\d{4})?$',
                r'(?i)aamas'  # 匹配简单格式
            ],
            # Computer Vision
            'CVPR': [
                r'(?i)conference on computer vision and pattern recognition',  # 基本匹配
                r'(?i)computer vision and pattern recognition conference',  # 匹配 "XXX Conference" 格式
                r'(?i)ieee/cvf\s*conference on computer vision and pattern recognition',  # IEEE/CVF格式
                r'(?i)proceedings of (?:the\s+)?(?:ieee(?:/cvf)?\s*)?conference on computer vision and pattern',
                r'(?i)proceedings of (?:the\s+)?computer vision and pattern recognition conference',  # 匹配 proceedings + conference 格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?conference on computer vision and pattern recognition',
                r'(?i)^cvpr(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 简单格式带年份和页码
                r'(?i)cvpr[\'\"]?\d{2}',  # CVPR'23 格式
                r'(?i)\[cvpr[\'\"]?\d{2}\]',  # [CVPR'23] 格式
                r'(?i)cvpr.*\d{4}'  # 宽松匹配带年份
            ],
            'ICCV': [
                r'(?i)international conference on computer vision',  # 基本匹配
                r'(?i)ieee/cvf.*international conference on computer vision',  # IEEE/CVF格式
                r'(?i)proceedings of the (?:ieee(?:/cvf)?\s*)?international conference on computer vision',  # Proceedings格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?international conference on computer vision',  # 带序号的格式
                r'(?i)^iccv(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 简单格式带年份和页码
                r'(?i)iccv[\'\"]?\d{2}',  # ICCV'23 格式
                r'(?i)\[iccv[\'\"]?\d{2}\]',  # [ICCV'23] 格式
                r'(?i)iccv.*\d{4}',  # 宽松匹配带年份
            ],
            'ECCV': [
                r'(?i)european conference on computer vision',
                r'(?i)computer vision[\s\-–—]+eccv\s*\d{4}',  # 匹配 "Computer Vision–ECCV 2020" 格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?european conference on computer vision',
                r'(?i)eccv\s*\d{4}.*(?:conference|glasgow)',  # 匹配带地点或conference关键词的格式
                r'(?i)^eccv(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'  # 匹配简单格式，包括年份和页码
            ],
            '3DV': [
                r'(?i)international conference (?:in|on) 3d vision',  # 匹配基本名称
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:international\s*)?3dv',  # 匹配带序号的格式
                r'(?i)^3dv(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 匹配简单格式，包括年份和页码
                r'(?i)3dv[\'\"]?\d{2}',  # 匹配 "3DV'24" 格式
                r'(?i)(?:international\s+)?conference\s+(?:in|on)\s+3d\s+vision.*3dv'  # 匹配 "International Conference in 3D Vision (3DV)" 格式
            ],

            # Computer Vision & Graphics
            'ACM MM': [
                r'(?i)acm international conference on multimedia',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?acm (?:international )?conference on multimedia',
                r'(?i)^acm\s*mm(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 匹配 "ACM MM 2022, 2022" 格式
                r'(?i)acm\s*mm.*\d{4}',  # 匹配带年份的宽松格式
                r'(?i)^mm(?:\s+\d{4})?$'  # 匹配简单的MM格式
            ],
            'SIGGRAPH Asia': [
                r'(?i)siggraph\s+asia(?:\s+\d{4})?(?:\s+conference\s+papers)?',  # 匹配 "SIGGRAPH Asia 2024 Conference Papers"
                r'(?i)acm\s+siggraph\s+asia(?:\s+\d{4})?',  # 匹配带 ACM 前缀的格式
                r'(?i)^siggraph\s+asia(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'  # 匹配带页码和年份的格式
            ],
            'SIGGRAPH': [
                r'(?i)siggraph(?:\s+\d{4})?(?:\s+conference\s+papers)?',
                r'(?i)acm\s+siggraph(?:\s+\d{4})?',
                r'(?i)^siggraph(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'
            ],

            # NLP
            'ACL Findings': [
                r'(?i)findings\s+of\s+(?:the\s+)?\s*acl',  # 允许多个空格
                r'(?i)findings\s+of\s+(?:the\s+)?\s*acl\s+\d{4}(?:\s*,\s*\d{4})?',  # 匹配 "Findings of  ACL 2024, 2023" 格式
                r'(?i)acl\s+findings'  # 匹配简写格式
            ],
            'EMNLP Findings': [
                r'(?i)findings\s+of\s+(?:the\s+)?\s*emnlp',  # 允许多个空格
                r'(?i)findings\s+of\s+(?:the\s+)?\s*emnlp\s+\d{4}(?:\s*,\s*\d{4})?',  # 匹配 "Findings of EMNLP 2024, 2023" 格式
                r'(?i)emnlp\s+findings'  # 匹配简写格式
            ],
            'ACL': [
                r'(?i)association for computational linguistics',  # 基本匹配
                r'(?i)proceedings of (?:the\s+)?association for computational linguistics',  # Proceedings格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?meeting of the acl',
                r'(?i)^acl(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 简单格式带年份和页码
                r'(?i)acl[\'\"]?\d{2}',  # ACL'23 格式
                r'(?i)\[acl[\'\"]?\d{2}\]',  # [ACL'23] 格式
                r'(?i)acl.*\d{4}'  # 宽松匹配带年份
            ],
            'EMNLP': [
                r'(?i)conference on empirical methods in natural language processing',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?conference on empirical methods in nlp',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?conference on empirical methods in natural language',  # 新增匹配
                r'(?i)^emnlp(?:\s+\d{4})?(?:\s*,\s*\d{4})?$',  # 匹配年份格式
                r'(?i)emnlp\s+\d{4}'  # 匹配简单年份格式
            ],
            'NAACL': [
                r'(?i)north american chapter of the association for computational linguistics',
                r'(?i)proceedings of the (?:\d{4}\s+)?conference of the north american chapter',  # 匹配 "Proceedings of the 2019 conference of the North American chapter" 格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?conference of the naacl',
                r'(?i)naacl(?:\s*-\s*\w+)?(?:\s+\d{4})?',  # 匹配 "NAACL-HLT 2019" 格式
                r'(?i)^naacl(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'  # 匹配简单格式，包括年份和页码
            ],
            'COLM': [
                r'(?i)conference on online learning and meta-learning',
                r'(?i)colm[\s\-]+\d{4}(?:\s+oral)?(?:\s*,\s*\d{4})?',  # 修改: 增加可选的逗号和年份
                r'(?i)colm.*\d{4}.*oral(?:\s*,\s*\d{4})?',  # 修改: 增加可选的逗号和年份
                r'(?i)colm\s+\d{4}(?:\s+oral)?(?:\s*, \s*\d{4})?',  # 修改: 增加可选的oral和逗号年份
                r'(?i)colm'  # 新增: 直接匹配 "COLM 2024 Oral, 2024" 格式
            ],
            # Data Mining & Databases
            'KDD': [
                r'(?i)knowledge discovery and data mining',  # 基本匹配
                r'(?i)proceedings of (?:the\s+)?(?:\d+(?:st|nd|rd|th)?\s*)?acm sigkdd',  # Proceedings格式
                r'(?i)acm sigkdd international conference',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?conference on kdd',
                r'(?i)^kdd(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 简单格式带年份和页码
                r'(?i)kdd[\'\"]?\d{2}',  # KDD'23 格式
                r'(?i)\[kdd[\'\"]?\d{2}\]',  # [KDD'23] 格式
                r'(?i)kdd.*\d{4}'  # 宽松匹配带年份
            ],
            'SIGMOD': [
                r'(?i)international conference on management of data',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?sigmod',
                r'(?i)^sigmod(?:\s+\d{4})?$'
            ],
            'VLDB': [
                r'(?i)very large data bases',
                r'(?i)international conference on very large data bases',
                r'(?i)proceedings of the vldb endowment',  # 新增匹配VLDB Endowment格式
                r'(?i)^vldb(?:\s+\d{4})?$',
                r'(?i)vldb.*endowment.*\d{4}'  # 新增匹配带年份的Endowment格式
            ],

            # Web & IR
            'WWW': [
                r'(?i)international world wide web conferences?',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?international www conference',
                r'(?i)^www(?:\s+\d{4})?$',
                r'(?i)world wide web conference',  # 新增匹配简单格式
                r'(?i)international conference companion on world wide web',  # 新增匹配companion格式
                r'(?i)companion proceedings of the.*world wide web conference'  # 新增匹配proceedings格式
            ],
            'SIGIR': [
                r'(?i)international conference on research (?:and development )?in information retrieval',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?sigir',
                r'(?i)international acm sigir conference',  # 新增匹配ACM SIGIR格式
                r'(?i)^sigir(?:\s+\d{4})?$'
            ],

            # Security
            'CCS': [
                r'(?i)conference on computer and communications security',  # 基本匹配
                r'(?i)acm sigsac conference on computer and communications',
                r'(?i)proceedings of (?:the\s+)?(?:\d{4}\s*)?acm sigsac',  # Proceedings格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?acm ccs',
                r'(?i)^ccs(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 简单格式带年份和页码
                r'(?i)ccs[\'\"]?\d{2}',  # CCS'23 格式
                r'(?i)\[ccs[\'\"]?\d{2}\]',  # [CCS'23] 格式
                r'(?i)ccs.*\d{4}'  # 宽松匹配带年份
            ],
            'USENIX Security': [
                r'(?i)usenix security symposium',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?usenix security',
                r'(?i)^usenix(?:\s+security)?(?:\s+\d{4})?$'
            ],
            'NDSS': [
                r'(?i)network and distributed system security symposium',  # 匹配基本名称
                r'(?i)network and distributed system security symposium.*ndss',  # 匹配带NDSS缩写的格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?ndss',  # 匹配带序号的格式
                r'(?i)^ndss(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'  # 匹配简单格式，包括年份和页码
            ],
            'S&P': [
                r'(?i)symposium on security and privacy',  # 匹配基本名称
                r'(?i)ieee.*symposium on security and privacy.*s&p',  # 匹配 "44th IEEE Symposium on Security and Privacy (S&P'23)" 格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:ieee\s*)?s(?:&|and)p',  # 匹配带序号和IEEE前缀的格式
                r'(?i)^s(?:&|and)p(?:[\'\s]+\d{2,4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'  # 匹配简单格式，包括年份和页码
            ],

            # Journals
            'TPAMI': [
                r'(?i)transactions on pattern analysis and machine intelligence',
                r'(?i)ieee tpami',
                r'(?i)^tpami$'
            ],
            'IJCV': [
                r'(?i)international journal of computer vision',
                r'(?i)^ijcv$'
            ],
            'JMLR': [
                r'(?i)journal of machine learning research',
                r'(?i)^jmlr$'
            ],
            'TACL': [
                r'(?i)transactions of the association for computational linguistics',
                r'(?i)^tacl$'
            ],
            'TOG': [
                r'(?i)transactions on graphics',
                r'(?i)acm tog',
                r'(?i)^tog$'
            ],
            'OSDI': [
                r'(?i)symposium on operating systems design and implementation',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:usenix\s*)?symposium on operating systems design',  # 匹配 "18th USENIX Symposium on Operating Systems Design..."
                r'(?i)usenix.*osdi',  # 匹配包含USENIX和OSDI的组合
                r'(?i)^osdi(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 匹配简单格式，包括年份和页码
                r'(?i)osdi\s+\d{4}'  # 匹配基本年份格式
            ],
            'ISCA': [
                r'(?i)international symposium on computer architecture',
                r'(?i)proceedings of the (?:\d+(?:st|nd|rd|th)?\s*)?(?:annual\s*)?international symposium on computer',  # 新增proceedings格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:acm/ieee\s*)?international symposium on computer architecture',
                r'(?i)^isca(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',
                r'(?i)isca\s+\d{4}'
            ],
            'NSDI': [
                r'(?i)symposium on networked systems design and implementation',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:usenix\s*)?symposium on networked systems design',  # 匹配 "20th USENIX Symposium on Networked Systems Design..."
                r'(?i)usenix.*nsdi',  # 匹配包含USENIX和NSDI的组合
                r'(?i)^nsdi(?:\s*\d{2,4})?(?:\s*[\(\s].*\d{4})?',  # 匹配 "NSDI 24), 2024" 格式
                r'(?i)nsdi(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'  # 匹配带页码和年份的格式
            ],
            'PPoPP': [
                r'(?i)symposium on principles and practice of parallel programming',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?symposium on principles and practice of parallel',  # 匹配 "24th Symposium on Principles and Practice of Parallel..."
                r'(?i)principles and practice of parallel programming',
                r'(?i)^ppopp(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 匹配简单格式，包括年份和页码
                r'(?i)ppopp\s+\d{4}'  # 匹配基本年份格式
            ],
            'ICDE': [
                r'(?i)international conference on data engineering',
                r'(?i)ieee.*international conference on data engineering.*icde',  # 匹配 "2022 IEEE 38th International Conference on Data Engineering (ICDE)"
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?icde',
                r'(?i)^icde(?:\s+\d{4})?$'
            ],
            'MICCAI': [
                r'(?i)international conference on medical image computing and computer[- ]assisted',  # 匹配主标题
                r'(?i)medical image computing and computer[- ]assisted intervention',  # 匹配完整会议名
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?miccai',  # 匹配带序号的格式
                r'(?i)^miccai(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 匹配简单格式，包括年份和页码
                r'(?i)miccai\s+\d{4}'  # 匹配基本年份格式
            ],
            'ICRA': [
                r'(?i)international conference on robotics and automation',
                r'(?i)ieee.*international conference on robotics and automation.*icra',  # 匹配 "2024 IEEE International Conference on Robotics and Automation (ICRA)"
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:ieee\s*)?icra',  # 匹配带序号和IEEE前缀的格式
                r'(?i)^icra(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 匹配简单格式，包括年份和页码
                r'(?i)icra\s+\d{4}'  # 匹配基本年份格式
            ],
            'US Patent': [
                r'(?i)us\s*patent\s*[\d,]+',  # 匹配 "US Patent 11,501,337" 格式
                r'(?i)u\.?s\.?\s*pat\.?\s*[\d,]+',  # 匹配缩写形式 "U.S. Pat. 11,501,337"
                r'(?i)united\s*states\s*patent\s*[\d,]+',  # 匹配完整名称
                r'(?i)patent\s*#?\s*[\d,]+',  # 匹配简单格式 "Patent #11,501,337"
            ],
            'IROS': [
                r'(?i)international conference on intelligent robots and systems',
                r'(?i)ieee/rsj.*international conference on intelligent robots',  # 匹配 "IEEE/RSJ International Conference on Intelligent Robots and Systems"
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:ieee/rsj\s*)?iros',  # 匹配带序号和IEEE/RSJ前缀的格式
                r'(?i)^iros(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 匹配简单格式，包括年份和页码
                r'(?i)iros\s+\d{4}'  # 匹配基本年份格式
            ],
            # HCI
            'CHI': [
                r'(?i)chi conference on human factors in computing systems',
                r'(?i)conference on human factors in computing systems.*chi',  # 新增匹配 "2025 Conference on Human Factors in Computing Systems (CHI)" 格式
                r'(?i)proceedings of the chi conference',  # 匹配 Proceedings 格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?chi conference',
                r'(?i)^chi(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'  # 匹配简单格式，包括年份和页码
            ],
            # Crypto
            'CRYPTO': [
                r'(?i)annual international cryptology conference',  # 匹配 "Annual International Cryptology Conference"
                r'(?i)cryptology\s+eprint\s+archive',  # 匹配 "Cryptology ePrint Archive"
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?crypto(?:logy)?(?:\s+conference)?',  # 匹配带序号的格式
                r'(?i)^crypto(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'  # 匹配简单格式，包括年份和页码
            ],
            # Theory
            'STOC': [
                r'(?i)symposium on theory of computing',  # 匹配基本名称
                r'(?i)proceedings of the (?:\d+(?:st|nd|rd|th)?\s*)?(?:annual\s*)?acm symposium on theory of computing',  # 匹配完整proceedings格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:acm\s*)?stoc',  # 匹配带序号和ACM前缀的格式
                r'(?i)^stoc(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'  # 匹配简单格式，包括年份和页码
            ],
            'FOCS': [
                r'(?i)foundations of computer science',  # 匹配基本名称
                r'(?i)ieee.*annual symposium on foundations of computer science.*focs',  # 匹配 "2018 IEEE 59th Annual Symposium on Foundations of Computer Science (FOCS" 格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:ieee\s*)?symposium on foundations',  # 匹配带序号和IEEE前缀的格式
                r'(?i)^focs(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'  # 匹配简单格式，包括年份和页码
            ],
            # Software Engineering
            'ASE': [
                r'(?i)automated software engineering',  # 匹配基本名称
                r'(?i)ieee/acm.*international conference on automated software',  # 匹配 "IEEE/ACM International Conference on Automated Software Engineering" 格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:ieee/acm\s*)?ase',  # 匹配带序号和IEEE/ACM前缀的格式
                r'(?i)^ase(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'  # 匹配简单格式，包括年份和页码
            ],
            # Signal Processing
            'ICASSP': [
                r'(?i)international conference on acoustics, speech,? and signal processing',  # 匹配完整名称
                r'(?i)ieee.*international conference on acoustics.*icassp',  # 匹配带IEEE的完整名称
                r'(?i)icassp\s+\d{4}[\s\-]+\d{4}\s+ieee',  # 匹配 "ICASSP 2025-2025 IEEE" 格式
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:ieee\s*)?icassp',  # 匹配带序号和IEEE前缀的格式
                r'(?i)^icassp(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 匹配简单格式，包括年份和页码
                r'(?i)icassp.*\d{4}.*acoustics',  # 匹配包含年份和acoustics的组合
                r'(?i)icassp[\'\"]?\d{2}'  # 匹配 "ICASSP'21" 格式
            ],
            # Top Journals
            'Science': [
                r'(?i)^science$',  # 匹配纯 Science
                r'(?i)^science[\s,]+\d+\s*\(\d+\)',  # 匹配 "Science 330 (6002)" 格式
                r'(?i)^science(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 匹配带年份和页码的格式
                r'(?i)science.*\d+.*\d+.*\d{4}'  # 匹配包含卷号、期号、年份的宽松格式
            ],
            'Nature': [
                r'(?i)^nature$',  # 匹配纯 Nature
                r'(?i)^nature[\s,]+\d+\s*\(\d+\)',  # 匹配 "nature 529 (7587)" 格式
                r'(?i)^nature(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',  # 匹配带年份和页码的格式
                r'(?i)nature.*\d+.*\d+.*\d{4}'  # 匹配包含卷号、期号、年份的宽松格式
            ],
            
            
            # 医学领域 -----------------------------
            # Medical Journals - Top Tier 
            'NEJM': [
                r'(?i)new england journal of medicine',
                r'(?i)^nejm$',
                r'(?i)^nejm\s+\d{4}$', 
                r'(?i)n\s*engl\s*j\s*med'
            ],
            'Lancet': [
                r'(?i)^the\s+lancet$',
                r'(?i)^lancet$',
                r'(?i)^lancet\s+\d{4}$'  
            ],
            'JAMA': [
                r'(?i)journal of the american medical association',
                r'(?i)^jama$',
                r'(?i)^jama\s+\d{4}$'
            ],
            'Nature Medicine': [
                r'(?i)nature medicine',
                r'(?i)^nat\s+med$',
                r'(?i)^nature\s+medicine$',
                r'(?i)nature\s+med(?:icine)?'
            ],
            'Cell': [
                r'(?i)^cell$',
                r'(?i)^cell\s+\d{4}$',
                r'(?i)cell\s+\d+\s*\(\d+\)'
            ],
            'Science Translational Medicine': [
                r'(?i)science translational medicine',
                r'(?i)^sci\s+transl\s+med$',
                r'(?i)science\s+transl\s+med'
            ],
            'BMJ': [
                r'(?i)british medical journal',
                r'(?i)^bmj$',
                r'(?i)^bmj\s+\d{4}$'
            ],

            # Medical Specialty Journals
            'Nature Genetics': [
                r'(?i)nature genetics',
                r'(?i)^nat\s+genet$',
                r'(?i)^nature\s+genetics$'
            ],
            'Nature Biotechnology': [
                r'(?i)nature biotechnology',
                r'(?i)^nat\s+biotechnol$',
                r'(?i)^nature\s+biotechnology$'
            ],
            'Nature Immunology': [
                r'(?i)nature immunology',
                r'(?i)^nat\s+immunol$',
                r'(?i)^nature\s+immunology$'
            ],
            'PNAS': [
                r'(?i)proceedings of the national academy of sciences',
                r'(?i)^pnas$',
                r'(?i)^pnas\s+\d{4}$',  # 添加带年份匹配
                r'(?i)proc\s+natl\s+acad\s+sci'
            ],
            'Circulation': [
                r'(?i)^circulation$',
                r'(?i)^circulation\s+\d{4}$'
            ],
            'Journal of Clinical Investigation': [
                r'(?i)journal of clinical investigation',
                r'(?i)^j\s+clin\s+invest$',
                r'(?i)^jci$'
            ],
            'Immunity': [
                r'(?i)^immunity$',
                r'(?i)^immunity\s+\d{4}$'
            ],
            'Cancer Cell': [
                r'(?i)cancer cell',
                r'(?i)^cancer\s+cell$'
            ],
            'Neuron': [
                r'(?i)^neuron$',
                r'(?i)^neuron\s+\d{4}$'
            ],

            # Medical Conferences  
            'MICCAI': [
                r'(?i)international conference on medical image computing and computer[- ]assisted',
                r'(?i)medical image computing and computer[- ]assisted intervention',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?miccai',
                r'(?i)^miccai(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',
                r'(?i)^miccai\s+\d{4}$'  # 添加简单年份匹配
            ],
            'MIDL': [
                r'(?i)medical imaging with deep learning',
                r'(?i)^midl$',
                r'(?i)^midl\s+\d{4}$'
            ],
            'ISBI': [
                r'(?i)international symposium on biomedical imaging',
                r'(?i)ieee.*international symposium on biomedical imaging',
                r'(?i)^isbi$',
                r'(?i)^isbi\s+\d{4}$'
            ],
            'AMIA': [
                r'(?i)american medical informatics association',
                r'(?i)^amia$',
                r'(?i)amia.*annual'
            ],

            # Bioinformatics Journals
            'Bioinformatics': [
                r'(?i)^bioinformatics$',
                r'(?i)^bioinformatics\s+\d{4}$'
            ],
            'Nature Methods': [
                r'(?i)nature methods',
                r'(?i)^nat\s+methods$',
                r'(?i)^nature\s+methods$'
            ],
            'Genome Research': [
                r'(?i)genome research',
                r'(?i)^genome\s+res$',
                r'(?i)^genome\s+research$'
            ],
            'Nucleic Acids Research': [
                r'(?i)nucleic acids research',
                r'(?i)^nucleic\s+acids\s+res$',
                r'(?i)^nar$'
            ],

            # Public Health
            'Lancet Global Health': [
                r'(?i)lancet global health',
                r'(?i)^lancet\s+glob\s+health$',
                r'(?i)^lancet\s+global\s+health$'
            ],
            'Lancet Public Health': [
                r'(?i)lancet public health',
                r'(?i)^lancet\s+public\s+health$'
            ],
            
            
            # 生命科学领域 -----------------------------

            # 计算生物学顶级会议
            'RECOMB': [
                r'(?i)research in computational molecular biology',
                r'(?i)international conference on research in computational molecular biology',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?recomb',
                r'(?i)^recomb(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$'
            ],
            'ISMB': [
                r'(?i)intelligent systems for molecular biology',
                r'(?i)international conference on intelligent systems for molecular biology',
                r'(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?ismb',
                r'(?i)^ismb(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$',
                r'(?i)ismb[\'\"]?\d{2}'
            ],

            'eLife': [
                r'(?i)^elife$',
                r'(?i)^elife\s+\d{4}$'
            ],

            # 生物信息学顶级期刊
            'Genome Biology': [
                r'(?i)genome biology',
                r'(?i)^genome\s+biol$',
                r'(?i)^genome\s+biology$'
            ],

            'PLoS Computational Biology': [
                r'(?i)plos computational biology',
                r'(?i)^plos\s+comput\s+biol$',
                r'(?i)^plos\s+computational\s+biology$'
            ],

            # 分子生物学顶级期刊  
            'Molecular Cell': [
                r'(?i)molecular cell',
                r'(?i)^mol\s+cell$',
                r'(?i)^molecular\s+cell$'
            ],
            'Genes & Development': [
                r'(?i)genes (?:and|&) development',
                r'(?i)^genes\s+dev$',
                r'(?i)^genes\s+(?:and|&)\s+development$'
            ],
            'Current Biology': [
                r'(?i)current biology',
                r'(?i)^curr\s+biol$',
                r'(?i)^current\s+biology$'
            ],

            # 结构生物学顶级期刊
            'Structure': [
                r'(?i)^structure$',
                r'(?i)^structure\s+\d{4}$'
            ],

            # 系统生物学顶级期刊
            'Cell Systems': [
                r'(?i)cell systems',
                r'(?i)^cell\s+syst$',
                r'(?i)^cell\s+systems$'
            ],
            'Molecular Systems Biology': [
                r'(?i)molecular systems biology',
                r'(?i)^mol\s+syst\s+biol$',
                r'(?i)^molecular\s+systems\s+biology$'
            ],

            # 基因组学顶级期刊
            'Genome Research': [
                r'(?i)genome research',
                r'(?i)^genome\s+res$',
                r'(?i)^genome\s+research$'
            ],

            # 蛋白质科学顶级期刊
            'Protein Science': [
                r'(?i)protein science',
                r'(?i)^protein\s+sci$',
                r'(?i)^protein\s+science$'
            ],

            # 癌症研究顶级期刊
            'Cancer Cell': [
                r'(?i)cancer cell',
                r'(?i)^cancer\s+cell$'
            ],

            # 生物工程顶级期刊
            'Nature Biomedical Engineering': [
                r'(?i)nature biomedical engineering',
                r'(?i)^nat\s+biomed\s+eng$',
                r'(?i)^nature\s+biomedical\s+engineering$'
            ],
            'Nature Methods': [
                r'(?i)nature methods',
                r'(?i)^nat\s+methods$',
                r'(?i)^nature\s+methods$'
            ],

            'Nature Communications': [
                r'(?i)nature communications',
                r'(?i)^nat\s+commun$',
                r'(?i)^nature\s+communications$'
            ],

            'bioRxiv': [
                r'(?i)^biorxiv$',
                r'(?i)^biorxiv\s+\d{4}$',
                r'(?i)biorxiv.*\d{4}'
            ],

            # 经济学领域 - 顶级期刊 -----------------------------
            # Top 5经济学期刊（被称为"五大"）
            'American Economic Review': [
                r'(?i)american economic review',
                r'(?i)^aer$',
                r'(?i)^am\s+econ\s+rev$',
                r'(?i)^american\s+economic\s+review$'
            ],
            'Quarterly Journal of Economics': [
                r'(?i)quarterly journal of economics',
                r'(?i)^qje$',
                r'(?i)^q\s+j\s+econ$',
                r'(?i)^quarterly\s+journal\s+of\s+economics$'
            ],
            'Journal of Political Economy': [
                r'(?i)journal of political economy',
                r'(?i)^jpe$',
                r'(?i)^j\s+polit\s+econ$',
                r'(?i)^journal\s+of\s+political\s+economy$'
            ],
            'Econometrica': [
                r'(?i)^econometrica$',
                r'(?i)^econometrica\s+\d{4}$'
            ],
            'Review of Economic Studies': [
                r'(?i)review of economic studies',
                r'(?i)^restud$',
                r'(?i)^rev\s+econ\s+stud$',
                r'(?i)^review\s+of\s+economic\s+studies$'
            ],

            # 其他顶级综合性经济学期刊
            'Review of Economics and Statistics': [
                r'(?i)review of economics and statistics',
                r'(?i)^restat$',
                r'(?i)^rev\s+econ\s+stat$',
                r'(?i)^review\s+of\s+economics\s+and\s+statistics$'
            ],
            'Economic Journal': [
                r'(?i)economic journal',
                r'(?i)^econ\s+j$',
                r'(?i)^economic\s+journal$'
            ],
            'European Economic Review': [
                r'(?i)european economic review',
                r'(?i)^eur\s+econ\s+rev$',
                r'(?i)^european\s+economic\s+review$'
            ],
            'Journal of the European Economic Association': [
                r'(?i)journal of the european economic association',
                r'(?i)^jeea$',
                r'(?i)^j\s+eur\s+econ\s+assoc$'
            ],

            # 顶级应用经济学期刊
            'Journal of Finance': [
                r'(?i)journal of finance',
                r'(?i)^j\s+finance$',
                r'(?i)^journal\s+of\s+finance$'
            ],
            'Journal of Financial Economics': [
                r'(?i)journal of financial economics',
                r'(?i)^jfe$',
                r'(?i)^j\s+financ\s+econ$',
                r'(?i)^journal\s+of\s+financial\s+economics$'
            ],
            'Review of Financial Studies': [
                r'(?i)review of financial studies',
                r'(?i)^rfs$',
                r'(?i)^rev\s+financ\s+stud$',
                r'(?i)^review\s+of\s+financial\s+studies$'
            ],
            'Journal of Labor Economics': [
                r'(?i)journal of labor economics',
                r'(?i)^jole$',
                r'(?i)^j\s+labor\s+econ$',
                r'(?i)^journal\s+of\s+labor\s+economics$'
            ],
            'Journal of Public Economics': [
                r'(?i)journal of public economics',
                r'(?i)^jpe$',
                r'(?i)^j\s+public\s+econ$',
                r'(?i)^journal\s+of\s+public\s+economics$'
            ],
            'Journal of International Economics': [
                r'(?i)journal of international economics',
                r'(?i)^jie$',
                r'(?i)^j\s+int\s+econ$',
                r'(?i)^journal\s+of\s+international\s+economics$'
            ],
            'Journal of Development Economics': [
                r'(?i)journal of development economics',
                r'(?i)^jde$',
                r'(?i)^j\s+dev\s+econ$',
                r'(?i)^journal\s+of\s+development\s+economics$'
            ],
            'Journal of Urban Economics': [
                r'(?i)journal of urban economics',
                r'(?i)^jue$',
                r'(?i)^j\s+urban\s+econ$',
                r'(?i)^journal\s+of\s+urban\s+economics$'
            ],
            'Journal of Environmental Economics and Management': [
                r'(?i)journal of environmental economics and management',
                r'(?i)^jeem$',
                r'(?i)^j\s+environ\s+econ\s+manag$'
            ],
            'Journal of Health Economics': [
                r'(?i)journal of health economics',
                r'(?i)^jhe$',
                r'(?i)^j\s+health\s+econ$',
                r'(?i)^journal\s+of\s+health\s+economics$'
            ],

            # 顶级计量经济学期刊
            'Journal of Econometrics': [
                r'(?i)journal of econometrics',
                r'(?i)^j\s+econom$',
                r'(?i)^journal\s+of\s+econometrics$'
            ],
            'Econometric Theory': [
                r'(?i)econometric theory',
                r'(?i)^econom\s+theory$',
                r'(?i)^econometric\s+theory$'
            ],

            # 商学院相关顶级期刊
            'Management Science': [
                r'(?i)management science',
                r'(?i)^manag\s+sci$',
                r'(?i)^management\s+science$'
            ],
            'Operations Research': [
                r'(?i)operations research',
                r'(?i)^oper\s+res$',
                r'(?i)^operations\s+research$'
            ],

            # Working Paper系列（在经济学中很重要）
            'NBER Working Paper': [
                r'(?i)nber working paper',
                r'(?i)national bureau of economic research.*working paper',
                r'(?i)^nber\s+wp$',
                r'(?i)nber.*working.*paper'
            ],
            'SSRN': [
                r'(?i)social science research network',
                r'(?i)^ssrn$',
                r'(?i)ssrn.*\d{4}'
            ],
            'RePEc': [
                r'(?i)research papers in economics',
                r'(?i)^repec$',
                r'(?i)ideas\.repec\.org'
            ],
        }

        # List of standardized top-tier conference names
        self.top_tier_conferences = [
            # 计算机科学领域 -----------------------------
            # AI & ML
            'NeurIPS', 'ICML', 'ICLR', 'AAAI', 'IJCAI', 'COLT', 'AAMAS',  # 添加AAMAS
            # Computer Vision & Graphics
            'CVPR', 'ECCV', 'ICCV', 'SIGGRAPH', 'SIGGRAPH Asia', 'ACM MM', '3DV',
            # NLP
            'ACL', 'ACL Findings', 'EMNLP', 'EMNLP Findings', 'NAACL', 'COLM', 'ICASSP',
            # Web & IR
            'WWW', 'SIGIR', 'WSDM',
            # Data Mining & Databases
            'ICDM', 'SIGMOD', 'VLDB', 'ICDE', 'KDD',
            # Networks
            'SIGCOMM', 'INFOCOM', 'NSDI',
            # Security
            'CCS', 'USENIX Security', 'S&P', 'NDSS',
            # Software Engineering
            'ICSE', 'FSE', 'ASE',
            # Architecture
            'ISCA', 'MICRO', 'ASPLOS', 'OSDI', 'PPoPP',
            # HCI
            'CHI', 'UbiComp',
            # Theory
            'STOC', 'FOCS', 'SODA',
            # Medical
            'MICCAI',
            # Robotics
            'ICRA', 'IROS',
            # Cyrpto
            "CRYPTO",
            # Patent
            'US Patent',
            # Signal Processing
            'ICASSP',  # 添加ICASSP到会议列表
            # Top Journals
            'Nature', 'Science',  # 确保两个顶级期刊都在列表中
            
            # 医学领域 -----------------------------
            'NEJM', 'Lancet', 'JAMA', 'Nature Medicine', 'Cell', 
            'Science Translational Medicine', 'BMJ', 'Nature Genetics',
            'Nature Biotechnology', 'Nature Immunology', 'PNAS',
            'Circulation', 'Journal of Clinical Investigation', 'Immunity',
            'Cancer Cell', 'Neuron', 'MICCAI', 'MIDL', 'ISBI', 'AMIA',
            'Bioinformatics', 'Nature Methods', 'Genome Research',
            'Nucleic Acids Research', 'Lancet Global Health', 'Lancet Public Health',
            
            # 生命科学领域 -----------------------------
            'RECOMB', 'ISMB', 'bioRxiv','Nature Methods', 'Nature Communications',
            'eLife', 
            'Genome Biology', 'PLoS Computational Biology',  
            'Molecular Cell', 'Genes & Development', 'Current Biology',  
            'Structure', 'Cell Systems', 'Molecular Systems Biology',  
            'Genome Research', 'Protein Science', 'Cancer Cell',  
            'Nature Biomedical Engineering', 
            
            # 经济学领域 -----------------------------
            'American Economic Review', 'Quarterly Journal of Economics', 'Journal of Political Economy', 
            'Econometrica', 'Review of Economic Studies', 
            'Review of Economics and Statistics', 'Economic Journal', 'European Economic Review', 
            'Journal of the European Economic Association', 
            'Journal of Finance', 'Journal of Financial Economics', 'Review of Financial Studies', 
            'Journal of Labor Economics', 'Journal of Public Economics', 'Journal of International Economics',
            'Journal of Development Economics', 'Journal of Urban Economics', 'Journal of Environmental Economics and Management',
            'Journal of Health Economics', 
            'Journal of Econometrics', 'Econometric Theory', 
            'Management Science', 'Operations Research', 
            'NBER Working Paper', 'SSRN', 'bioRxiv', 
        ]

        # Initialize conference counter
        self.conference_count = {conf: 0 for conf in self.top_tier_conferences}
        self.top_tier_papers = 0

    def match_conference(self, venue_str):
        """
        匹配会议名称，将各种格式标准化

        Args:
            venue_str (str): 会议名称字符串

        Returns:
            str: 标准化的会议名称
        """
        if not venue_str:
            return venue_str

        # 清理特殊字符
        venue_str = venue_str.strip().replace('\xa0', ' ').replace('–', '-').replace('—', '-')

        # 遍历所有会议的匹配模式
        for standard_name, patterns in self.conference_patterns.items():
            for pattern in patterns:
                if re.search(pattern, venue_str):
                    return standard_name

        return venue_str

    def match_conference_with_year(self, text_str):
        """
        匹配会议名称，将各种格式标准化，并尝试提取年份

        Args:
            text_str (str): 论文标题或会议名称字符串

        Returns:
            str: 标准化的会议名称，如果有年份则返回“会议名称 年份”格式
        """
        if not text_str:
            return text_str

        # 清理特殊字符
        text_str = text_str.strip().replace('\xa0', ' ').replace('–', '-').replace('—', '-')

        # 尝试从字符串中提取年份，优先考虑2000年以后的年份
        year = None

        # 首先尝试匹配2000年以后的年份
        recent_year_match = re.search(r'(?:20)\d{2}', text_str)  # 匹配2000-2099年的格式
        if recent_year_match:
            year = recent_year_match.group(0)

        # 如果没有找到2000年以后的年份，再尝试匹配1900年代的年份
        if not year:
            older_year_match = re.search(r'(?:19)\d{2}', text_str)  # 匹配1900-1999年的格式
            # 确保不是在匹配页码范围（通常页码不会是年份格式）
            if older_year_match:
                # 检查是否在页码范围内
                page_range_match = re.search(r'\d+\s*[-–—]\s*' + older_year_match.group(0), text_str)
                if not page_range_match:
                    year = older_year_match.group(0)

        # 尝试匹配简短年份格式 (如 '23, '24)
        if not year:
            # 改进的正则表达式，可以匹配更多格式，如ICLR'24, CVPR'22等
            short_year_match = re.search(r'[\'\"](\d{2})|\((\d{2})\)', text_str)
            if short_year_match:
                # 获取第一个非空的匹配组
                short_year = next((group for group in short_year_match.groups() if group is not None), None)
                if short_year:  # 只有当成功提取到年份时才处理
                    # 假设20xx年，除非是明显的过去年份
                    current_year = 2025  # 使用当前年份作为基准
                    prefix = "20" if int(short_year) <= int(str(current_year)[2:]) else "19"
                    year = prefix + short_year

        # 遍历所有会议的匹配模式
        conf = self.match_conference(text_str)

        # 如果有年份，返回“会议名称 年份”格式
        if year:
            return f"{conf} {year}"

        # 如果没有年份，只返回会议名称
        # 如果会议名称与原始文本相同，说明没有匹配到会议
        # 在这种情况下，如果文本中包含了会议名称，则只返回会议名称
        for standard_name in self.conference_patterns.keys():
            if standard_name in conf and standard_name != conf:
                return standard_name

        return conf

    def _match_conference_with_year_tuple(self, text_str):
        """
        内部方法，匹配会议名称和年份，返回元组

        Args:
            text_str (str): 论文标题或会议名称字符串

        Returns:
            tuple: (标准化的会议名称, 年份) - 如果没有找到年份，年份为None
        """
        if not text_str:
            return (text_str, None)

        # 清理特殊字符
        text_str = text_str.strip().replace('\xa0', ' ').replace('–', '-').replace('—', '-')

        # 尝试从字符串中提取年份，优先考虑2000年以后的年份
        year = None

        # 首先尝试匹配2000年以后的年份
        recent_year_match = re.search(r'(?:20)\d{2}', text_str)  # 匹配2000-2099年的格式
        if recent_year_match:
            year = recent_year_match.group(0)

        # 如果没有找到2000年以后的年份，再尝试匹配1900年代的年份
        if not year:
            older_year_match = re.search(r'(?:19)\d{2}', text_str)  # 匹配1900-1999年的格式
            # 确保不是在匹配页码范围（通常页码不会是年份格式）
            if older_year_match:
                # 检查是否在页码范围内
                page_range_match = re.search(r'\d+\s*[-–—]\s*' + older_year_match.group(0), text_str)
                if not page_range_match:
                    year = older_year_match.group(0)

        # 尝试匹配简短年份格式 (如 '23, '24)
        if not year:
            # 改进的正则表达式，可以匹配更多格式，如ICLR'24, CVPR'22等
            short_year_match = re.search(r'[\'\"](\d{2})|\((\d{2})\)', text_str)
            if short_year_match:
                # 获取第一个非空的匹配组
                short_year = next((group for group in short_year_match.groups() if group is not None), None)
                if short_year:  # 只有当成功提取到年份时才处理
                    # 假设20xx年，除非是明显的过去年份
                    current_year = 2025  # 使用当前年份作为基准
                    prefix = "20" if int(short_year) <= int(str(current_year)[2:]) else "19"
                    year = prefix + short_year

        # 遍历所有会议的匹配模式
        conf = self.match_conference(text_str)
        return (conf, year)

    def process_publication(self, pub):
        """
        Process a publication and update conference statistics.

        Args:
            pub (dict): Publication dictionary containing venue information and/or title.

        Returns:
            tuple or None: (Matched conference name, year) if it's a top-tier venue, None otherwise.
        """
        # 首先尝试从venue匹配
        venue = pub.get('venue', '')
        matched_conf, year = self._match_conference_with_year_tuple(venue)

        # 如果venue没有匹配到顶会，尝试从title匹配
        if matched_conf not in self.top_tier_conferences and 'title' in pub:
            title_match, title_year = self._match_conference_with_year_tuple(pub.get('title', ''))
            if title_match in self.top_tier_conferences:
                matched_conf, year = title_match, title_year

        # 如果还没有年份但有year字段，使用year字段
        if year is None and 'year' in pub:
            try:
                year = str(pub['year'])
            except (ValueError, TypeError):
                pass

        if matched_conf and matched_conf in self.top_tier_conferences:
            self.top_tier_papers += 1
            self.conference_count[matched_conf] += 1
            return (matched_conf, year)

        return None

    def get_stats(self):
        """
        Get the conference statistics.

        Returns:
            dict: Dictionary containing conference statistics.
        """
        return {
            'top_tier_papers': self.top_tier_papers,
            'conference_breakdown': self.conference_count
        }


def extract_conference_info(text):
    """
    从文本中提取会议信息的便捷函数

    Args:
        text (str): 包含会议信息的文本

    Returns:
        str: 标准化的会议名称
    """
    matcher = ConferenceMatcher()
    return matcher.match_conference(text)


def extract_conference_info_with_year(text):
    """
    从文本中提取会议信息和年份的便捷函数

    Args:
        text (str): 包含会议信息的文本

    Returns:
        str: 标准化的会议名称，如果有年份则返回“会议名称 年份”格式
    """
    matcher = ConferenceMatcher()
    return matcher.match_conference_with_year(text)


def extract_conference_info_tuple(text):
    """
    从文本中提取会议信息和年份的便捷函数，返回元组

    Args:
        text (str): 包含会议信息的文本

    Returns:
        tuple: (会议缩写, 年份) - 如果没有找到年份，年份为None
    """
    matcher = ConferenceMatcher()
    return matcher._match_conference_with_year_tuple(text)


def handle_neurips_format(venue_str):
    """
    专门处理NeurIPS格式的venue字符串，特别是处理带有卷号和页码的格式
    例如："Advances in neural information processing systems 33, 1877-1901, 2020"

    Args:
        venue_str (str): 包含NeurIPS信息的venue字符串

    Returns:
        str: 处理后的格式，例如 "NeurIPS 2020"
    """
    if not venue_str or not isinstance(venue_str, str):
        return venue_str

    # 检查是否是NeurIPS格式
    if not re.search(r'(?i)neural information processing|neurips|nips', venue_str):
        return venue_str

    # 尝试提取年份，优先考虑2000年以后的年份
    year = None
    recent_year_match = re.search(r'(?:20)\d{2}', venue_str)
    if recent_year_match:
        year = recent_year_match.group(0)

    # 如果没有找到2000年以后的年份，再尝试匹配1900年代的年份，但要避免页码
    if not year:
        # 尝试匹配逗号后面的年份，这通常是出版年份
        comma_year_match = re.search(r',\s*(\d{4})(?:\s*$|[^\d])', venue_str)
        if comma_year_match:
            year = comma_year_match.group(1)
        else:
            # 尝试匹配其他位置的年份，但避免页码范围
            older_year_match = re.search(r'(?:19)\d{2}', venue_str)
            if older_year_match:
                # 检查是否在页码范围内
                page_range_match = re.search(r'\d+\s*[-–—]\s*' + older_year_match.group(0), venue_str)
                if not page_range_match:
                    year = older_year_match.group(0)

    # 返回标准化的格式
    if year:
        return f"NeurIPS {year}"
    else:
        return "NeurIPS"



if __name__ == "__main__":
    matcher = ConferenceMatcher()
    # print(matcher.match_conference("[ICLR'25] The Thirteenth International Conference on Learning Representations"))
    print(matcher.match_conference("Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern …, 2022"))
