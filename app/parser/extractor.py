import logging
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image as PILImage
import pdfplumber

try:
    import pytesseract
except ImportError:
    pytesseract = None

from app.schemas.parser import ParsedNode

logger = logging.getLogger(__name__)

class PDFParser:
    """
    Service to extract structured layout elements from PDF manuals and build a tree hierarchy.
    """

    def __init__(self, tesseract_cmd: Optional[str] = None):
        if tesseract_cmd and pytesseract:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def parse(self, file_path: str) -> ParsedNode:
        """
        Parses a PDF file into a single root ParsedNode representing the hierarchy.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        logger.info(f"Starting PDF extraction for: {file_path}")
        all_blocks: List[Dict[str, Any]] = []
        global_order_index = 0

        with pdfplumber.open(file_path) as pdf:
            # 1. Estimate standard/median font size for the document
            median_font_size = self._estimate_median_font_size(pdf)
            logger.info(f"Estimated document median body font size: {median_font_size}")

            for page_num, page in enumerate(pdf.pages, start=1):
                logger.debug(f"Parsing page {page_num}/{len(pdf.pages)}")
                
                # Check if page is empty or scanned
                text_content = page.extract_text() or ""
                if len(text_content.strip()) < 100:
                    logger.info(f"Page {page_num} has minimal text ({len(text_content.strip())} chars). Triggering OCR fallback.")
                    page_blocks = self._parse_page_ocr(page, page_num)
                else:
                    page_blocks = self._parse_page_native(page, page_num, median_font_size)

                # Assign order index to each block
                for block in page_blocks:
                    block["order_index"] = global_order_index
                    global_order_index += 1
                    all_blocks.append(block)

        # 2. Reconstruct tree hierarchy from flat blocks
        return self._reconstruct_tree(all_blocks)

    def _estimate_median_font_size(self, pdf: pdfplumber.PDF) -> float:
        """
        Calculate the median font size across the first few pages of the document to establish a baseline.
        """
        sizes: List[float] = []
        # Sample up to 5 pages
        for page in pdf.pages[:5]:
            try:
                words = page.extract_words(extra_attrs=["size"])
                for w in words:
                    size = w.get("size")
                    if size:
                        sizes.append(float(size))
            except Exception:
                continue
        
        if not sizes:
            return 10.0  # Default fallback size
        
        sizes.sort()
        return sizes[len(sizes) // 2]

    def _parse_page_native(self, page: pdfplumber.page.Page, page_num: int, median_font_size: float) -> List[Dict[str, Any]]:
        """
        Extracts paragraphs, headings, lists, tables, and images metadata natively from PDF.
        """
        blocks: List[Dict[str, Any]] = []

        # Find tables and images bounding boxes to avoid capturing text inside them as duplicate paragraphs
        tables = page.find_tables()
        table_bboxes = [t.bbox for t in tables]

        # Extract images
        for img in page.images:
            # images have x0, top, x1, bottom
            top = img.get("top", img.get("y0", 0))
            blocks.append({
                "type": "image",
                "y_pos": float(top),
                "heading": None,
                "level": 0,
                "body": f"[Image metadata: width={img.get('width')}, height={img.get('height')}]",
                "metadata": {
                    "width": float(img.get("width", 0)),
                    "height": float(img.get("height", 0)),
                    "x0": float(img.get("x0", 0)),
                    "top": float(top),
                    "page": page_num
                }
            })

        # Process tables
        for tbl in tables:
            table_data = tbl.extract()
            markdown_table = self._table_to_markdown(table_data)
            blocks.append({
                "type": "table",
                "y_pos": float(tbl.bbox[1]),  # top coordinate of table
                "heading": None,
                "level": 0,
                "body": markdown_table,
                "metadata": {
                    "page": page_num,
                    "bbox": [float(val) for val in tbl.bbox]
                }
            })

        # Process text words
        try:
            words = page.extract_words(extra_attrs=["fontname", "size"])
        except Exception as e:
            logger.warning(f"Failed to extract native words on page {page_num} with extra attributes: {e}. Trying simple text.")
            words = page.extract_words()

        # Group words into lines
        lines = self._group_words_into_lines(words)

        for line_text, y_pos, avg_size, dominant_font in lines:
            # Skip text that lies inside any table bounding box
            if self._is_inside_any_bbox(y_pos, table_bboxes):
                continue

            # Determine if this line is a heading, list item, or paragraph
            node_type, level = self._classify_text_line(line_text, avg_size, dominant_font, median_font_size)

            blocks.append({
                "type": node_type,
                "y_pos": float(y_pos),
                "heading": line_text if node_type == "heading" else None,
                "level": level,
                "body": None if node_type == "heading" else line_text,
                "metadata": {
                    "page": page_num,
                    "font_size": avg_size,
                    "font_name": dominant_font
                }
            })

        # Sort blocks by vertical position to maintain layout flow
        blocks.sort(key=lambda b: b["y_pos"])
        return blocks

    def _parse_page_ocr(self, page: pdfplumber.page.Page, page_num: int) -> List[Dict[str, Any]]:
        """
        Renders a page to an image and uses Tesseract OCR to extract text when native parser yields nothing.
        """
        blocks: List[Dict[str, Any]] = []

        if not pytesseract:
            logger.error("OCR fallback triggered but pytesseract is not imported/installed. Skipping OCR.")
            return [{
                "type": "paragraph",
                "y_pos": 0.0,
                "heading": None,
                "level": 0,
                "body": f"[Scanned Page {page_num} - OCR skipped due to missing pytesseract]",
                "metadata": {"page": page_num}
            }]

        try:
            # Render page to image
            pil_image = page.to_image(resolution=150).original
            ocr_text = pytesseract.image_to_string(pil_image)
        except Exception as e:
            logger.error(f"Tesseract OCR failed to run on page {page_num}: {e}")
            return [{
                "type": "paragraph",
                "y_pos": 0.0,
                "heading": None,
                "level": 0,
                "body": f"[Scanned Page {page_num} - OCR execution failed: {str(e)}]",
                "metadata": {"page": page_num}
            }]

        # Segment OCR text into paragraph blocks by split
        paragraphs = ocr_text.split("\n\n")
        for idx, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue

            # Basic rule-based heading check on OCR text lines (capitalized/numbered starts)
            first_line = para.split("\n")[0].strip()
            is_heading = False
            level = 0
            if len(first_line) < 100 and (
                re.match(r"^(?:Section\s+)?\d+(?:\.\d+)*\.?\s+[A-Z]", first_line) or
                (first_line.isupper() and len(first_line) > 3)
            ):
                is_heading = True
                level = len(re.findall(r"\d+", first_line.split()[0])) if re.match(r"^\d+", first_line) else 1
                if level == 0:
                    level = 1

            if is_heading:
                # Store heading
                blocks.append({
                    "type": "heading",
                    "y_pos": float(idx),
                    "heading": first_line,
                    "level": level,
                    "body": None,
                    "metadata": {"page": page_num, "ocr": True}
                })
                # Store remaining body if there is one
                remaining_body = "\n".join(para.split("\n")[1:]).strip()
                if remaining_body:
                    blocks.append({
                        "type": "paragraph",
                        "y_pos": float(idx) + 0.5,
                        "heading": None,
                        "level": 0,
                        "body": remaining_body,
                        "metadata": {"page": page_num, "ocr": True}
                    })
            else:
                blocks.append({
                    "type": "paragraph",
                    "y_pos": float(idx),
                    "heading": None,
                    "level": 0,
                    "body": para,
                    "metadata": {"page": page_num, "ocr": True}
                })

        return blocks

    def _group_words_into_lines(self, words: List[Dict[str, Any]], tolerance: float = 3.0) -> List[Tuple[str, float, float, str]]:
        """
        Group individual word bboxes into sequential lines of text.
        Returns a list of Tuple: (line_text, y_pos, avg_size, dominant_font)
        """
        if not words:
            return []

        # Sort words by top coordinate, then by x0
        words = sorted(words, key=lambda w: (w["top"], w["x0"]))

        lines: List[List[Dict[str, Any]]] = []
        current_line: List[Dict[str, Any]] = [words[0]]

        for word in words[1:]:
            # If word is roughly at the same vertical height, group it
            if abs(word["top"] - current_line[-1]["top"]) <= tolerance:
                current_line.append(word)
            else:
                lines.append(current_line)
                current_line = [word]
        lines.append(current_line)

        formatted_lines: List[Tuple[str, float, float, str]] = []
        for line in lines:
            line = sorted(line, key=lambda w: w["x0"])
            text = " ".join([w["text"] for w in line]).strip()
            if not text:
                continue

            y_pos = sum([w["top"] for w in line]) / len(line)
            avg_size = sum([w.get("size", 10.0) for w in line]) / len(line)
            
            # Find dominant font name
            font_names = [w.get("fontname", "default") for w in line]
            dominant_font = max(set(font_names), key=font_names.count)

            formatted_lines.append((text, y_pos, avg_size, dominant_font))

        return formatted_lines

    def _is_inside_any_bbox(self, y_pos: float, bboxes: List[Tuple[float, float, float, float]]) -> bool:
        """
        Check if a given y position lies inside any table bounding box (x0, top, x1, bottom).
        """
        for bbox in bboxes:
            top, bottom = bbox[1], bbox[3]
            if top <= y_pos <= bottom:
                return True
        return False

    def _classify_text_line(self, text: str, font_size: float, font_name: str, median_size: float) -> Tuple[str, int]:
        """
        Classifies a line of text as either a heading, list, or paragraph, and determines level.
        """
        is_bold = "bold" in font_name.lower() or "bd" in font_name.lower()
        is_large = font_size > (median_size * 1.15)

        # Check list pattern (e.g. bullets, 1., a., (1))
        is_list_pattern = (
            re.match(r"^(?:[\u2022\u00b7\u25cf\u25cb\u25aa\-*])\s+", text) or
            re.match(r"^(?:\d+|\w)\.\s+", text) or
            re.match(r"^\(\d+\)\s+", text)
        )

        # Heading regex (e.g., Section 1.2, 1.1.2 Section)
        heading_match = re.match(r"^(?:Section\s+)?(\d+(?:\.\d+)*)\.?\s+[A-Z]", text)

        # A numbered match is a heading if it has multi-level numbering OR heading styles
        is_numbered_heading = False
        if heading_match:
            nums = heading_match.group(1).split(".")
            if len(nums) > 1 or is_large or is_bold:
                is_numbered_heading = True

        if is_list_pattern and not is_numbered_heading:
            return "list", 0

        if is_numbered_heading or is_large or (is_bold and len(text) < 150):
            # Determine heading level
            if heading_match:
                level = len(heading_match.group(1).split("."))
            elif font_size >= median_size * 1.4:
                level = 1
            elif font_size >= median_size * 1.15:
                level = 2
            else:
                level = 3
            return "heading", level

        return "paragraph", 0

    def _table_to_markdown(self, table_data: Optional[List[List[Optional[str]]]]) -> str:
        """
        Converts extracted pdfplumber grid data to a clean Markdown table string.
        """
        if not table_data:
            return ""

        # Filter out empty rows
        rows = [[cell.strip() if cell else "" for cell in row] for row in table_data if any(row)]
        if not rows:
            return ""

        headers = rows[0]
        markdown = "| " + " | ".join(headers) + " |\n"
        markdown += "| " + " | ".join(["---"] * len(headers)) + " |\n"

        for row in rows[1:]:
            # Pad row if it has fewer elements than headers
            if len(row) < len(headers):
                row = row + [""] * (len(headers) - len(row))
            else:
                row = row[:len(headers)]
            markdown += "| " + " | ".join(row) + " |\n"

        return markdown

    def _reconstruct_tree(self, blocks: List[Dict[str, Any]]) -> ParsedNode:
        """
        Organizes a list of flat blocks into a structured tree where child nodes
        are nested under their logical parent headings.
        """
        # Create virtual document root
        root = ParsedNode(
            heading="Document Root",
            level=0,
            node_type="heading",
            order_index=0,
            metadata={"root": True}
        )

        # Stack contains nodes currently being built, starts with root (level 0)
        stack: List[ParsedNode] = [root]

        for block in blocks:
            if block["type"] == "heading":
                node = ParsedNode(
                    heading=block["heading"],
                    level=block["level"],
                    node_type="heading",
                    order_index=block["order_index"],
                    metadata=block["metadata"]
                )

                # Pop from stack until the top element's level is less than the current heading's level
                while len(stack) > 1 and stack[-1].level >= node.level:
                    stack.pop()

                stack[-1].children.append(node)
                stack.append(node)

            else:
                # Paragraph, list, table, or image
                node = ParsedNode(
                    heading=None,
                    level=stack[-1].level + 1,
                    body=block["body"],
                    node_type=block["type"],
                    order_index=block["order_index"],
                    metadata=block["metadata"]
                )
                stack[-1].children.append(node)

        return root
