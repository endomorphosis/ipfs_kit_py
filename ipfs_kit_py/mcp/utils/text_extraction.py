"""
Text extraction utilities for MCP search functionality.

This module provides utilities to extract text from various file formats
to enable better search indexing and content discovery.
"""

import logging
import json
import re
from typing import Any, Dict, List, Optional, Union

# Configure logging
logger = logging.getLogger(__name__)

# File format constants
TEXT_CONTENT_TYPES = [
    "text/plain", "text/markdown", "text/csv", "text/html",
    "application/json", "application/xml", "application/javascript",
    "application/x-python", "application/x-typescript"
]

JSON_CONTENT_TYPES = [
    "application/json"
]

DOCUMENT_CONTENT_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.oasis.opendocument.text",
    "application/rtf"
]

IMAGE_CONTENT_TYPES = [
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "image/svg+xml", "image/tiff"
]

# Try importing optional dependencies for enhanced extraction
try:
    import pdftotext
    PDF_EXTRACTION_AVAILABLE = True
    logger.info("PDF text extraction available using pdftotext")
except ImportError:
    PDF_EXTRACTION_AVAILABLE = False
    logger.warning("PDF text extraction not available. Install with: pip install pdftotext")

try:
    import docx
    DOCX_EXTRACTION_AVAILABLE = True
    logger.info("DOCX text extraction available")
except ImportError:
    DOCX_EXTRACTION_AVAILABLE = False
    logger.warning("DOCX text extraction not available. Install with: pip install python-docx")

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
    logger.info("OCR text extraction available")
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("OCR text extraction not available. Install with: pip install pytesseract pillow")


def extract_text(
    data: bytes, 
    content_type: str,
    filename: Optional[str] = None,
    max_text_length: int = 32768  # 32KB default limit
) -> str:
    """
    Extract text from various file formats for search indexing.
    
    Args:
        data: Raw file data bytes
        content_type: MIME type of the content
        filename: Optional filename (used for extension-based format detection)
        max_text_length: Maximum text length to extract
        
    Returns:
        Extracted text
    """
    # Default result
    text = ""
    
    # Normalize content type to lowercase
    content_type = content_type.lower() if content_type else "application/octet-stream"
    
    try:
        # Plain text formats
        if any(ct in content_type for ct in TEXT_CONTENT_TYPES):
            text = data.decode('utf-8', errors='replace')
            
        # JSON special handling
        elif content_type in JSON_CONTENT_TYPES:
            try:
                json_data = json.loads(data.decode('utf-8', errors='replace'))
                text = extract_text_from_json(json_data)
            except json.JSONDecodeError:
                # Fallback to raw text if JSON parsing fails
                text = data.decode('utf-8', errors='replace')
                
        # PDF handling
        elif content_type == "application/pdf" and PDF_EXTRACTION_AVAILABLE:
            text = extract_text_from_pdf(data)
            
        # DOCX handling
        elif "officedocument.wordprocessingml.document" in content_type and DOCX_EXTRACTION_AVAILABLE:
            text = extract_text_from_docx(data)
            
        # Image OCR handling
        elif any(ct in content_type for ct in IMAGE_CONTENT_TYPES) and OCR_AVAILABLE:
            text = extract_text_from_image(data)
            
        # HTML special handling
        elif content_type == "text/html":
            text = extract_text_from_html(data.decode('utf-8', errors='replace'))
            
        # XML special handling
        elif content_type == "application/xml":
            text = extract_text_from_xml(data.decode('utf-8', errors='replace'))
            
        # If we couldn't extract text but content looks like text, try decoding
        elif not text and is_likely_text(data):
            text = data.decode('utf-8', errors='replace')
            
        # Limit text length if needed
        if max_text_length > 0 and len(text) > max_text_length:
            text = text[:max_text_length]
            
        return text
        
    except Exception as e:
        logger.error(f"Error extracting text from {content_type}: {e}")
        # Return empty string on error
        return ""


