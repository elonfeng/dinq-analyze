"""
Profile Utilities

This module provides shared utilities for profile management, including avatar and description generation.
"""

import os
import random
import logging

# 获取模块日志记录器
logger = logging.getLogger('server.utils.profile_utils')

# Get base URL from environment variables
BASE_URL = os.environ.get('DINQ_API_DOMAIN', 'http://localhost:5001')

# List of avatar files
AVATAR_DIR = 'images/icon/avatar'
AVATAR_FILES = [f"{i}.png" for i in range(21)]  # 0.png to 20.png

# Advisor icon path
ADVISOR_ICON_PATH = 'images/icon/advisor.png'

# List of researcher descriptions
RESEARCHER_DESCRIPTIONS = [
    "{name}, mindful architect of algorithms, sculpting intelligence from silent data flows. Finding clarity in complexity.",
    "{name}, quietly exploring digital consciousness. Weaving logic and intuition into learning systems. Present in the code.",
    "{name}, cultivating digital gardens where insights bloom. A calm coder harmonizing data streams and neural pathways.",
    "{name}, bridging human thought and machine potential. Finding stillness in the flow of computation and discovery.",
    "{name}, shaping future intelligence with present awareness. Balancing intricate code with quiet contemplation and deep focus.",
    "{name}, deep listener to data's subtle whispers. Guiding emergent insight with patient, focused observation.",
    "{name}, quietly orchestrating data flows. Finding resonance and harmony within the machine's learning rhythm.",
    "{name}, translating human intention into serene code. Weaving balanced logic, bridging thought and computation.",
    "{name}, calm observer of the algorithm's subtle dance. Nurturing emergent potential with mindful space and attention.",
    "{name}, seeking elegant simplicity within complex systems. Transforming data into insight through focused, mindful presence."
]

# Define the list of known/preferred conference acronyms
PREFERRED_CONFERENCE_ACRONYMS = {
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
    # Medical
    'MICCAI',
    # Robotics
    'ICRA', 'IROS',
    # Cyrpto
    "CRYPTO",
    # Patent
    'US Patent'
}

def update_base_url(new_base_url):
    """
    更新 BASE_URL 全局变量
    
    Args:
        new_base_url (str): 新的基础 URL
    """
    global BASE_URL
    logger.info(f"Updating BASE_URL from {BASE_URL} to {new_base_url}")
    BASE_URL = new_base_url

def get_random_avatar():
    """
    Get a random avatar URL from the avatar directory.

    Returns:
        str: URL to a random avatar image
    """
    avatar_file = random.choice(AVATAR_FILES)
    return f"{BASE_URL}/{AVATAR_DIR}/{avatar_file}"

def get_random_description(name):
    """
    Get a random researcher description with the name filled in.

    Args:
        name (str): Researcher name to insert into the description

    Returns:
        str: A random description with the name inserted
    """
    description_template = random.choice(RESEARCHER_DESCRIPTIONS)
    return description_template.format(name=name)

def get_advisor_avatar():
    """
    Get the advisor avatar URL.

    Returns:
        str: URL to the advisor avatar image
    """
    return f"{BASE_URL}/{ADVISOR_ICON_PATH}"
