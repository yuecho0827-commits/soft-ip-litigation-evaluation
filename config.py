"""
配置文件 - Soft IP 主诉评估系统
支持 Mock 模式和真实 LLM API 切换
"""

import os
from pathlib import Path

# 手动读取 .env 文件（避免 python-dotenv 依赖）
def _load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                val = val.strip().strip('"').strip("'")
                os.environ[key.strip()] = val

_load_env()

# 项目根目录
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "soft_ip.db"

# LLM 配置
USE_MOCK = os.getenv("USE_MOCK", "True").lower() == "true"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# 数据库配置
SQLITE_URL = f"sqlite:///{DB_PATH}"

# 应用配置
APP_TITLE = "Soft IP 主诉评估系统"
APP_VERSION = "0.1.0 MVP"

# 商标侵权评估配置
TRADEMARK_CAUSE_TYPE = "商标侵权"
SUPPORTED_CAUSE_TYPES = [TRADEMARK_CAUSE_TYPE]

# 业务目标类型
GOAL_TYPES = ["要钱", "要名"]

# 评分权重（三维评分）
SCORING_WEIGHTS = {
    "legal_feasibility": 0.45,
    "business_expectation": 0.25,
    "evidence_readiness": 0.30
}

# 置信度权重
CONFIDENCE_WEIGHTS = {
    "evidence_completeness": 0.4,
    "retrieval_quality": 0.3,
    "data_freshness": 0.3
}

# 对抗修正系数范围
ADVERSARIAL_COEFF_MIN = 0.75
ADVERSARIAL_COEFF_MAX = 1.15

# Mock 模式延迟（秒）
MOCK_DELAY = 1
