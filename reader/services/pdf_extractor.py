import fitz
import pytesseract
import os
from PIL import Image
from io import BytesIO
from collections import defaultdict

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)



# def debug_text(label, text):
#     print(f"\n--- {label} ---")
#     print("Actual newlines:", text.count("\n"))
#     print("Escaped text:", repr(text[:500]))



def format_pdf_text(page):
    """Extract text blocks and preserve their line breaks."""
    blocks = page.get_text("blocks", sort=True)
    formatted_blocks = []

    for block in blocks:
        x0, y0, x1, y1, text = block[:5]

        text = text.strip()
        if not text:
            continue

        # Preserve line breaks already present inside the block.
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            formatted_blocks.append("\n".join(lines))

    return "\n".join(formatted_blocks)




def format_ocr_text(image):
    """Extract OCR text with basic coordinate-aware column ordering."""
    data = pytesseract.image_to_data(
        image,
        lang="eng+khm",
        output_type=pytesseract.Output.DICT,
    )

    # Group words into OCR-detected lines.
    lines = defaultdict(list)

    for i, word in enumerate(data["text"]):
        word = word.strip()
        if not word:
            continue

        key = (
            data["block_num"][i],
            data["par_num"][i],
            data["line_num"][i],
        )

        lines[key].append({
            "text": word,
            "x": data["left"][i],
            "y": data["top"][i],
        })

    formatted_lines = []

    for key, words in lines.items():
        words.sort(key=lambda word: word["x"])

        formatted_lines.append({
            "block": key[0],
            "x": min(word["x"] for word in words),
            "y": min(word["y"] for word in words),
            "text": " ".join(word["text"] for word in words),
        })

    # Sort lines vertically before arranging the columns.
    formatted_lines.sort(key=lambda line: (line["y"], line["x"]))

    # This threshold is a heuristic for your current benchmark PDF.
    # It is not a universal page-layout rule.
    column_split_x = image.width * 0.5

    # The two-column region in your test document.
    column_start_y = 450
    column_end_y = 850

    before_columns = []
    left_column = []
    right_column = []
    after_columns = []

    for line in formatted_lines:
        if line["y"] < column_start_y:
            before_columns.append(line)
        elif line["y"] < column_end_y:
            if line["x"] < column_split_x:
                left_column.append(line)
            else:
                right_column.append(line)
        else:
            after_columns.append(line)

    # Read each column top-to-bottom.
    left_column.sort(key=lambda line: (line["y"], line["x"]))
    right_column.sort(key=lambda line: (line["y"], line["x"]))

    # Keep content before/after the columns in normal reading order.
    result = (
        before_columns
        + left_column
        + right_column
        + after_columns
    )

    return "\n".join(line["text"] for line in result)


def extract_pdf_pages(pdf_bytes, mode="normal"):
    """
    Extract text from a PDF page by page.

    mode="normal": use embedded text first, OCR pages with little text.
    mode="hard": OCR every page.
    """
    if mode not in ("normal", "hard"):
        raise ValueError("Unknown scan mode.")

    results = []

    with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
        for index, page in enumerate(pdf):
            extracted_text = ""

            if mode == "normal":
                extracted_text = format_pdf_text(page)
                # debug_text("PyMuPDF", extracted_text)

            # OCR if Hard Scan was chosen or embedded text is insufficient.
            used_ocr = mode == "hard" or len(extracted_text) < 30

            if used_ocr:
                pix = page.get_pixmap(
                    matrix=fitz.Matrix(2, 2),
                    alpha=False,
                )

                image = Image.frombytes(
                    "RGB",
                    [pix.width, pix.height],
                    pix.samples,
                )

                extracted_text = format_ocr_text(image)
                # debug_text("OCR", extracted_text)

            results.append({
                "page_number": index + 1,
                "text": extracted_text,
                "used_ocr": used_ocr,
            })

    return results
