import logging
import re
import unicodedata
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from rapidfuzz import fuzz

from app.models.node import Node
from app.schemas.parser import ParsedNode
from app.utils.hashing import calculate_content_hash

logger = logging.getLogger(__name__)

def normalize_for_similarity(text: Optional[str]) -> str:
    """
    Applies aggressive normalization to text before computing similarity scores:
    1. Converts to lowercase.
    2. NFKC unicode normalization.
    3. Trims page number footnotes/headers (e.g. 'Page 12', '12 of 24').
    4. Compresses duplicate whitespaces.
    5. Compresses repeated punctuation.
    """
    if not text:
        return ""
    
    # 1. Lowercase and Unicode Normalize
    text = text.lower()
    text = unicodedata.normalize("NFKC", text)
    
    # 2. Strip page number footnotes/indicators
    text = re.sub(r"\bpage\s+\d+(?:\s+of\s+\d+)?\b", "", text)
    text = re.sub(r"^\d+$", "", text)  # standalone numbers
    
    # 3. Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    
    # 4. Remove repeated punctuation (e.g., "!!!" to "!", "..." to ".")
    text = re.sub(r"([!?,.:;])\1+", r"\1", text)
    
    return text.strip()

def flatten_parsed_tree(node: ParsedNode, current_path: List[str] = None) -> List[Tuple[ParsedNode, str]]:
    """
    Recursively flattens the ParsedNode tree.
    Returns a list of Tuples (node, heading_path_string).
    """
    if current_path is None:
        current_path = []
        
    path_str = " > ".join(current_path)
    flat_list = [(node, path_str)]
    
    next_path = list(current_path)
    if node.heading and node.heading != "Document Root":
        next_path.append(node.heading)
        
    for child in node.children:
        flat_list.extend(flatten_parsed_tree(child, next_path))
        
    return flat_list

def get_v1_path(node: Node, nodes_by_id: Dict[int, Node]) -> str:
    """
    Walks up the parent chain of a stored Node to construct its heading path.
    """
    path_parts = []
    curr_parent_id = node.parent_id
    while curr_parent_id is not None:
        parent_node = nodes_by_id.get(curr_parent_id)
        if parent_node:
            if parent_node.heading:
                path_parts.append(parent_node.heading)
            curr_parent_id = parent_node.parent_id
        else:
            break
    path_parts.reverse()
    return " > ".join(path_parts)

def calculate_match_score(
    v2_node: ParsedNode, v2_path: str,
    v1_node: Node, v1_path: str
) -> float:
    """
    Computes similarity match score between v2 parsed node and stored v1 node.
    Score = (HeadingSim * 0.45) + (BodySim * 0.25) + (PathSim * 0.20) + (TypeSim * 0.10)
    """
    # 1. Heading similarity (S_h)
    v2_heading_norm = normalize_for_similarity(v2_node.heading)
    v1_heading_norm = normalize_for_similarity(v1_node.heading)
    if not v2_heading_norm and not v1_heading_norm:
        heading_sim = 100.0
    else:
        heading_sim = fuzz.token_sort_ratio(v2_heading_norm, v1_heading_norm)

    # 2. Body similarity (S_b)
    v2_body_norm = normalize_for_similarity(v2_node.body)
    v1_body_norm = normalize_for_similarity(v1_node.body)
    if not v2_body_norm and not v1_body_norm:
        body_sim = 100.0
    else:
        body_sim = fuzz.token_sort_ratio(v2_body_norm, v1_body_norm)

    # 3. Path similarity (S_p)
    v2_path_norm = normalize_for_similarity(v2_path)
    v1_path_norm = normalize_for_similarity(v1_path)
    if not v2_path_norm and not v1_path_norm:
        path_sim = 100.0
    else:
        path_sim = fuzz.token_sort_ratio(v2_path_norm, v1_path_norm)

    # 4. Type similarity (S_t) - Already guaranteed by pre-filter but set here for completeness
    type_sim = 100.0 if v2_node.node_type == v1_node.node_type else 0.0

    weighted_score = (
        (heading_sim * 0.45) +
        (body_sim * 0.25) +
        (path_sim * 0.20) +
        (type_sim * 0.10)
    )
    return weighted_score

def align_document_versions(
    db: Session,
    doc_id_v1: int,
    parsed_root_v2: ParsedNode,
    threshold: float = 70.0
) -> Dict[int, Tuple[str, float, str]]:
    """
    Compares the parsed nodes of version v2 with stored nodes of version v1.
    Uses pre-filtering and a greedy 1-to-1 matching strategy to identify alignments.
    
    Returns a dictionary mapping:
      v2_parsed_node.order_index -> (v1_node.logical_node_id, matched_score, matching_status)
    """
    logger.info(f"Aligning new document version against existing document ID {doc_id_v1}")

    # Fetch and index v1 nodes
    v1_nodes = db.query(Node).filter(Node.document_id == doc_id_v1).all()
    v1_nodes_by_id = {node.id: node for node in v1_nodes}
    
    # Flatten v2 tree (skipping the virtual root itself)
    v2_flat = flatten_parsed_tree(parsed_root_v2)
    v2_flat = [(node, path) for node, path in v2_flat if node.order_index > 0]

    # Precompute paths for v1 nodes
    v1_paths = {node.id: get_v1_path(node, v1_nodes_by_id) for node in v1_nodes}

    candidates: List[Tuple[float, ParsedNode, Node]] = []

    # Pre-filtered evaluation
    for v2_node, v2_path in v2_flat:
        for v1_node in v1_nodes:
            # Pre-filter 1: Must be compatible node_type
            if v2_node.node_type != v1_node.node_type:
                continue
            # Pre-filter 2: Headings must be at the same level
            if v2_node.node_type == "heading" and v2_node.level != v1_node.level:
                continue

            # Calculate score
            score = calculate_match_score(v2_node, v2_path, v1_node, v1_paths[v1_node.id])
            if score >= threshold:
                candidates.append((score, v2_node, v1_node))

    # Sort candidates by score descending
    candidates.sort(key=lambda x: x[0], reverse=True)

    matched_v2_indexes: Set[int] = set()
    matched_v1_ids: Set[int] = set()
    alignment_map: Dict[int, Tuple[str, float, str]] = {}

    # Greedy match allocation
    for score, v2_node, v1_node in candidates:
        if v2_node.order_index in matched_v2_indexes or v1_node.id in matched_v1_ids:
            continue

        matched_v2_indexes.add(v2_node.order_index)
        matched_v1_ids.add(v1_node.id)

        # Content hash change detection
        v2_hash = calculate_content_hash(v2_node.heading, v2_node.body)
        status = "MATCHED" if v2_hash == v1_node.content_hash else "MODIFIED"

        alignment_map[v2_node.order_index] = (v1_node.logical_node_id, float(score), status)
        logger.debug(
            f"Matched v2 index {v2_node.order_index} with logical_id {v1_node.logical_node_id} "
            f"(Score: {score:.1f}, Status: {status})"
        )

    return alignment_map
