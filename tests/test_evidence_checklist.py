"""
evidence_checklist.py 的单元测试。

验证商标权取证清单的数据结构完整性与 prompt 渲染。
"""
import pytest

from evidence_checklist import (
    TRADEMARK_EVIDENCE_CHECKLIST,
    COPYRIGHT_EVIDENCE_CHECKLIST,
    UNFAIR_COMPETITION_EVIDENCE_CHECKLIST,
    CATEGORIES,
    render_checklist_prompt,
)


def test_checklist_has_11_items():
    """商标权取证清单应为 11 项（5 类构成要件）"""
    assert len(TRADEMARK_EVIDENCE_CHECKLIST) == 11


def test_every_item_has_required_fields():
    """每项都必须包含完整字段"""
    required = ['category', 'element', 'standard_evidence', 'legal_basis',
                'impact_if_missing', 'check_points']
    for item in TRADEMARK_EVIDENCE_CHECKLIST:
        for field in required:
            assert field in item, '缺少字段: {} in {}'.format(field, item.get('element'))
            assert item[field], '字段为空: {} in {}'.format(field, item.get('element'))


def test_impact_if_missing_values_are_valid():
    """缺失影响只能是 block / warning / optional"""
    valid = {'block', 'warning', 'optional'}
    for item in TRADEMARK_EVIDENCE_CHECKLIST:
        assert item['impact_if_missing'] in valid, '非法缺失影响值: {}'.format(item['impact_if_missing'])


def test_legal_basis_items_are_complete():
    """每条法律依据都应有 law / article / url"""
    for item in TRADEMARK_EVIDENCE_CHECKLIST:
        for basis in item['legal_basis']:
            assert basis.get('law'), '法律依据缺 law'
            assert basis.get('article'), '法律依据缺 article'
            assert basis.get('url'), '法律依据缺 url'
            assert 'pkulaw.com' in basis['url'], '法律依据链接非北大法宝: {}'.format(basis['url'])


def test_all_five_categories_covered():
    """五个证据类别都应有覆盖"""
    categories = set(item['category'] for item in TRADEMARK_EVIDENCE_CHECKLIST)
    assert categories == set(CATEGORIES)


def test_block_items_are_only_rights_and_use():
    """block 级（硬缺失）只应出现在商标权有效、商标性使用两项"""
    block_items = [item['element'] for item in TRADEMARK_EVIDENCE_CHECKLIST
                   if item['impact_if_missing'] == 'block']
    assert block_items == ['商标权有效', '被告构成商标性使用']


def test_render_checklist_prompt_contains_all_items():
    """渲染出的 prompt 应包含全部 11 项要素名"""
    prompt = render_checklist_prompt()
    for item in TRADEMARK_EVIDENCE_CHECKLIST:
        assert item['element'] in prompt


def test_render_checklist_prompt_contains_legal_basis():
    """渲染出的 prompt 应包含法律依据"""
    prompt = render_checklist_prompt()
    assert '法律依据' in prompt
    assert '商标法' in prompt


# ---------- 著作权清单 ----------

def test_copyright_checklist_has_10_items():
    """著作权取证清单应为 10 项"""
    assert len(COPYRIGHT_EVIDENCE_CHECKLIST) == 10


def test_copyright_every_item_has_required_fields():
    """著作权清单每项字段齐全"""
    required = ['category', 'element', 'standard_evidence', 'legal_basis',
                'impact_if_missing', 'check_points']
    for item in COPYRIGHT_EVIDENCE_CHECKLIST:
        for field in required:
            assert field in item, '缺少字段: {} in {}'.format(field, item.get('element'))
            assert item[field], '字段为空: {} in {}'.format(field, item.get('element'))


def test_copyright_impact_if_missing_valid():
    """缺失影响只能是 block / warning / optional"""
    valid = {'block', 'warning', 'optional'}
    for item in COPYRIGHT_EVIDENCE_CHECKLIST:
        assert item['impact_if_missing'] in valid


