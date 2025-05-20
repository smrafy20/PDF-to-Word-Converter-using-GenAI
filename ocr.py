import os
import tempfile
from PyPDF2 import PdfReader
import pdf2image
from PIL import Image
from google.cloud import vision
import io
import shutil

def convert_pdf_to_images(pdf_path):
    if not os.path.exists(pdf_path):
        return [], None
    temp_dir = tempfile.mkdtemp()
    try:
        images = pdf2image.convert_from_path(
            pdf_path,
            dpi=200,
            output_folder=temp_dir,
            fmt='jpeg',
            thread_count=os.cpu_count() or 4,
            paths_only=True
        )
        return images, temp_dir
    except Exception:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return [], None

def optimize_image(image_path, max_size=(1500, 1500), quality=85):
    try:
        img = Image.open(image_path)
        if img.width > max_size[0] or img.height > max_size[1]:
            img.thumbnail(max_size, Image.LANCZOS)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
        return img_byte_arr.getvalue()
    except Exception:
        return None

def extract_text_from_image(image_path):
    client = vision.ImageAnnotatorClient()
    img_bytes = optimize_image(image_path)
    if not img_bytes:
        return "--- ERROR: Failed to optimize image ---"
    image = vision.Image(content=img_bytes)
    response = client.text_detection(image=image)
    if response.error.message:
        return f"--- ERROR: {response.error.message} ---"
    texts = response.text_annotations
    if texts:
        return texts[0].description
    return ""
