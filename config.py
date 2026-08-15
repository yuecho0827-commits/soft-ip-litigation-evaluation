"""
配置文件 - Soft IP 主诉评估系统
支持 Mock 模式和真实 LLM API 切换
"""
import os
import shutil
import sqlite3
from pathlib import Path
BASE_DIR = Path(__file__).parent
INSTALL_ENV_PATH = BASE_DIR / '.env'
LEGACY_DATA_DIR = BASE_DIR / 'data'
LEGACY_RUNTIME_DIR = BASE_DIR / 'runtime'
APP_STORAGE_DIRNAME = 'SoftIpLitigationEvaluation'
FALLBACK_USER_DATA_DIR = BASE_DIR / '.user_data'
APP_TITLE = 'Soft IP 主诉评估系统'
APP_VERSION = '0.1.0 MVP'
TRADEMARK_CAUSE_TYPE = '商标侵权'
SUPPORTED_CAUSE_TYPES = [TRADEMARK_CAUSE_TYPE]
GOAL_TYPES = ['要钱', '要名']
SCORING_WEIGHTS = {'legal_feasibility': 0.45, 'business_expectation': 0.25, 'evidence_readiness': 0.3}
CONFIDENCE_WEIGHTS = {'evidence_completeness': 0.4, 'retrieval_quality': 0.3, 'data_freshness': 0.3}
ADVERSARIAL_COEFF_MIN = 0.75
ADVERSARIAL_COEFF_MAX = 1.15
MOCK_DELAY = 1
_RUNTIME_SETTING_ORDER = ['USE_MOCK', 'LLM_PROVIDER', 'DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL', 'QCC_API_TOKEN', 'PKULAW_API_TOKEN']
_DEFAULT_RUNTIME_SETTINGS = {'USE_MOCK': 'False', 'LLM_PROVIDER': 'deepseek', 'DEEPSEEK_API_KEY': '', 'DEEPSEEK_BASE_URL': 'https://api.deepseek.com', 'QCC_API_TOKEN': '', 'PKULAW_API_TOKEN': ''}

def _default_user_data_dir() -> Path:
    local_appdata = os.getenv('LOCALAPPDATA')
    if local_appdata:
        return Path(local_appdata) / APP_STORAGE_DIRNAME
    xdg_data_home = os.getenv('XDG_DATA_HOME')
    if xdg_data_home:
        return Path(xdg_data_home) / APP_STORAGE_DIRNAME
    return Path.home() / '.local' / 'share' / APP_STORAGE_DIRNAME

def _ensure_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / '.write_test'
        probe.write_text('ok', encoding='utf-8')
        probe.unlink()
        return True
    except (OSError, PermissionError):
        return False

def _select_user_data_dir() -> Path:
    for candidate in (PREFERRED_USER_DATA_DIR, FALLBACK_USER_DATA_DIR):
        if _ensure_writable_dir(candidate):
            return candidate
    raise PermissionError('未找到可写的数据目录')
PREFERRED_USER_DATA_DIR = _default_user_data_dir()
USER_DATA_DIR = _select_user_data_dir()
ENV_PATH = USER_DATA_DIR / '.env'
RUNTIME_DIR = USER_DATA_DIR / 'runtime'
REPORT_DIR = RUNTIME_DIR / 'reports'
DB_PATH = RUNTIME_DIR / 'soft_ip.db'
LEGACY_DB_CANDIDATES = [LEGACY_RUNTIME_DIR / 'soft_ip.db', LEGACY_DATA_DIR / 'soft_ip.db', BASE_DIR / 'soft_ip_runtime.db']
LEGACY_REPORT_DIRS = [LEGACY_RUNTIME_DIR / 'reports', LEGACY_DATA_DIR / 'reports']

def _copy_tree_contents(source_dir: Path, target_dir: Path) -> None:
    if not source_dir.exists():
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    for item in source_dir.iterdir():
        target = target_dir / item.name
        if target.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

def _bootstrap_user_storage() -> None:
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not ENV_PATH.exists() and INSTALL_ENV_PATH.exists():
        shutil.copy2(INSTALL_ENV_PATH, ENV_PATH)
    _copy_tree_contents(LEGACY_RUNTIME_DIR, RUNTIME_DIR)
    if not DB_PATH.exists():
        for legacy_db in LEGACY_DB_CANDIDATES:
            if legacy_db.exists():
                shutil.copy2(legacy_db, DB_PATH)
                break
    for legacy_report_dir in LEGACY_REPORT_DIRS:
        _copy_tree_contents(legacy_report_dir, REPORT_DIR)