def test_copyright_legal_basis_complete():
    """每条法律依据都应有 law / article / url，且链接为北大法宝"""
    for item in COPYRIGHT_EVIDENCE_CHECKLIST:
        for basis in item['legal_basis']:
            assert basis.get('law')
            assert basis.get('article')
            assert basis.get('url')
            assert 'pkulaw.com' in basis['url']


def test_copyright_categories_covered():
    """五个证据类别都应有覆盖"""
    categories = set(item['category'] for item in COPYRIGHT_EVIDENCE_CHECKLIST)
    assert categories == set(CATEGORIES)


def test_copyright_block_items():
    """block 级只应出现在著作权权属、实质性相似两项"""
    block_items = [item['element'] for item in COPYRIGHT_EVIDENCE_CHECKLIST
                   if item['impact_if_missing'] == 'block']
    assert block_items == ['著作权权属', '实质性相似']


def test_copyright_render_contains_items():
    """渲染著作权清单应包含全部要素名与著作权法依据"""
    prompt = render_checklist_prompt(COPYRIGHT_EVIDENCE_CHECKLIST)
    for item in COPYRIGHT_EVIDENCE_CHECKLIST:
        assert item['element'] in prompt
    assert '著作权法' in prompt


# ---------- 不正当竞争清单 ----------

def test_unfair_competition_has_9_items():
    """不正当竞争取证清单应为 9 项"""
    assert len(UNFAIR_COMPETITION_EVIDENCE_CHECKLIST) == 9


def test_unfair_competition_fields_complete():
    """不正当竞争清单每项字段齐全"""
    required = ['category', 'element', 'standard_evidence', 'legal_basis',
                'impact_if_missing', 'check_points']
    for item in UNFAIR_COMPETITION_EVIDENCE_CHECKLIST:
        for field in required:
            assert field in item, '缺少字段: {} in {}'.format(field, item.get('element'))
            assert item[field], '字段为空: {} in {}'.format(field, item.get('element'))


def test_unfair_competition_impact_valid():
    """缺失影响只能是 block / warning / optional"""
    valid = {'block', 'warning', 'optional'}
    for item in UNFAIR_COMPETITION_EVIDENCE_CHECKLIST:
        assert item['impact_if_missing'] in valid


def test_unfair_competition_legal_basis_complete():
    """每条法律依据都应有 law / article / url，且链接为北大法宝"""
    for item in UNFAIR_COMPETITION_EVIDENCE_CHECKLIST:
        for basis in item['legal_basis']:
            assert basis.get('law')
            assert basis.get('article')
            assert basis.get('url')
            assert 'pkulaw.com' in basis['url']


def test_unfair_competition_categories():
    """不正当竞争清单覆盖 4 类（无抗辩应对类）"""
    expected = {'权利基础证据', '侵权认定证据', '损害赔偿证据', '取证技术规范'}
    categories = set(item['category'] for item in UNFAIR_COMPETITION_EVIDENCE_CHECKLIST)
    assert categories == expected


def test_unfair_competition_block_items():
    """block 级应为 4 项（商业标识、商业秘密构成、混淆、商业秘密侵权）"""
    block_items = [item['element'] for item in UNFAIR_COMPETITION_EVIDENCE_CHECKLIST
                   if item['impact_if_missing'] == 'block']
    assert len(block_items) == 4
    assert '有一定影响的商业标识' in block_items
    assert '混淆行为（擅自使用相同或近似标识）' in block_items


def test_unfair_competition_render_contains_items():
    """渲染不正当竞争清单应包含全部要素名与反不正当竞争法依据"""
    prompt = render_checklist_prompt(UNFAIR_COMPETITION_EVIDENCE_CHECKLIST)
    for item in UNFAIR_COMPETITION_EVIDENCE_CHECKLIST:
        assert item['element'] in prompt
    assert '反不正当竞争法' in prompt
