"""
证据文件解析器
- PDF：pymupdf 文本提取
- 图片：DeepSeek Vision API OCR
- 证据分类：LLM 自动标注证据类型
"""

import base64
import json
import io
import urllib.request
import urllib.error
from typing import Dict, List, Tuple

import fitz  # pymupdf


def parse_pdf(file_bytes: bytes, filename: str) -> Dict:
    """
    解析 PDF 文件，提取全部文本
    返回 {"text": str, "page_count": int, "success": bool, "error": str}
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        full_text = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                full_text.append(f"--- 第 {page.number + 1} 页 ---\n{text.strip()}")

        return {
            "success": True,
            "text": "\n\n".join(full_text),
            "page_count": len(doc),
            "filename": filename,
            "error": ""
        }
    except Exception as e:
        return {
            "success": False,
            "text": "",
            "page_count": 0,
            "filename": filename,
            "error": str(e)
        }


def ocr_image(image_bytes: bytes, filename: str, api_key: str) -> Dict:
    """
    用 DeepSeek Vision API 识别图片中的文字
    返回 {"success": bool, "text": str, "error": str}
    """
    try:
        # 将图片转为 base64
        b64_data = base64.b64encode(image_bytes).decode("utf-8")

        # 检测图片格式
        if filename.lower().endswith(".png"):
            mime = "image/png"
        elif filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
            mime = "image/jpeg"
        elif filename.lower().endswith(".webp"):
            mime = "image/webp"
        else:
            mime = "image/png"

        # 调用 DeepSeek API（带图片的 vision 请求）
        url = "https://api.deepseek.com/v1/chat/completions"
        payload = json.dumps({
            "model": "deepseek-chat",
            "max_tokens": 2000,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的OCR文字识别助手。请识别图片中的所有文字内容，原样输出。如果是法律文书、合同、证据材料等，请完整提取所有文字。不要添加任何解释，只输出识别到的文字。"
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64_data}"
                            }
                        },
                        {
                            "type": "text",
                            "text": "请识别这张图片中的所有文字内容。"
                        }
                    ]
                }
            ]
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            ocr_text = result["choices"][0]["message"]["content"]

        return {
            "success": True,
            "text": ocr_text.strip(),
            "filename": filename,
            "error": ""
        }

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        # 检查是否是不支持图片格式的错误
        if "image" in error_body.lower() or "multimodal" in error_body.lower() or "vision" in error_body.lower():
            return {
                "success": False,
                "text": "",
                "filename": filename,
                "error": "当前 DeepSeek 模型不支持图片 OCR，请改用文字描述或升级模型"
            }
        return {
            "success": False,
            "text": "",
            "filename": filename,
            "error": f"API 调用失败: {error_body[:200]}"
        }
    except Exception as e:
        return {
            "success": False,
            "text": "",
            "filename": filename,
            "error": str(e)
        }


def classify_evidence(text: str, api_key: str) -> Dict:
    """
    用 LLM 自动分类证据类型
    返回 {"category": str, "legal_element": str, "summary": str}
    """
    try:
        url = "https://api.deepseek.com/v1/chat/completions"
        payload = json.dumps({
            "model": "deepseek-chat",
            "max_tokens": 500,
            "messages": [
                {
                    "role": "system",
                    "content": """你是一个知识产权法律助手。请根据提供的文本，判断它属于哪种证据类型，并与商标侵权构成要件对应。

证据类型：权利证明 / 侵权证据 / 损害赔偿证据 / 程序性文件 / 其他
法律要件：权利基础 / 商标使用行为 / 商品类似性 / 商标近似性 / 赔偿依据 / 其他

请返回严格 JSON：
{"category": "证据类型", "legal_element": "对应要件", "summary": "30字以内摘要"}"""
                },
                {
                    "role": "user",
                    "content": f"文本内容（前1000字）：\n{text[:1000]}"
                }
            ]
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            raw = result["choices"][0]["message"]["content"].strip()

        # 清理可能出现的 markdown 代码块
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        return json.loads(raw)

    except Exception:
        # 降级：简单关键词匹配
        category = "其他"
        if any(kw in text for kw in ["商标注册", "注册号", "商标证", "续展"]):
            category = "权利证明"
        elif any(kw in text for kw in ["公证", "截图", "购买", "侵权商品", "侵权产品"]):
            category = "侵权证据"
        elif any(kw in text for kw in ["销售额", "利润", "损失", "赔偿", "许可费"]):
            category = "损害赔偿证据"

        return {
            "category": category,
            "legal_element": "待确认",
            "summary": text[:30].replace("\n", " ")
        }


def is_image_file(filename: str) -> bool:
    """判断是否为图片文件"""
    ext = filename.lower()
    return ext.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'))


def is_pdf_file(filename: str) -> bool:
    """判断是否为 PDF 文件"""
    return filename.lower().endswith('.pdf')
