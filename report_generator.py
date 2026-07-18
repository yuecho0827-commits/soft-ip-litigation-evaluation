"""
报告生成器 - 评估报告输出
支持 Markdown 和 PDF 格式
"""

from typing import Dict, Any, List
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

def generate_markdown_report(case_info: Dict, score_result: Dict, rule_results: List, legal_analysis: Dict) -> str:
    """
    生成 Markdown 格式评估报告
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 标题
    md = f"""# Soft IP 主诉评估报告

**案件名称**: {case_info.get('name', '未命名案件')}
**评估时间**: {now}
**案由**: {case_info.get('cause_type', '商标侵权')}
**业务目标**: {case_info.get('goal_type', '未指定')}
**客户**: {case_info.get('client_org', '未指定')}

---

## 一、结论摘要

**总体建议**: {score_result.get('recommendation', '待评估')}
**综合评分**: {score_result.get('final_score', 'N/A')} 分（满分100分）
**置信度**: {score_result.get('confidence_score', 'N/A')}%

{score_result.get('reason', '')}

"""

    # 行动建议
    action_items = score_result.get('action_items', [])
    if action_items:
        md += "\n### 建议行动\n"
        for i, item in enumerate(action_items, 1):
            md += f"{i}. {item}\n"

    md += "\n---\n\n"

    # 三维评分
    md += """## 二、三维评分总览

| 维度 | 得分 | 权重 | 说明 |
|------|------|------|------|
"""
    md += f"| 法律可行性 | {score_result.get('legal_feasibility', 'N/A')} | 45% | 权利基础、侵权认定、程序合规 |\n"
    md += f"| 业务预期 | {score_result.get('business_expectation', 'N/A')} | 25% | 赔偿预期、成本控制 |\n"
    md += f"| 证据就绪度 | {score_result.get('evidence_readiness', 'N/A')} | 30% | 证据完整性、证明力 |\n"
    md += f"\n**最终得分**: {score_result.get('final_score', 'N/A')}\n\n"
    md += "---\n\n"

    # 红线风险
    md += """## 三、红线风险检查

"""
    for rule in rule_results:
        severity = rule.get("severity", rule.get("status", "pass"))
        rule_name = rule.get("rule_name", rule.get("name", "未知规则"))
        result = rule.get("result", rule.get("detail", rule.get("status", "通过")))
        reason = rule.get("reason", rule.get("detail", ""))
        status_icon = "✅" if severity == "pass" else ("⚠️" if severity == "warning" else "🚫")
        md += f"### {status_icon} {rule_name}\n\n"
        md += f"**结果**: {result}\n\n"
        md += f"**说明**: {reason}\n\n"

    md += "---\n\n"

    # 法律要件分析
    md += """## 四、法律要件分析

"""
    elements = legal_analysis.get("elements", [])
    for element in elements:
        md += f"### {element.get('element', '未知要件')}\n\n"
        md += f"**评分**: {element.get('score', 'N/A')} 分\n\n"
        md += f"**分析**: {element.get('analysis', '')}\n\n"
        md += f"**证据状态**: {element.get('evidence_status', '未评估')}\n\n"

        risks = element.get("risks", [])
        if risks:
            md += "**风险提示**:\n"
            for risk in risks:
                md += f"- {risk}\n"
            md += "\n"

    md += "---\n\n"

    # 证据矩阵（简化）
    md += """## 五、证据缺口诊断

（详细证据矩阵请在系统中查看）

**关键缺失证据**:
"""
    for rule in rule_results:
        if rule.get("severity") in ["warning", "block"] and "缺失" in rule.get("rule_name", ""):
            md += f"- {rule.get('reason', '')}\n"

    md += "\n---\n\n"

    # 附录
    md += f"""## 六、附录

**评估模型版本**: v0.1.0 MVP
**评估方法**: 规则引擎 + LLM 辅助分析
**免责声明**: 本报告为 AI 辅助生成，仅供内部决策参考，不构成正式法律意见。

