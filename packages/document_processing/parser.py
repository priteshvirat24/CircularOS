"""PDF document parser using PyMuPDF.

Extracts text, headings, tables, and page-level content
with full coordinate preservation for citation mapping.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class ParsedPage:
    """Parsed content from a single document page."""
    page_number: int
    text_content: str
    word_count: int
    has_tables: bool = False
    has_images: bool = False
    tables: list[dict] = field(default_factory=list)
    blocks: list[dict] = field(default_factory=list)


@dataclass
class ParsedHeading:
    """Detected heading in a document."""
    text: str
    level: int
    page_number: int
    font_size: float
    is_bold: bool
    y_position: float


@dataclass
class ParsedDocument:
    """Complete parsed document."""
    page_count: int
    pages: list[ParsedPage]
    headings: list[ParsedHeading]
    full_text: str
    metadata: dict
    quality_score: float
    needs_ocr: bool


def parse_pdf(file_path: str) -> ParsedDocument:
    """Parse a PDF document using PyMuPDF.
    
    Extracts:
    - Page-level text with coordinates
    - Headings with font analysis
    - Tables
    - Document metadata
    - Quality assessment
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF (fitz) is required. Install with: pip install PyMuPDF")
    
    doc = fitz.open(file_path)
    pages: list[ParsedPage] = []
    headings: list[ParsedHeading] = []
    all_text_parts: list[str] = []
    total_text_blocks = 0
    empty_pages = 0
    
    # Analyze font sizes across document for heading detection
    font_sizes: list[float] = []
    
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict", sort=True)["blocks"]
        
        for block in blocks:
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("size"):
                            font_sizes.append(span["size"])
    
    # Determine heading thresholds
    if font_sizes:
        avg_font_size = sum(font_sizes) / len(font_sizes)
        heading_threshold = avg_font_size * 1.15  # 15% larger than average
    else:
        avg_font_size = 12
        heading_threshold = 14
    
    # Parse each page
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1
        
        # Extract text
        text = page.get_text("text")
        word_count = len(text.split()) if text.strip() else 0
        
        if not text.strip():
            empty_pages += 1
        
        # Extract structured blocks
        dict_content = page.get_text("dict", sort=True)
        blocks = dict_content.get("blocks", [])
        
        page_blocks = []
        for block in blocks:
            if block.get("type") == 0:  # Text block
                total_text_blocks += 1
                block_text = ""
                max_font_size = 0
                is_bold = False
                
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        span_text = span.get("text", "")
                        block_text += span_text
                        
                        font_size = span.get("size", 0)
                        if font_size > max_font_size:
                            max_font_size = font_size
                        
                        flags = span.get("flags", 0)
                        if flags & 2**4:  # Bold flag
                            is_bold = True
                
                block_text = block_text.strip()
                if not block_text:
                    continue
                
                page_blocks.append({
                    "text": block_text,
                    "bbox": block.get("bbox"),
                    "font_size": max_font_size,
                    "is_bold": is_bold,
                })
                
                # Detect headings
                if (max_font_size >= heading_threshold or is_bold) and len(block_text) < 200:
                    # Determine heading level based on font size
                    if max_font_size >= avg_font_size * 1.5:
                        level = 1
                    elif max_font_size >= avg_font_size * 1.3:
                        level = 2
                    elif max_font_size >= heading_threshold:
                        level = 3
                    else:
                        level = 4
                    
                    headings.append(ParsedHeading(
                        text=block_text,
                        level=level,
                        page_number=page_num,
                        font_size=max_font_size,
                        is_bold=is_bold,
                        y_position=block.get("bbox", [0, 0, 0, 0])[1],
                    ))
        
        # Check for tables
        tables = page.find_tables()
        has_tables = len(tables.tables) > 0 if tables else False
        table_data = []
        if has_tables:
            for table in tables.tables:
                try:
                    table_data.append({
                        "rows": len(table.cells) if hasattr(table, 'cells') else 0,
                        "header": table.header.names if hasattr(table, 'header') and table.header else [],
                        "data": table.extract()[:10],  # First 10 rows
                    })
                except Exception:
                    pass
        
        # Check for images
        has_images = len(page.get_images()) > 0
        
        pages.append(ParsedPage(
            page_number=page_num,
            text_content=text,
            word_count=word_count,
            has_tables=has_tables,
            has_images=has_images,
            tables=table_data,
            blocks=page_blocks,
        ))
        
        all_text_parts.append(text)
    
    # Document metadata
    metadata = doc.metadata or {}
    
    # Quality assessment
    total_pages = len(doc)
    if total_pages == 0:
        quality_score = 0.0
    else:
        text_coverage = 1.0 - (empty_pages / total_pages)
        avg_words = sum(p.word_count for p in pages) / total_pages if total_pages > 0 else 0
        word_score = min(avg_words / 100, 1.0)  # Expect ~100 words per page
        quality_score = round((text_coverage * 0.6 + word_score * 0.4), 3)
    
    needs_ocr = quality_score < 0.3 or empty_pages > total_pages * 0.5
    
    doc.close()
    
    full_text = "\n\n".join(all_text_parts)
    
    logger.info(
        "document_parsed",
        pages=total_pages,
        headings=len(headings),
        quality_score=quality_score,
        needs_ocr=needs_ocr,
        empty_pages=empty_pages,
    )
    
    return ParsedDocument(
        page_count=total_pages,
        pages=pages,
        headings=headings,
        full_text=full_text,
        metadata=metadata,
        quality_score=quality_score,
        needs_ocr=needs_ocr,
    )


