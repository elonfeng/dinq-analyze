# coding: UTF-8
"""
Configuration for Scholar API service.
Contains lists of top-tier conferences and journals.
"""

import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Define top-tier AI conferences (CCF-A)
TOP_TIER_CONFERENCES = [
    # Top
    'Nature', 'Science',
    # AI & ML
    'NeurIPS', 'ICML', 'ICLR', 'AAAI', 'IJCAI', 'COLT', 'AAMAS',
    # Computer Vision & Graphics
    'CVPR', 'ECCV', 'ICCV', 'SIGGRAPH', 'SIGGRAPH Asia', 'ACM MM', '3DV',
    # NLP
    'ACL', 'EMNLP', 'NAACL', 'COLM', 'ICASSP',
    # Web & IR
    'WWW', 'SIGIR', 'CIKM', 'WSDM',
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
    # Medical & Bioinformatics
    'MICCAI', 'MIDL', 'ISBI', 'AMIA', 'RECOMB', 'ISMB',
    # Robotics
    'ICRA', 'IROS',
    # Cyrpto
    "CRYPTO",
    # Patent
    'US Patent'
]

# Define top-tier journals (CCF-A)
TOP_TIER_JOURNALS = [
    # AI & ML
    'TPAMI', 'IJCV', 'JMLR', 'TNN', 'TNNLS', 'AIJ', 'AI',
    # NLP & IR
    'TACL', 'CL', 'TOIS',
    # Graphics & Multimedia
    'TOG', 'TIP', 'TMM',
    # Databases
    'TODS', 'TKDE', 'VLDBJ',
    # Networks & Security
    'TON', 'JSAC', 'TDSC', 'TIFS',
    # Software Engineering
    'TSE', 'TOSEM',
    # Architecture
    'TC', 'TOCS', 'TACO',
    # HCI
    'TOCHI', 'IJHCS',
    
    # 医学领域
    'NEJM', 'Lancet', 'JAMA', 'Nature Medicine', 'Cell',
    'Science Translational Medicine', 'BMJ', 'Nature Genetics',
    'Nature Biotechnology', 'Nature Immunology', 'PNAS',
    'Circulation', 'Journal of Clinical Investigation', 'Immunity',
    'Cancer Cell', 'Neuron',
    'Bioinformatics', 'Nature Methods', 'Genome Research',
    'Nucleic Acids Research', 'Lancet Global Health', 'Lancet Public Health',
    
    # 生命科学领域 -----------------------------
    'bioRxiv','Nature Methods', 'Nature Communications',
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

# Create a combined list of top venues
TOP_TIER_VENUES = TOP_TIER_CONFERENCES + TOP_TIER_JOURNALS
