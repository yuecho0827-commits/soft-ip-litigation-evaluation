"""
证据文件解析器
- PDF：pymupdf 文本提取
- 图片：PaddleOCR / Tesseract / RapidOCR（多引擎自动切换）
"""

import io
import numpy as np
from typing import Dict

import fitz  # pymupdf
from PIL import Image


# ── 检测可用的 OCR 引擎 ──

_TESSERACT_OK = False
_PADDLEOCR_OK = False
_RAPIDOCR_OK = False
_paddle_engine = None
_rapid_engine = None

# Tesseract
try:
    import pytesseract
    _TESSERACT_OK = True
except ImportError:
    pass

# PaddleOCR
try:
    from paddleocr import PaddleOCR
    _paddle_engine = PaddleOCR(lang='ch', use_angle_cls=True, show_log=False)
    _PADDLEOCR_OK = True
except ImportError:
    pass
except Exception:
    pass  # 模型下载失败等

# RapidOCR（备用）
if not _PADDLEOCR_OK and not _TESSERACT_OK:
    try:
        from rapidocr_onnxruntime import RapidOCR
        _rapid_engine = RapidOCR()
        _RAPIDOCR_OK = True
    except ImportError:
        pass
    except Exception:
        pass


# ── PDF 解析 ──

def parse_pdf(file_bytes: bytes, filename: str) -> Dict:
    """解析 PDF 文件，提取全部文本"""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        full_text = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                full_text.append(f"--- 第 {page.number + 1} 页 ---\n{text.strip()}")

        return {
            "success": True, "text": "\n\n".join(full_text),
            "page_count": len(doc), "filename": filename, "error": ""
        }
    except Exception as e:
        return {"success": False, "text": "", "page_count": 0, "filename": filename, "error": str(e)}


# ── 图片 OCR（多引擎自动切换）──

def ocr_image(image_bytes: bytes, filename: str) -> Dict:
    """
    识别图片中的文字，自动选择可用引擎：
      1. PaddleOCR（用户首选）
      2. Tesseract（系统已安装时）
      3. RapidOCR（纯 pip 备选）
    """
    image = Image.open(io.BytesIO(image_bytes))

    # ── 引擎 1：PaddleOCR ──
    if _PADDLEOCR_OK and _paddle_engine:
        try:
            img_array = np.array(image.convert("RGB"))
            result = _paddle_engine.ocr(img_array)

            texts = []
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) >= 2:
                        texts.append(line[1][0])

            if texts:
                return {"success": True, "text": "\n".join(texts), "filename": filename, "error": "", "engine": "PaddleOCR"}
            else:
                return {"success": False, "text": "", "filename": filename,
                        "error": "PaddleOCR 未识别到文字，可能图片质量过低或不含文字", "engine": "PaddleOCR"}
        except Exception as e:
            pass  # 回退到下一个引擎

    # ── 引擎 2：Tesseract ──
    if _TESSERACT_OK:
        try:
            text = pytesseract.image_to_string(image, lang="chi_sim+eng")
            if text.strip():
                return {"success": True, "text": text.strip(), "filename": filename, "error": "", "engine": "Tesseract"}
        except pytesseract.pytesseract.TesseractNotFoundError:
            pass
        except pytesseract.pytesseract.TesseractError:
            pass
        except Exception:
            pass

    # ── 引擎 3：RapidOCR ──
    if _RAPIDOCR_OK and _rapid_engine:
        try:
            img_array = np.array(image.convert("RGB"))
            result, _ = _rapid_engine(img_array)

            texts = []
            if result:
                for line in result:
                    if line and len(line) >= 2:
                        texts.append(line[1])

            if texts:
                return {"success": True, "text": "\n".join(texts), "filename": filename, "error": "", "engine": "RapidOCR"}
        except Exception:
            pass

    # ── 所有引擎都不可用 ──
    return {
        "success": False, "text": "", "filename": filename,
        "error": (
            "未找到可用的 OCR 引擎，请安装以下任一引擎：\n\n"
            "方式1（推荐）：pip install paddlepaddle paddleocr -i https://pypi.tuna.tsinghua.edu.cn/simple\n"
            "方式2（备选）：pip install rapidocr-onnxruntime\n"
            "方式3（系统级）：brew install tesseract"
        )
    }


def is_image_file(filename: str) -> bool:
    ext = filename.lower()
    return ext.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'))


def is_pdf_file(filename: str) -> bool:
    return filename.lower().endswith('.pdf')
