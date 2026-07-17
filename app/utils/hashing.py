import hashlib
import re
from typing import Optional

def normalize_text(text: Optional[str]) -> str:
    """
    Normalizes a string by compressing all consecutive whitespace characters
    (spaces, tabs, newlines, carriage returns) into a single space and stripping edges.
    """
    if not text:
        return ""
    # Replace all whitespace sequences with a single space
    clean = re.sub(r"\s+", " ", text)
    return clean.strip()

def calculate_content_hash(heading: Optional[str], body: Optional[str]) -> str:
    """
    Generates a stable SHA-256 hash of heading and body contents.
    Normalizes whitespace before hashing to prevent minor layout differences
    from triggering false change detections.
    """
    norm_heading = normalize_text(heading)
    norm_body = normalize_text(body)
    
    # Concatenate using a unique delimiter
    combined_content = f"{norm_heading}||{norm_body}"
    
    # Calculate SHA256 digest
    hash_obj = hashlib.sha256(combined_content.encode("utf-8"))
    return hash_obj.hexdigest()
