import fitz
import pytest
from app.extraction.files import pdf_text, image_text

def test_pdf_page_text_is_extracted_with_page_reference():
    doc=fitz.open()
    page=doc.new_page()
    page.insert_text((72,72),'A verifiable news claim on page one.')
    raw=doc.tobytes()
    text,pages=pdf_text(raw)
    assert '[Page 1]' in text
    assert 'verifiable news claim' in text
    assert pages==[1]

def test_invalid_image_is_rejected():
    with pytest.raises(ValueError): image_text(b'not an image')

def test_image_ocr_recognizes_english_text():
    from io import BytesIO
    from PIL import Image, ImageDraw
    image=Image.new('RGB',(900,180),'white')
    ImageDraw.Draw(image).text((25,50),'Fact check this important news report',fill='black')
    data=BytesIO()
    image.save(data,format='PNG')
    assert 'important' in image_text(data.getvalue()).lower()