def _read_env_file(env_path: Path=ENV_PATH) -> dict:
    values = {}
    if env_path.exists():
        for raw_line in env_path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if line and (not line.startswith('#')) and ('=' in line):
                key, _, val = line.partition('=')
                values[key.strip()] = val.strip().strip('"').strip("'")
    return values

def _apply_env_values(values: dict) -> None:
    for key, value in values.items():
        os.environ[key] = value

def get_runtime_settings() -> dict:
    file_values = _read_env_file()
    merged = dict(_DEFAULT_RUNTIME_SETTINGS)
    for key in _RUNTIME_SETTING_ORDER:
        env_value = os.getenv(key)
        if env_value:
            merged[key] = env_value
    for key, value in file_values.items():
        if key in _RUNTIME_SETTING_ORDER:
            merged[key] = value
    use_mock = str(merged.get('USE_MOCK', 'False')).lower() == 'true'
    llm_provider = (merged.get('LLM_PROVIDER') or 'deepseek').strip() or 'deepseek'
    deepseek_api_key = (merged.get('DEEPSEEK_API_KEY') or '').strip()
    deepseek_base_url = (merged.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com').strip() or 'https://api.deepseek.com'
    qcc_api_token = (merged.get('QCC_API_TOKEN') or '').strip()
    pkulaw_api_token = (merged.get('PKULAW_API_TOKEN') or '').strip()
    return {'use_mock': use_mock, 'llm_provider': llm_provider, 'deepseek_api_key': deepseek_api_key, 'deepseek_base_url': deepseek_base_url, 'qcc_api_token': qcc_api_token, 'pkulaw_api_token': pkulaw_api_token, 'env_path': str(ENV_PATH), 'api_key_configured': bool(deepseek_api_key), 'qcc_api_token_configured': bool(qcc_api_token), 'pkulaw_api_token_configured': bool(pkulaw_api_token)}
_config_initialized = False

def _init_config_once() -> None:
    """幂等初始化：首次 import 时自动执行，后续调用跳过。测试中可通过 reload_config() 强制刷新。"""
    global _config_initialized, RUNTIME_DIR, DB_PATH, SQLITE_URL
    if _config_initialized:
        return
    _config_initialized = True
    _bootstrap_user_storage()
    _apply_env_values(_read_env_file())
    global _RUNTIME_SETTINGS, USE_MOCK, LLM_PROVIDER
    global DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, QCC_API_TOKEN, PKULAW_API_TOKEN
    _RUNTIME_SETTINGS = get_runtime_settings()
    USE_MOCK = _RUNTIME_SETTINGS['use_mock']
    LLM_PROVIDER = _RUNTIME_SETTINGS['llm_provider']
    DEEPSEEK_API_KEY = _RUNTIME_SETTINGS['deepseek_api_key']
    DEEPSEEK_BASE_URL = _RUNTIME_SETTINGS['deepseek_base_url']
    QCC_API_TOKEN = _RUNTIME_SETTINGS['qcc_api_token']
    PKULAW_API_TOKEN = _RUNTIME_SETTINGS['pkulaw_api_token']
    try:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH):
            pass
        SQLITE_URL = f'sqlite:///{DB_PATH}'
    except (OSError, PermissionError, sqlite3.Error):
        SQLITE_URL = 'sqlite:///:memory:'

def reload_config() -> None:
    """强制重新初始化配置（用于测试或 save_runtime_settings 后手动刷新模块级常量）"""
    global _config_initialized
    _config_initialized = False
    _init_config_once()
_init_config_once()

