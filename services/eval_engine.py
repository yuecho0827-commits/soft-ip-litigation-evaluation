"""
评估引擎工厂 — 统一 Mock/Real 模式切换。

使用方式:
    from services.eval_engine import create_engine

    engine = create_engine(use_mock=True)
    result = engine["evaluate_rights_foundation"](case_description, ...)
"""
import mock_llm
import llm_client
from moot_court import run_moot_court as run_moot_court_real
EVAL_FUNCTION_NAMES = ['evaluate_rights_foundation', 'evaluate_infringement', 'evaluate_procedure', 'evaluate_financial_return', 'evaluate_precedent_value', 'evaluate_evidence_readiness', 'extract_defendant_info']

def create_engine(use_mock: bool) -> dict:
    """
    根据模式创建评估引擎，返回包含所有评估函数的字典。

    评估分析页面直接使用 engine["evaluate_rights_foundation"](...) 调用，
    不再需要关心底层是 mock_llm 还是 llm_client。
    """
    module = mock_llm if use_mock else llm_client
    engine = {}
    for name in EVAL_FUNCTION_NAMES:
        engine[name] = getattr(module, name)
    if use_mock:
        engine['run_moot_court_simulation'] = mock_llm.run_moot_court_simulation
    else:
        engine['run_moot_court_simulation'] = run_moot_court_real
    return engine