---
*报告生成时间: {now}*
"""

    return md

def generate_pdf_bytes(markdown_content: str) -> bytes:
    """
    将 Markdown 报告转为 PDF 并返回 bytes（用于 Streamlit download_button）
    """
    import os, io, re
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # 注册中文字体（macOS + Linux 多路径）
    font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",   # Debian/Ubuntu (packages.txt)
        "/System/Library/Fonts/STHeiti Light.ttc",          # macOS
        "/System/Library/Fonts/STHeiti Medium.ttc",          # macOS
        "/System/Library/Fonts/Supplemental/Songti.ttc",     # macOS
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]

    cn_font_name = "Helvetica"
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont("ChineseFont", fp))
                cn_font_name = "ChineseFont"
                break
            except Exception:
                continue

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    title_style = ParagraphStyle(
        'ChineseTitle', fontName=cn_font_name,
        fontSize=18, textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=20, alignment=TA_CENTER, leading=24
    )
    h1_style = ParagraphStyle(
        'ChineseH1', fontName=cn_font_name,
        fontSize=14, textColor=colors.HexColor('#2c3e50'),
        spaceAfter=10, spaceBefore=16, leading=20
    )
    h2_style = ParagraphStyle(
        'ChineseH2', fontName=cn_font_name,
        fontSize=12, textColor=colors.HexColor('#34495e'),
        spaceAfter=8, spaceBefore=12, leading=18
    )
    body_style = ParagraphStyle(
        'ChineseBody', fontName=cn_font_name,
        fontSize=10, textColor=colors.HexColor('#333333'),
        leading=16, spaceAfter=4
    )

    story = []
    lines = markdown_content.split('\n')
    for line in lines:
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 0.3*cm))
            continue

        parts = re.split(r'(\*\*.*?\*\*)', stripped)
        para_parts = []
        for p in parts:
            if p.startswith('**') and p.endswith('**'):
                para_parts.append(f'<b>{p[2:-2]}</b>')
            else:
                para_parts.append(p)
        text = ''.join(para_parts)

        if stripped.startswith('# ') and not stripped.startswith('## '):
            story.append(Paragraph(text[2:], title_style))
        elif stripped.startswith('## '):
            story.append(Paragraph(text[3:], h1_style))
        elif stripped.startswith('### '):
            story.append(Paragraph(text[4:], h2_style))
        elif stripped.startswith('|') and '---' not in stripped:
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if cells:
                t = Table([cells], colWidths=[doc.width/len(cells)]*len(cells))
                t.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (-1, -1), cn_font_name),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(t)
        elif stripped.startswith('- '):
            story.append(Paragraph(f"• {text[2:]}", body_style))
        elif stripped.startswith('---'):
            story.append(Spacer(1, 0.5*cm))
        else:
            story.append(Paragraph(text, body_style))

    doc.build(story)
    return buf.getvalue()

def generate_pdf_report(markdown_content: str, output_path: str) -> bool:
    """将 Markdown 报告保存为 PDF 文件"""
    try:
        pdf_bytes = generate_pdf_bytes(markdown_content)
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)
        return True
    except Exception as e:
        print(f"PDF 生成失败: {e}")
        return False

def save_report(case_id: str, markdown_content: str, output_dir: str = "data/reports") -> str:
    """
    保存报告到文件
    返回文件路径
    """
    os.makedirs(output_dir, exist_ok=True)

    # 保存 Markdown
    md_path = os.path.join(output_dir, f"{case_id}_report.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    # 生成 PDF
    pdf_path = os.path.join(output_dir, f"{case_id}_report.pdf")
    try:
        generate_pdf_report(markdown_content, pdf_path)
    except Exception as e:
        print(f"PDF 生成失败: {e}")
        pdf_path = None

    return md_path, pdf_path

if __name__ == "__main__":
    # 测试
    test_case = {"name": "测试案件", "cause_type": "商标侵权"}
    test_score = {"recommendation": "建议起诉", "final_score": 75, "confidence_score": 70}
    test_rules = []
    test_analysis = {"elements": []}

    md = generate_markdown_report(test_case, test_score, test_rules, test_analysis)
    print(md[:500])
