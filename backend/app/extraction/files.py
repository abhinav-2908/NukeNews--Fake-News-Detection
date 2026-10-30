from io import BytesIO
from PIL import Image, ImageOps
from app.core.config import settings

def pdf_text(data: bytes) -> tuple[str,list[int]]:
    try:
        import fitz
    except ImportError as exc:
        raise ValueError("PDF extraction requires PyMuPDF. Install backend requirements and retry.") from exc
    doc=fitz.open(stream=data,filetype="pdf")
    if doc.is_encrypted: raise ValueError("Encrypted PDFs are not supported.")
    if len(doc)>100: raise ValueError("PDF exceeds the 100-page limit.")
    pages=[]
    for i,p in enumerate(doc):
        content=p.get_text().strip()
        if not content:
            try:
                import pytesseract
                from PIL import Image
                pix=p.get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False)
                content=pytesseract.image_to_string(Image.open(BytesIO(pix.tobytes("png"))),lang=settings.ocr_languages).strip()
            except Exception:
                content=""
        if content: pages.append(f"[Page {i+1}] {content}")
    return "\n\n".join(pages),list(range(1,len(doc)+1))

def image_text(data: bytes) -> str:
    try: im=Image.open(BytesIO(data)); im.verify(); im=Image.open(BytesIO(data))
    except Exception as exc: raise ValueError("Image is invalid or unsupported.") from exc
    if im.format not in ("PNG","JPEG","WEBP"): raise ValueError("Use PNG, JPEG, or WebP images.")
    if im.width*im.height>25_000_000: raise ValueError("Image dimensions exceed the 25 megapixel limit.")
    try:
        import pytesseract
        return pytesseract.image_to_string(ImageOps.exif_transpose(im),lang=settings.ocr_languages).strip()
    except Exception as exc: raise ValueError("OCR is unavailable. Install Tesseract with English and Hindi language packs.") from exc