def extract_text_from_json(json_data: Any, max_depth: int = 3) -> str:
    """
    Extract text from JSON data, recursively processing structures.
    
    Args:
        json_data: Parsed JSON data
        max_depth: Maximum recursion depth
        
    Returns:
        Extracted text
    """
    if max_depth <= 0:
        return ""
    
    result = []
    
    if isinstance(json_data, dict):
        for key, value in json_data.items():
            # Add the key name
            result.append(str(key))
            
            # Process value based on type
            if isinstance(value, (dict, list)):
                result.append(extract_text_from_json(value, max_depth - 1))
            elif isinstance(value, (str, int, float, bool)):
                result.append(str(value))
                
    elif isinstance(json_data, list):
        for item in json_data:
            if isinstance(item, (dict, list)):
                result.append(extract_text_from_json(item, max_depth - 1))
            elif isinstance(item, (str, int, float, bool)):
                result.append(str(item))
                
    elif isinstance(json_data, (str, int, float, bool)):
        result.append(str(json_data))
    
    return " ".join(result)


def extract_text_from_pdf(data: bytes) -> str:
    """
    Extract text from PDF data.
    
    Args:
        data: PDF file data
        
    Returns:
        Extracted text
    """
    if not PDF_EXTRACTION_AVAILABLE:
        return ""
    
    try:
        import io
        pdf_file = io.BytesIO(data)
        
        # Extract text from each page
        with pdftotext.PDF(pdf_file) as pdf:
            return "\n\n".join(pdf)
            
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return ""


def extract_text_from_docx(data: bytes) -> str:
    """
    Extract text from DOCX data.
    
    Args:
        data: DOCX file data
        
    Returns:
        Extracted text
    """
    if not DOCX_EXTRACTION_AVAILABLE:
        return ""
    
    try:
        import io
        docx_file = io.BytesIO(data)
        
        # Load the document
        doc = docx.Document(docx_file)
        
        # Extract text from paragraphs
        text = []
        for para in doc.paragraphs:
            text.append(para.text)
            
        return "\n".join(text)
        
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {e}")
        return ""


def extract_text_from_image(data: bytes) -> str:
    """
    Extract text from image data using OCR.
    
    Args:
        data: Image file data
        
    Returns:
        Extracted text
    """
    if not OCR_AVAILABLE:
        return ""
    
    try:
        import io
        image_file = io.BytesIO(data)
        
        # Open the image
        img = Image.open(image_file)
        
        # Perform OCR
        text = pytesseract.image_to_string(img)
        
        return text
        
    except Exception as e:
        logger.error(f"Error extracting text from image: {e}")
        return ""


def extract_text_from_html(html: str) -> str:
    """
    Extract text from HTML, removing tags.
    
    Args:
        html: HTML content
        
    Returns:
        Extracted text
    """
    try:
        # Simple tag removal - a full HTML parser would be more accurate but heavier
        text = re.sub(r'<style.*?>.*?</style>', ' ', html, flags=re.DOTALL)
        text = re.sub(r'<script.*?>.*?</script>', ' ', text, flags=re.DOTALL)
        text = re.sub(r'<!--.*?-->', ' ', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]*>', ' ', text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
        
    except Exception as e:
        logger.error(f"Error extracting text from HTML: {e}")
        return html  # Return original if parsing fails


def extract_text_from_xml(xml: str) -> str:
    """
    Extract text from XML, removing tags.
    
    Args:
        xml: XML content
        
    Returns:
        Extracted text
    """
    try:
        # Simple tag removal
        text = re.sub(r'<[^>]*>', ' ', xml)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
        
    except Exception as e:
        logger.error(f"Error extracting text from XML: {e}")
        return xml  # Return original if parsing fails


def is_likely_text(data: bytes, threshold: float = 0.8) -> bool:
    """
    Check if data is likely to be text based on byte patterns.
    
    Args:
        data: Binary data to check
        threshold: Minimum ratio of text characters to consider as text
        
    Returns:
        True if data is likely text, False otherwise
    """
    # Sample the first 1KB of data
    sample = data[:1024]
    if not sample:
        return False
    
    # Count printable ASCII and common UTF-8 characters
    text_chars = 0
    for byte in sample:
        # ASCII printable chars plus newline/tab
        if (32 <= byte <= 126) or byte in (9, 10, 13):
            text_chars += 1
    
    # Calculate ratio of text characters
    ratio = text_chars / len(sample)
    
    return ratio >= threshold