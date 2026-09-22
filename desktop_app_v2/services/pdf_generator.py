"""Generate searchable PDF from scanned images using pytesseract + PyMuPDF"""
import fitz
import os


def generate_searchable_pdf(image_paths, output_path):
    try:
        import pytesseract
        from PIL import Image
        from config import TESSERACT_CMD
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    except ImportError as e:
        return False, f"Dependencia faltante: {e}"

    master_doc = None
    page_doc = None
    try:
        master_doc = fitz.open()

        for img_path in image_paths:
            if not os.path.exists(img_path):
                continue

            pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                img_path, extension='pdf', lang='spa'
            )
            page_doc = fitz.open("pdf", pdf_bytes)
            master_doc.insert_pdf(page_doc)
            page_doc.close()
            page_doc = None

        if len(master_doc) == 0:
            return False, "No se generaron paginas"

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        master_doc.save(output_path)
        return True, None

    except Exception as e:
        return False, str(e)
    finally:
        if page_doc:
            page_doc.close()
        if master_doc:
            master_doc.close()
