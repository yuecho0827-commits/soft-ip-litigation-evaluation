"""
证据文件解析器
- PDF：pymupdf 文本提取
- 图片：PaddleOCR / Tesseract / RapidOCR（多引擎自动切换）
"""
import io
from typing import Dict
try:
    import numpy as np
    _NUMPY_OK = True
except Exception:
    _NUMPY_OK = False
try:
    import fitz
    _FITZ_OK = True
except Exception:
    _FITZ_OK = False
try:
    from PIL import Image
    _PIL_OK = True
except Exception:
    _PIL_OK = False
_TESSERACT_OK = False
_PADDLEOCR_OK = False
_RAPIDOCR_OK = False
_paddle_engine = None
_rapid_engine = None
try:
    import pytesseract
    _TESSERACT_OK = True
except ImportError:
    pass

def _init_paddleocr():
    global _paddle_engine, _PADDLEOCR_OK
    if _PADDLEOCR_OK or _paddle_engine:
        return _PADDLEOCR_OK
    try:
        from paddleocr import PaddleOCR
        _paddle_engine = PaddleOCR(lang='ch', use_textline_orientation=True)
        _PADDLEOCR_OK = True
    except Exception:
        _PADDLEOCR_OK = False
    return _PADDLEOCR_OK

def _init_rapidocr():
    global _rapid_engine, _RAPIDOCR_OK
    if _RAPIDOCR_OK or _rapid_engine:
        return _RAPIDOCR_OK
    try:
        from rapidocr_onnxruntime import RapidOCR
        _rapid_engine = RapidOCR()
        _RAPIDOCR_OK = True
    except Exception:
        _RAPIDOCR_OK = False
    return _RAPIDOCR_OK

def _build_result(success: bool, text: str, filename: str, error: str = '', **extra) -> Dict:
    """构建统一的解析结果字典"""
    result = {'success': success, 'text': text, 'filename': filename, 'error': error}
    result.update(extra)
    return result


def parse_pdf(file_bytes: bytes, filename: str) -> Dict:
    """解析 PDF 文件，提取全部文本"""
    if not _FITZ_OK:
        return _build_result(False, '', filename, error='pymupdf 未安装。请运行: pip install pymupdf')
    try:
        doc = fitz.open(stream=file_bytes, filetype='pdf')
        full_text = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                full_text.append('--- 第 {} 页 ---\n{}'.format(page.number + 1, text.strip()))
        return _build_result(True, '\n\n'.join(full_text), filename, page_count=len(doc))
    except Exception as e:
        return _build_result(False, '', filename, page_count=0, error=str(e))

def _ocr_with_paddle(image, filename: str) -> Dict:
    """PaddleOCR 引擎识别"""
    if not _init_paddleocr():
        return None
    try:
        if not _NUMPY_OK:
            raise RuntimeError('numpy 未安装')
        img_array = np.array(image.convert('RGB'))
        result = _paddle_engine.ocr(img_array)
        texts = []
        if result and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    texts.append(line[1][0])
        if texts:
            return _build_result(True, '\n'.join(texts), filename, engine='PaddleOCR')
        return _build_result(False, '', filename, error='PaddleOCR 未识别到文字', engine='PaddleOCR')
    except Exception:
        return None


def _ocr_with_tesseract(image, filename: str) -> Dict:
    """Tesseract 引擎识别"""
    if not _TESSERACT_OK:
        return None
    try:
        text = pytesseract.image_to_string(image, lang='chi_sim+eng')
        if text.strip():
            return _build_result(True, text.strip(), filename, engine='Tesseract')
    except Exception:
        pass
    return None


def _ocr_with_rapid(image, filename: str) -> Dict:
    """RapidOCR 引擎识别"""
    if not _init_rapidocr():
        return None
    try:
        if not _NUMPY_OK:
            raise RuntimeError('numpy 未安装')
        img_array = np.array(image.convert('RGB'))
        result, _ = _rapid_engine(img_array)
        texts = []
        if result:
            for line in result:
                if line and len(line) >= 2:
                    texts.append(line[1])
        if texts:
            return _build_result(True, '\n'.join(texts), filename, engine='RapidOCR')
    except Exception:
        pass
    return None


OCR_ENGINES = [_ocr_with_paddle, _ocr_with_tesseract, _ocr_with_rapid]


def ocr_image(image_bytes: bytes, filename: str) -> Dict:
    """识别图片中的文字，自动选择可用引擎"""
    if not _PIL_OK:
        return _build_result(False, '', filename, error='Pillow 未安装。请运行: pip install Pillow')
    image = Image.open(io.BytesIO(image_bytes))
    for engine_func in OCR_ENGINES:
        result = engine_func(image, filename)
        if result is not None:
            return result
    return _build_result(False, '', filename, error='未找到可用的 OCR 引擎。请安装以下任一：\n\n方式1（推荐）: pip install paddlepaddle paddleocr\n方式2（备选）: pip install rapidocr-onnxruntime\n方式3（系统）: brew install tesseract')

def is_image_file(filename: str) -> bool:
    ext = filename.lower()
    return ext.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'))

def is_pdf_file(filename: str) -> bool:
    return filename.lower().endswith('.pdf')