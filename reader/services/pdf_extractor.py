import logging
import os
from io import BytesIO
from pathlib import Path

import fitz
import pytesseract
from PIL import Image


TESSERACT_DIR = Path(
    r"C:\Program Files\Tesseract-OCR"
)

TESSDATA_DIR = Path(
    os.getenv(
        "TESSDATA_DIR",
        str(TESSERACT_DIR / "tessdata"),
    )
)

LOCAL_TESSERACT = TESSERACT_DIR / "tesseract.exe"

if os.getenv("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.environ[
        "TESSERACT_CMD"
    ]
elif LOCAL_TESSERACT.is_file():
    pytesseract.pytesseract.tesseract_cmd = str(
        LOCAL_TESSERACT
    )

if TESSDATA_DIR.is_dir():
    os.environ["TESSDATA_PREFIX"] = str(TESSDATA_DIR)




logger = logging.getLogger(__name__)



OCR_LANGUAGES = os.getenv("ECHOREAD_OCR_LANGUAGES", "eng+khm")
MIN_NATIVE_TEXT_LENGTH = 150


def _get_text_blocks(page):
    """Extract native text blocks without sorting them."""
    blocks = []

    for index, block in enumerate(page.get_text("blocks", sort=False)):
        x0, y0, x1, y1, text = block[:5]
        block_type = block[6] if len(block) > 6 else 0

        if block_type != 0 or not text.strip():
            continue

        blocks.append({
            "id": index,
            "x0": x0,
            "y0": y0,
            "x1": x1,
            "y1": y1,
            "text": text.strip(),
        })

    return blocks


def _join_visual_lines(text):
    """
    Join wrapped lines into readable paragraphs.
    Preserve blank lines as paragraph boundaries.
    """
    paragraphs = []
    current_lines = []

    for line in text.splitlines():
        line = line.strip()

        if not line:
            if current_lines:
                paragraphs.append(" ".join(current_lines))
                current_lines = []
            continue

        current_lines.append(line)

    if current_lines:
        paragraphs.append(" ".join(current_lines))

    return "\n".join(paragraphs)


def _detect_column_split(blocks, page_width):
    """
    Find a plausible central gutter between two text columns.

    This only finds a candidate split. Actual reordering happens
    locally in _order_blocks(), between full-width blocks.
    """
    if len(blocks) < 6:
        return None

    candidates = set()

    for left in blocks:
        for right in blocks:
            if left["x1"] >= right["x0"]:
                continue

            gap = right["x0"] - left["x1"]

            if gap >= page_width * 0.04:
                candidates.add(
                    round((left["x1"] + right["x0"]) / 2, 2)
                )

    best_split = None
    best_score = None

    for split_x in candidates:
        left_blocks = [
            b for b in blocks if b["x1"] <= split_x
        ]
        right_blocks = [
            b for b in blocks if b["x0"] >= split_x
        ]

        # Ignore splits that leave too little content on either side.
        if len(left_blocks) < 2 or len(right_blocks) < 2:
            continue

        left_top = min(b["y0"] for b in left_blocks)
        left_bottom = max(b["y1"] for b in left_blocks)
        right_top = min(b["y0"] for b in right_blocks)
        right_bottom = max(b["y1"] for b in right_blocks)

        overlap = min(left_bottom, right_bottom) - max(
            left_top, right_top
        )

        shorter_height = min(
            left_bottom - left_top,
            right_bottom - right_top,
        )

        if shorter_height <= 0:
            continue

        overlap_ratio = overlap / shorter_height

        if overlap_ratio < 0.5:
            continue

        # Prefer balanced columns and a gutter near the page centre.
        balance = min(len(left_blocks), len(right_blocks))
        centre_penalty = abs(split_x - page_width / 2) / page_width

        score = (
            balance * 3
            + overlap_ratio * 5
            - centre_penalty * 2
        )

        if best_score is None or score > best_score:
            best_score = score
            best_split = split_x

    return best_split


def _is_column_region(blocks, split_x):
    """Check whether a local group looks like a genuine two-column region."""
    left = [b for b in blocks if b["x1"] <= split_x]
    right = [b for b in blocks if b["x0"] >= split_x]

    # Blocks crossing the split should have already separated regions.
    if len(left) + len(right) != len(blocks):
        return False

    if len(left) < 2 or len(right) < 2:
        return False

    left_top = min(b["y0"] for b in left)
    left_bottom = max(b["y1"] for b in left)
    right_top = min(b["y0"] for b in right)
    right_bottom = max(b["y1"] for b in right)

    overlap = min(left_bottom, right_bottom) - max(
        left_top, right_top
    )

    shorter_height = min(
        left_bottom - left_top,
        right_bottom - right_top,
    )

    if shorter_height < 40:
        return False

    return overlap / shorter_height >= 0.6


