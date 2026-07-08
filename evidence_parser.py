"""
证据文件解析器
- PDF：pymupdf 文本提取
- 图片：Tesseract OCR（离线，无需 API）
- 证据分类：LLM 自动标注证据类型
"""

import io
from typing import Dict

import fitz  # pymupdf
import pytesseract
from PIL import Image


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


def ocr_image(image_bytes: bytes, filename: str) -> Dict:
    """
    用 Tesseract OCR 识别图片中的文字（离线，无需 API）
    需要先安装：brew install tesseract tesseract-lang
    返回 {"success": bool, "text": str, "error": str}
    """
    try:
        # 加载图片
        image = Image.open(io.BytesIO(image_bytes))

        # OCR 识别（中英文混合）
        text = pytesseract.image_to_string(image, lang="chi_sim+eng")

        if not text.strip():
            return {
                "success": False,
                "text": "",
                "filename": filename,
                "error": "图片中未识别到文字，可能图片质量过低或不含文字"
            }

        return {
            "success": True,
            "text": text.strip(),
            "filename": filename,
            "error": ""
        }

    except pytesseract.pytesseract.TesseractNotFoundError:
        return {
            "success": False,
            "text": "",
            "filename": filename,
            "error": "Tesseract 未安装。\n\n本地环境：\n  macOS: brew install --build-from-source tesseract\n  或: conda install -c conda-forge tesseract\n\nStreamlit Cloud 上自动可用，无需安装。"
        }
    except pytesseract.pytesseract.TesseractError as e:
        if "chi_sim" in str(e) or "traineddata" in str(e):
            return {
                "success": False,
                "text": "",
                "filename": filename,
                "error": "缺少中文语言包。\n\n本地环境：\n  brew install tesseract-lang\n\n或使用英文模式：\n  brew install tesseract\n\nStreamlit Cloud 上自动可用。"
            }
        return {
            "success": False,
            "text": "",
            "filename": filename,
            "error": f"OCR 识别失败: {e}"
        }
    except Exception as e:
        return {
            "success": False,
            "text": "",
            "filename": filename,
            "error": f"图片处理失败: {e}"
        }


def is_image_file(filename: str) -> bool:
    """判断是否为图片文件"""
    ext = filename.lower()
    return ext.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'))


def is_pdf_file(filename: str) -> bool:
    """判断是否为 PDF 文件"""
    return filename.lower().endswith('.pdf')
