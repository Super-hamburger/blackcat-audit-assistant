from pathlib import Path
import fitz

class PdfEngine:
    def __init__(self, pdf_path):
        self.pdf_path = Path(pdf_path)

    def get_page_count(self):
        with fitz.open(self.pdf_path) as doc:
            return len(doc)

    def extract_text(self, page_index):
        with fitz.open(self.pdf_path) as doc:
            return doc.load_page(page_index).get_text()

    def extract_words(self, page_index):
        with fitz.open(self.pdf_path) as doc:
            page = doc.load_page(page_index)
            words = []
            for item in page.get_text("words"):
                words.append({
                    "x0": float(item[0]),
                    "y0": float(item[1]),
                    "x1": float(item[2]),
                    "y1": float(item[3]),
                    "text": str(item[4]),
                })
            rect = page.rect
            return {
                "words": words,
                "page_rect": {
                    "width": float(rect.width),
                    "height": float(rect.height),
                },
            }

    def save_single_page(self, page_index, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with fitz.open(self.pdf_path) as source_doc:
            target_doc = fitz.open()
            target_doc.insert_pdf(source_doc, from_page=page_index, to_page=page_index)
            target_doc.save(output_path)
            target_doc.close()
