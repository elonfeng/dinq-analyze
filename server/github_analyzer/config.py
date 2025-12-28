import os
from typing import Any
from dotenv import load_dotenv

load_dotenv()

def load_config() -> dict[str, Any]:
    """
    从环境变量加载配置，适配DINQ项目的配置体系
    """
    # 尝试从DINQ项目的API配置中获取密钥
    try:
        from server.config.api_keys import API_KEYS
        github_token = API_KEYS.get('GITHUB_TOKEN', '')
        openrouter_api_key = API_KEYS.get('OPENROUTER_API_KEY', '')
        crawlbase_token = API_KEYS.get('CRAWLBASE_API_TOKEN', '')
    except ImportError:
        # 如果无法导入API_KEYS，则从环境变量获取
        github_token = ''
        openrouter_api_key = ''
        crawlbase_token = ''

    # 从环境变量获取配置（优先级更高）
    config = {
        "github": {
            "token": os.getenv("GITHUB_TOKEN", github_token)
        },
        "openrouter": {
            "api_key": os.getenv("OPENROUTER_API_KEY", openrouter_api_key),
            "model": _default_github_model()
        },
        "crawlbase": {
            "token": os.getenv("CRAWLBASE_API_TOKEN", os.getenv("CRAWLBASE_TOKEN", crawlbase_token))
        }
    }

    # 验证必需的配置
    missing_configs = []

    if not config["github"]["token"]:
        missing_configs.append("GITHUB_TOKEN")

    if not config["openrouter"]["api_key"]:
        missing_configs.append("OPENROUTER_API_KEY")

    if not config["crawlbase"]["token"]:
        missing_configs.append("CRAWLBASE_API_TOKEN")

    if missing_configs:
        raise ValueError(
            f"Missing required environment variables or API keys: {', '.join(missing_configs)}. "
            f"Please set them in environment variables or add them to server/config/api_keys.py"
        )

    return config


def _default_github_model() -> str:
    # Speed-first by default; override via DINQ_LLM_TASK_MODEL_GITHUB_AI / DINQ_LLM_MODEL_FAST.
    try:
        from server.config.llm_models import get_model

        return get_model("fast", task="github_ai")
    except Exception:
        return os.getenv("OPENROUTER_MODEL", "x-ai/grok-code-fast-1")