def _order_blocks(page, blocks):
    """
    Preserve full-width content in page order and reorder only
    local regions that appear to contain two text columns.
    """
    if not blocks:
        return ""

    split_x = _detect_column_split(blocks, page.rect.width)

    # No convincing central gutter: use ordinary reading order.
    if split_x is None:
        ordered = sorted(blocks, key=lambda b: (b["y0"], b["x0"]))
        return "\n".join(
            _join_visual_lines(b["text"]) for b in ordered
        )

    ordered_by_position = sorted(
        blocks, key=lambda b: (b["y0"], b["x0"])
    )

    output = []
    region = []

    def flush_region():
        """Reorder a region only if it is convincingly two-column."""
        if not region:
            return

        if _is_column_region(region, split_x):
            left = sorted(
                (b for b in region if b["x1"] <= split_x),
                key=lambda b: (b["y0"], b["x0"]),
            )
            right = sorted(
                (b for b in region if b["x0"] >= split_x),
                key=lambda b: (b["y0"], b["x0"]),
            )
            output.extend(left)
            output.extend(right)
        else:
            output.extend(
                sorted(region, key=lambda b: (b["y0"], b["x0"]))
            )

        region.clear()

    
    for block in ordered_by_position:
        crosses_split = (
            block["x0"] < split_x < block["x1"]
        )

        if crosses_split:
            # A full-width heading, paragraph, or table separates regions.
            flush_region()
            output.append(block)
        else:
            # NEW: Separate regions when there's a large vertical gap.
            if region:
                region_bottom = max(
                    item["y1"] for item in region
                )
                vertical_gap = block["y0"] - region_bottom

                gap_threshold = max(
                    25, page.rect.height * 0.03
                )

                if vertical_gap > gap_threshold:
                    flush_region()

            region.append(block)

    flush_region()

    return "\n".join(
        _join_visual_lines(b["text"]) for b in output
    )




def _get_ocr_blocks(page):
    """
    Extract OCR text with positional information.

    Convert OCR pixel coordinates back to PDF page coordinates
    so the existing column-ordering logic can be reused.
    """
    for language in ("eng", "khm"):
        traineddata = TESSDATA_DIR / f"{language}.traineddata"
        if not traineddata.is_file():
            raise FileNotFoundError(
                f"Missing Tesseract language data: {traineddata}"
            )

    scale = 2.5
    pixmap = page.get_pixmap(
        matrix=fitz.Matrix(scale, scale),
        alpha=False,
    )

    with Image.open(BytesIO(pixmap.tobytes("png"))) as image:
        data = pytesseract.image_to_data(
            image,
            lang=OCR_LANGUAGES,
            config="--psm 3",
            output_type=pytesseract.Output.DICT,
        )

    # Group recognized words by their OCR paragraph.
    paragraphs = {}

    for i, word in enumerate(data["text"]):
        word = word.strip()
        if not word:
            continue

        block_num = data["block_num"][i]
        par_num = data["par_num"][i]
        line_num = data["line_num"][i]
        word_num = data["word_num"][i]

        key = (block_num, par_num)

        left = data["left"][i]
        top = data["top"][i]
        right = left + data["width"][i]
        bottom = top + data["height"][i]

        if key not in paragraphs:
            paragraphs[key] = {
                "words": [],
                "x0": left,
                "y0": top,
                "x1": right,
                "y1": bottom,
            }

        paragraph = paragraphs[key]
        paragraph["words"].append(
            (line_num, word_num, word)
        )

        paragraph["x0"] = min(paragraph["x0"], left)
        paragraph["y0"] = min(paragraph["y0"], top)
        paragraph["x1"] = max(paragraph["x1"], right)
        paragraph["y1"] = max(paragraph["y1"], bottom)

    blocks = []

    for index, paragraph in enumerate(paragraphs.values()):
        words = sorted(
            paragraph["words"],
            key=lambda item: (item[0], item[1]),
        )

        lines = []
        current_line = []
        previous_line_num = None

        for line_num, word_num, word in words:
            if (
                previous_line_num is not None
                and line_num != previous_line_num
            ):
                lines.append(" ".join(current_line))
                current_line = []

            current_line.append(word)
            previous_line_num = line_num

        if current_line:
            lines.append(" ".join(current_line))

        blocks.append({
            "id": index,
            "x0": paragraph["x0"] / scale,
            "y0": paragraph["y0"] / scale,
            "x1": paragraph["x1"] / scale,
            "y1": paragraph["y1"] / scale,
            "text": "\n".join(lines),
        })

    return blocks


def _ocr_page(page):
    """OCR a page and apply the shared reading-order logic."""
    blocks = _get_ocr_blocks(page)

    if not blocks:
        return ""

    return _order_blocks(page, blocks).strip()



def extract_pdf_pages(pdf_bytes, mode="normal"):
    """
    normal: native extraction, with OCR fallback for sparse pages.
    hard: OCR every page.
    """
    if mode not in ("normal", "hard"):
        raise ValueError("Unknown scan mode.")

    if not pdf_bytes:
        raise ValueError("The PDF file is empty.")

    results = []

    with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
        if pdf.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported.")

        for index, page in enumerate(pdf):
            used_ocr = mode == "hard"

            if used_ocr:
                text = _ocr_page(page)
            else:
                blocks = _get_text_blocks(page)
                text = _order_blocks(page, blocks)

                if len(text.strip()) < MIN_NATIVE_TEXT_LENGTH:
                    logger.info(
                        "Page %s has little native text; trying OCR.",
                        index + 1,
                    )
                    text = _ocr_page(page)
                    used_ocr = True

            results.append({
                "page_number": index + 1,
                "text": text,
                "used_ocr": used_ocr,
            })
    return results


