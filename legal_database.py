"""
法律数据库检索模块 - 北大法宝 MCP 集成
提供法规检索、案例检索、法条内容获取的接口。
MCP 调用由 AI Agent 完成，本模块负责数据存取和格式化。
"""
import json
from datetime import datetime
from typing import Dict, List, Optional
from database import SessionLocal, Case

def generate_search_queries(case_description: str) -> List[Dict]:
    """从案情中提取法律检索关键词"""
    queries = []
    tm_keywords = ['商标', '商标法', '注册商标', '商标侵权']
    case_lower = case_description.lower()
    if any((k in case_description for k in ['商标', '注册商标'])):
        queries.append({'type': 'law_keyword', 'title': '中华人民共和国商标法', 'description': '商标法核心法条'})
        queries.append({'type': 'case_search', 'text': f'商标侵权 近似商标 混淆', 'case_type': '民事案件', 'description': '商标侵权类案检索'})
        queries.append({'type': 'law_search', 'text': '商标侵权 损害赔偿 法定赔偿', 'description': '商标侵权赔偿标准'})
    if '驰名商标' in case_description or '驰名' in case_description:
        queries.append({'type': 'law_keyword', 'title': '驰名商标认定和保护规定', 'description': '驰名商标相关法规'})
        queries.append({'type': 'case_search', 'text': f'驰名商标 跨类保护', 'case_type': '民事案件', 'description': '驰名商标保护类案'})
    if any((k in case_description for k in ['不正当竞争', '反不正当竞争', '混淆'])):
        queries.append({'type': 'law_keyword', 'title': '中华人民共和国反不正当竞争法', 'description': '反不正当竞争法'})
    if any((k in case_description for k in ['赔偿', '损失', '获利', '销售额', '损害'])):
        queries.append({'type': 'case_search', 'text': f'商标侵权 赔偿额 法定赔偿', 'case_type': '民事案件', 'description': '商标侵权赔偿额参考案例'})
    if any((k in case_description for k in ['公证', '证据', '固定证据'])):
        queries.append({'type': 'case_search', 'text': f'商标侵权 电子证据 公证取证', 'case_type': '民事案件', 'description': '证据采信标准参考案例'})
    return queries

def format_laws_for_report(laws: List[Dict]) -> str:
    """格式化法规检索结果为报告文本"""
    if not laws:
        return '暂无相关法规检索结果。'
    parts = ['### 相关法律法规\n']
    for law in laws[:10]:
        title = law.get('title', law.get('name', '未知法规'))
        content = law.get('content', law.get('text', ''))
        source = law.get('source', '')
        if content:
            parts.append(f'**{title}**\n{content}\n')
            if source:
                parts.append(f'*来源: {source}*\n')
    return '\n'.join(parts)

def format_cases_for_report(cases: List[Dict]) -> str:
    """格式化案例检索结果为报告文本"""
    if not cases:
        return '暂无相关案例检索结果。'
    parts = ['### 类案参考\n']
    for i, case in enumerate(cases[:5], 1):
        title = case.get('title', case.get('name', '未知案例'))
        court = case.get('court', case.get('courthouse_name', ''))
        date = case.get('date', case.get('decision_date', ''))
        summary = case.get('summary', case.get('abstract', ''))
        result = case.get('result', case.get('judgment_result', ''))
        parts.append(f'**{i}. {title}**')
        if court:
            parts.append(f'- 审理法院: {court}')
        if date:
            parts.append(f'- 审结日期: {date}')
        if summary:
            parts.append(f'- 案件摘要: {summary[:200]}')
        if result:
            parts.append(f'- 裁判结果: {result[:200]}')
        parts.append('')
    return '\n'.join(parts)