def reconstruct_clause_hierarchy(
    headings: list[ParsedHeading],
    pages: list[ParsedPage],
) -> list[dict]:
    """Reconstruct clause hierarchy from headings and page content.
    
    Returns a list of clause dictionaries with:
    - clause_number
    - heading
    - text_content
    - level
    - page_start/page_end
    - children (recursive)
    """
    clauses = []
    
    # Pattern for clause numbers like "1.", "1.1", "1.1.1", "(a)", "(i)", etc.
    clause_number_pattern = re.compile(
        r'^(?:(\d+(?:\.\d+)*)\.|(\([a-z]\))|(\([ivxlcdm]+\))|([A-Z]\.)|(\d+\)))\s*'
    )
    
    if not headings:
        # If no headings detected, try to split by paragraph patterns
        for page in pages:
            text = page.text_content
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for i, para in enumerate(paragraphs):
                match = clause_number_pattern.match(para)
                clause_num = None
                if match:
                    clause_num = match.group(0).strip()
                
                clauses.append({
                    "clause_number": clause_num,
                    "heading": None,
                    "text_content": para,
                    "level": 0,
                    "page_start": page.page_number,
                    "page_end": page.page_number,
                    "order_index": len(clauses),
                })
        return clauses
    
    # Build clauses from headings
    for i, heading in enumerate(headings):
        # Find text content between this heading and the next
        next_heading = headings[i + 1] if i + 1 < len(headings) else None
        
        content_parts = []
        for page in pages:
            if page.page_number < heading.page_number:
                continue
            if next_heading and page.page_number > next_heading.page_number:
                break
            
            # Collect text blocks that fall between headings
            for block in page.blocks:
                block_text = block.get("text", "")
                if block_text == heading.text:
                    continue
                if next_heading and block_text == next_heading.text:
                    break
                content_parts.append(block_text)
        
        text_content = "\n".join(content_parts).strip()
        
        # Try to extract clause number
        match = clause_number_pattern.match(heading.text)
        clause_num = match.group(0).strip() if match else None
        
        page_end = heading.page_number
        if next_heading:
            page_end = next_heading.page_number
        
        clauses.append({
            "clause_number": clause_num,
            "heading": heading.text,
            "text_content": text_content or heading.text,
            "level": heading.level - 1,
            "page_start": heading.page_number,
            "page_end": page_end,
            "order_index": len(clauses),
        })
    
    return clauses