def save_runtime_settings(*, use_mock: bool, llm_provider: str, deepseek_api_key: str, deepseek_base_url: str, qcc_api_token: str, pkulaw_api_token: str) -> dict:
    values = _read_env_file()
    values.update({'USE_MOCK': 'True' if use_mock else 'False', 'LLM_PROVIDER': (llm_provider or 'deepseek').strip() or 'deepseek', 'DEEPSEEK_API_KEY': (deepseek_api_key or '').strip(), 'DEEPSEEK_BASE_URL': (deepseek_base_url or 'https://api.deepseek.com').strip() or 'https://api.deepseek.com', 'QCC_API_TOKEN': (qcc_api_token or '').strip(), 'PKULAW_API_TOKEN': (pkulaw_api_token or '').strip()})
    ordered_lines = ['# Soft IP 主诉评估系统 环境配置', '# 由系统配置页自动维护', '']
    for key in _RUNTIME_SETTING_ORDER:
        ordered_lines.append(f"{key}={values.get(key, '')}")
    extra_keys = [key for key in values.keys() if key not in _RUNTIME_SETTING_ORDER]
    if extra_keys:
        ordered_lines.append('')
        ordered_lines.append('# 其他保留配置')
        for key in sorted(extra_keys):
            ordered_lines.append(f'{key}={values[key]}')
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    ENV_PATH.write_text('\n'.join(ordered_lines) + '\n', encoding='utf-8')
    _apply_env_values(values)
    reload_config()
    return get_runtime_settings()

def get_runtime_configuration_status():
    """返回当前运行模式及必要配置检查结果。"""
    settings = get_runtime_settings()
    missing_required = []
    optional_warnings = []
    missing_optional_services = []
    if not settings['use_mock'] and (not settings['deepseek_api_key'].strip()):
        missing_required.append('DEEPSEEK_API_KEY')
    if not settings['deepseek_base_url'].strip():
        optional_warnings.append('DEEPSEEK_BASE_URL 未设置，已回退到默认地址')
    if not settings['use_mock'] and (not settings['qcc_api_token'].strip()):
        missing_optional_services.append('QCC_API_TOKEN')
        optional_warnings.append('企查查 Token 未配置，财务画像会自动跳过。')
    if not settings['use_mock'] and (not settings['pkulaw_api_token'].strip()):
        missing_optional_services.append('PKULAW_API_TOKEN')
        optional_warnings.append('北大法宝 Token 未配置，法条检索、类案检索和引用验证会自动跳过。')
    storage_notice = ''
    if USER_DATA_DIR == FALLBACK_USER_DATA_DIR:
        storage_notice = '当前环境无法写入默认用户目录，系统已自动回退到安装目录下的 .user_data。数据库、缓存、报告都会写入当前实际生效目录。'
    return {'use_mock': settings['use_mock'], 'mode_label': 'Mock 模拟模式' if settings['use_mock'] else '真实 Demo 模式', 'ready': settings['use_mock'] or not missing_required, 'missing_required': missing_required, 'missing_optional_services': missing_optional_services, 'optional_warnings': optional_warnings, 'configured_items': {'USE_MOCK': str(settings['use_mock']), 'LLM_PROVIDER': settings['llm_provider'], 'DEEPSEEK_BASE_URL': settings['deepseek_base_url'] or '(default)', 'DEEPSEEK_API_KEY': '已配置' if settings['deepseek_api_key'].strip() else '未配置', 'QCC_API_TOKEN': '已配置' if settings['qcc_api_token'].strip() else '未配置', 'PKULAW_API_TOKEN': '已配置' if settings['pkulaw_api_token'].strip() else '未配置', 'DB_PATH': str(DB_PATH), 'RUNTIME_DIR': str(RUNTIME_DIR), 'ENV_PATH': str(ENV_PATH), 'USER_DATA_DIR': str(USER_DATA_DIR), 'INSTALL_DIR': str(BASE_DIR)}, 'db_path': str(DB_PATH), 'runtime_dir': str(RUNTIME_DIR), 'env_path': str(ENV_PATH), 'user_data_dir': str(USER_DATA_DIR), 'preferred_user_data_dir': str(PREFERRED_USER_DATA_DIR), 'install_dir': str(BASE_DIR), 'report_dir': str(REPORT_DIR), 'using_fallback_storage': USER_DATA_DIR == FALLBACK_USER_DATA_DIR, 'storage_notice': storage_notice, 'llm_provider': settings['llm_provider'], 'deepseek_base_url': settings['deepseek_base_url'], 'api_key_configured': settings['api_key_configured'], 'qcc_api_token_configured': settings['qcc_api_token_configured'], 'pkulaw_api_token_configured': settings['pkulaw_api_token_configured']}