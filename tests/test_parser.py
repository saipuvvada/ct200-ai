import pytest
from unittest.mock import MagicMock, patch
from app.parser.extractor import PDFParser

class MockTable:
    def __init__(self, bbox, grid_data):
        self.bbox = bbox
        self.grid_data = grid_data

    def extract(self):
        return self.grid_data


def test_table_to_markdown_formatting():
    """
    Verify table grid conversions to clean markdown.
    """
    parser = PDFParser()
    grid = [
        ["Header A", "Header B"],
        ["Val 1", "Val 2"],
        [None, "Val 4"]  # Test None handling
    ]
    markdown = parser._table_to_markdown(grid)
    expected = (
        "| Header A | Header B |\n"
        "| --- | --- |\n"
        "| Val 1 | Val 2 |\n"
        "|  | Val 4 |\n"
    )
    assert markdown == expected


def test_classify_text_line_headings_and_paragraphs():
    """
    Test line classification using font size, font weight, and list patterns.
    """
    parser = PDFParser()
    
    # Standard text should be paragraph
    typ, lvl = parser._classify_text_line("Just normal text.", 10.0, "Helvetica", 10.0)
    assert typ == "paragraph"
    assert lvl == 0

    # Header with larger size
    typ, lvl = parser._classify_text_line("Large Title", 15.0, "Helvetica", 10.0)
    assert typ == "heading"
    assert lvl == 1

    # Header with section numbering
    typ, lvl = parser._classify_text_line("1.2.3 Section Name", 10.0, "Helvetica", 10.0)
    assert typ == "heading"
    assert lvl == 3

    # Bullet list item
    typ, lvl = parser._classify_text_line("• List element here", 10.0, "Helvetica", 10.0)
    assert typ == "list"
    assert lvl == 0

    # Numbered list item
    typ, lvl = parser._classify_text_line("1. List item", 10.0, "Helvetica", 10.0)
    assert typ == "list"
    assert lvl == 0


def test_native_page_parsing_flow():
    """
    Mock pdfplumber page layout elements and verify full page parsing.
    """
    parser = PDFParser()
    
    # 1. Setup mock page
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Paragraph text on page."
    
    # Mock images
    mock_page.images = [
        {"x0": 10, "top": 120, "width": 50, "height": 50}
    ]

    # Mock tables
    mock_table = MockTable(bbox=(0, 200, 100, 250), grid_data=[["Col 1", "Col 2"], ["A", "B"]])
    mock_page.find_tables.return_value = [mock_table]

    # Mock words (incorporates font size metadata)
    mock_page.extract_words.return_value = [
        # Line 1: Heading
        {"text": "1.", "x0": 20, "top": 20, "fontname": "Arial-BoldMT", "size": 14.0},
        {"text": "Introduction", "x0": 35, "top": 20, "fontname": "Arial-BoldMT", "size": 14.0},
        # Line 2: Paragraph
        {"text": "This", "x0": 20, "top": 80, "fontname": "Arial", "size": 10.0},
        {"text": "is", "x0": 45, "top": 80, "fontname": "Arial", "size": 10.0},
        {"text": "body", "x0": 58, "top": 80, "fontname": "Arial", "size": 10.0},
        # Line 3: Table data (inside bbox, should be filtered out from paragraphs)
        {"text": "Col", "x0": 10, "top": 210, "fontname": "Arial", "size": 10.0},
        {"text": "1", "x0": 30, "top": 210, "fontname": "Arial", "size": 10.0},
    ]

    # 2. Run parser page routine
    blocks = parser._parse_page_native(mock_page, page_num=1, median_font_size=10.0)

    # 3. Assertions
    # Blocks should contain: Heading (top 20), Paragraph (top 80), Image (top 120), Table (top 200)
    # The word inside table bbox (top 210) must be ignored.
    assert len(blocks) == 4
    
    assert blocks[0]["type"] == "heading"
    assert blocks[0]["heading"] == "1. Introduction"
    
    assert blocks[1]["type"] == "paragraph"
    assert blocks[1]["body"] == "This is body"
    
    assert blocks[2]["type"] == "image"
    assert blocks[2]["metadata"]["width"] == 50.0

    assert blocks[3]["type"] == "table"
    assert "Col 1" in blocks[3]["body"]


@patch("app.parser.extractor.pytesseract")
def test_ocr_fallback_flow(mock_pytesseract):
    """
    Test OCR fallback scenario when native page extraction is blank/empty.
    """
    # Configure mock pytesseract
    mock_pytesseract.image_to_string.return_value = "1. OCR Section\n\nThis is OCR text."
    
    parser = PDFParser()
    
    # Setup page
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "   "  # Empty
    
    # Mock image rendering context
    mock_image_context = MagicMock()
    mock_image_context.original = MagicMock()
    mock_page.to_image.return_value = mock_image_context

    blocks = parser._parse_page_ocr(mock_page, page_num=1)
    
    # Verify blocks segmentations
    assert len(blocks) == 2
    assert blocks[0]["type"] == "heading"
    assert blocks[0]["heading"] == "1. OCR Section"
    assert blocks[1]["type"] == "paragraph"
    assert blocks[1]["body"] == "This is OCR text."
