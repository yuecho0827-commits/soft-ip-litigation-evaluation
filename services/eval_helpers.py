"""
评估辅助函数 — 数据处理和状态构建的纯逻辑函数。

所有函数均为纯函数（无副作用、无 Streamlit 依赖），
依赖项（如维度标签、检索标签）通过参数注入。
"""

def build_dimension_result(result: dict, fallback: dict, label: str) -> dict:
    """合并评估结果和回退值，标记完成状态"""
    merged = dict(fallback)
    merged.update(result or {})
    error = merged.get('error')
    if error:
        merged['status'] = 'failed'
        merged['is_complete'] = False
        merged['analysis'] = f'{label}未完成：{error}'
    else:
        merged['status'] = merged.get('status', 'completed')
        merged['is_complete'] = merged.get('status') != 'failed'
    return merged

def build_external_failure(label: str, error: str, status: str='failed', include_collections: bool=True) -> dict:
    """构建外部服务调用失败的标准响应"""
    payload = {'label': label, 'status': status, 'error': error, '_summary': error}
    if include_collections:
        payload.setdefault('laws', [])
        payload.setdefault('cases', [])
    return payload

def label_dimension_names(names: list[str], dimension_labels: dict[str, str]) -> list[str]:
    """将维度代码名映射为中文标签"""
    return [dimension_labels.get(name, name) for name in names]

def build_integrity_payload(integrity: dict, dimension_labels: dict[str, str]) -> dict:
    """从数据完整性检查结果构建展示用 payload"""
    critical_issues = label_dimension_names(integrity.get('critical_missing', []), dimension_labels) + label_dimension_names(integrity.get('critical_failed', []), dimension_labels)
    optional_issues = label_dimension_names(integrity.get('optional_incomplete', []), dimension_labels)
    return {'is_complete': integrity.get('is_complete', False), 'label': '完整' if integrity.get('is_complete') else '部分完成', 'critical_issues': critical_issues, 'optional_issues': optional_issues}