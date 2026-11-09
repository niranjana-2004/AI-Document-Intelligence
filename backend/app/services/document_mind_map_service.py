import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_mind_map import DocumentMindMap
from app.models.handwritten_analysis import HandwrittenConcept
from app.models.handwritten_page import HandwrittenPage
from app.services.embedding_services import generate_embedding
from app.services.similarity_service import cosine_similarity
from app.services.handwriting.handwritten_source_service import get_document_transcription_source
from app.services.handwriting.handwritten_concept_service import (
    generate_handwritten_concepts,
    list_handwritten_concepts
)
from app.services.handwriting.ollama_client import query_ollama, extract_json_from_text, OllamaError
from app.services.text_processing_service import clean_text, detect_chunk_category
from app.schemas.document_mind_map import MindMapNode, SourceEvidence, MindMapResponse

logger = logging.getLogger(__name__)

# Valid node types and relationship labels
VALID_NODE_TYPES = {"root", "topic", "subtopic", "concept", "definition", "process", "example"}
VALID_RELATIONSHIPS = {"contains", "depends_on", "causes", "related_to", "example_of", "part_of", "leads_to"}


def compute_text_hash(text: str) -> str:
    """Compute deterministic SHA-256 hash of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def normalize_concept_label(label: str) -> str:
    """
    Normalize concept string: strip numbering, bullet markers, excess whitespace,
    and retain title casing while keeping established acronyms like TCP, DNS, HTTP, TLS.
    """
    cleaned = re.sub(r'^(?:\d+[\.\)]|[-*•–—])\s*', '', label.strip())
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def count_tree_nodes(node: MindMapNode) -> int:
    """Recursively calculate total node count in the mind map."""
    total = 1
    for child in node.children:
        total += count_tree_nodes(child)
    return total


def extract_standard_concepts_fallback(
    text: str,
    chunks: List[DocumentChunk]
) -> List[Dict[str, Any]]:
    """
    Deterministic rule-based concept extraction from chunks and headings
    when Ollama is offline or for short documents.
    """
    extracted_concepts: List[Dict[str, Any]] = []
    seen_names: Set[str] = set()

    # 1. Inspect chunks with headings or structured categories
    for chunk in chunks:
        content = (chunk.content or "").strip()
        page = chunk.page_number or 1

        # Look for markdown headings (# Heading or ## Heading)
        heading_matches = re.findall(r'^(?:#{1,3})\s+([^\n]+)', content, flags=re.MULTILINE)
        for h in heading_matches:
            name = normalize_concept_label(h)
            if name and len(name) > 2 and name.lower() not in seen_names:
                seen_names.add(name.lower())
                # Extract first sentence under heading as excerpt/definition
                lines = content.split('\n')
                desc = f"Key section covering {name}."
                for l in lines:
                    if l.strip() and not l.startswith('#') and len(l.strip()) > 15:
                        desc = l.strip()[:160] + ("..." if len(l.strip()) > 160 else "")
                        break
                extracted_concepts.append({
                    "name": name,
                    "definition": desc,
                    "excerpt": desc,
                    "page_number": page,
                    "related_concepts": []
                })

        # Look for definition patterns: "X is defined as Y" or "X refers to Y" or "X: Y"
        def_patterns = [
            r'([A-Z][A-Za-z0-9\s\-]{2,30})\s+(?:is defined as|refers to|represents)\s+([^\.\n]+(?:\.|\n))',
            r'([A-Z][A-Za-z0-9\s\-]{2,25}):\s+([A-Z][^\.\n]+(?:\.|\n))'
        ]
        for pat in def_patterns:
            matches = re.findall(pat, content)
            for m_name, m_def in matches:
                name = normalize_concept_label(m_name)
                if name and len(name) > 2 and name.lower() not in seen_names:
                    seen_names.add(name.lower())
                    clean_def = m_def.strip()
                    extracted_concepts.append({
                        "name": name,
                        "definition": clean_def[:200],
                        "excerpt": f"{name}: {clean_def[:140]}",
                        "page_number": page,
                        "related_concepts": []
                    })

    # If few concepts detected, extract strong paragraph topic sentences
    if len(extracted_concepts) < 4 and text:
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if len(p.strip()) > 30]
        for idx, p in enumerate(paragraphs[:10]):
            first_sentence = re.split(r'(?<=[.!?])\s+', p)[0].strip()
            # Pick first 3-5 words as title
            words = first_sentence.split()
            title = " ".join(words[:4]).strip(" ,.-:")
            if title and title.lower() not in seen_names:
                seen_names.add(title.lower())
                extracted_concepts.append({
                    "name": title,
                    "definition": first_sentence[:200],
                    "excerpt": p[:150],
                    "page_number": 1,
                    "related_concepts": []
                })

    return extracted_concepts


def get_document_text_and_hash(
    document: Document,
    db: Session,
    user_id: int
) -> Tuple[str, str]:
    """Retrieve full text and SHA-256 hash without performing concept extraction."""
    if document.is_handwritten:
        source_data = get_document_transcription_source(document.id, db, user_id=user_id)
        if not source_data["has_transcription"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Handwritten document '{document.filename}' has no transcription yet. Please transcribe it first."
            )
        return source_data["full_text"], source_data["hash"]

    # Standard Document (PDF / DOCX / TXT)
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )
    full_text = (document.extracted_text or "").strip()
    if not full_text and chunks:
        full_text = "\n\n".join(c.content for c in chunks if c.content).strip()

    if not full_text or len(full_text) < 15:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough structured content was found to generate a meaningful mind map."
        )

    content_hash = compute_text_hash(full_text)
    return full_text, content_hash


def get_or_extract_document_concepts(
    document: Document,
    db: Session,
    user_id: int,
    full_text: Optional[str] = None,
    content_hash: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], str, str]:
    """
    Retrieve or extract concepts for a document.
    Reuses existing HandwrittenConcept records or handwritten_concept_service if available.
    Returns: (concepts_list, full_text, content_hash)
    """
    if full_text is None or content_hash is None:
        full_text, content_hash = get_document_text_and_hash(document, db, user_id)

    if document.is_handwritten:
        # Check existing HandwrittenConcept records
        existing_concepts = (
            db.query(HandwrittenConcept)
            .filter(HandwrittenConcept.document_id == document.id)
            .all()
        )
        if existing_concepts:
            concepts = [
                {
                    "name": c.name,
                    "definition": c.definition,
                    "excerpt": c.excerpt or c.definition,
                    "page_number": c.page_number or 1,
                    "related_concepts": c.related_concepts or []
                }
                for c in existing_concepts
            ]
            return concepts, full_text, content_hash

        # Generate using existing concept service
        try:
            concept_res = generate_handwritten_concepts(document.id, user_id, db)
            concepts = concept_res.get("concepts", [])
            return concepts, full_text, content_hash
        except Exception as e:
            logger.warning(f"Handwritten concept extraction failed: {e}. Using fallback...")
            # Fallback extraction from transcription pages
            chunks = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == document.id)
                .all()
            )
            concepts = extract_standard_concepts_fallback(full_text, chunks)
            return concepts, full_text, content_hash

    # Standard Document (PDF / DOCX / TXT)
    # First check if any concepts exist in DB for this document
    existing_concepts = (
        db.query(HandwrittenConcept)
        .filter(HandwrittenConcept.document_id == document.id)
        .all()
    )
    if existing_concepts:
        concepts = [
            {
                "name": c.name,
                "definition": c.definition,
                "excerpt": c.excerpt or c.definition,
                "page_number": c.page_number or 1,
                "related_concepts": c.related_concepts or []
            }
            for c in existing_concepts
        ]
        return concepts, full_text, content_hash

    # Extract concepts using Ollama with strict prompt
    sample_text = full_text[:4000]
    prompt = f"""Extract 5 to 12 core academic concepts or key technical terms from this document.

DOCUMENT CONTENT:
----------------
{sample_text}
----------------

SCHEMA REQUIREMENT:
Return a JSON object containing an array named "concepts":
{{
  "concepts": [
    {{
      "name": "Concept Name",
      "definition": "Clear concise definition from text",
      "excerpt": "Direct supporting sentence from the text",
      "page_number": 1,
      "related_concepts": ["Term A", "Term B"]
    }}
  ]
}}
"""
    try:
        raw_res = query_ollama(
            prompt=prompt,
            system_prompt="You are an academic concept extraction engine. Output valid JSON only adhering strictly to schema.",
            temperature=0.1
        )
        parsed = extract_json_from_text(raw_res)
        concepts = parsed.get("concepts", []) if isinstance(parsed, dict) else []
        if concepts:
            return concepts, full_text, content_hash
    except Exception as e:
        logger.info(f"Ollama concept extraction for document #{document.id} failed or unavailable: {e}")

    # Fallback rule-based concept extraction
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .all()
    )
    concepts = extract_standard_concepts_fallback(full_text, chunks)
    return concepts, full_text, content_hash


def consolidate_concepts(concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Consolidate duplicate concepts or casing variants (e.g. TCP vs tcp),
    merging their page numbers and excerpts.
    """
    consolidated: Dict[str, Dict[str, Any]] = {}

    for c in concepts:
        raw_name = str(c.get("name") or "").strip()
        if not raw_name:
            continue
        norm_key = re.sub(r'[^\w\s]', '', raw_name.lower()).strip()
        if not norm_key:
            continue

        if norm_key in consolidated:
            existing = consolidated[norm_key]
            # If current name has better casing (e.g. uppercase acronym), use it
            if raw_name.isupper() and not existing["name"].isupper():
                existing["name"] = raw_name
            # Merge page numbers
            page = c.get("page_number", 1)
            if page and page not in existing.get("all_pages", []):
                existing.setdefault("all_pages", [existing.get("page_number", 1)]).append(page)
            # Retain definition if existing is empty
            if not existing.get("definition") and c.get("definition"):
                existing["definition"] = c.get("definition")
        else:
            consolidated[norm_key] = {
                "name": raw_name,
                "definition": str(c.get("definition") or "").strip(),
                "excerpt": str(c.get("excerpt") or c.get("definition") or "").strip(),
                "page_number": int(c.get("page_number") or 1),
                "all_pages": [int(c.get("page_number") or 1)],
                "related_concepts": c.get("related_concepts") or []
            }

    return list(consolidated.values())


def generate_deterministic_mind_map(
    document: Document,
    concepts: List[Dict[str, Any]],
    full_text: str
) -> MindMapNode:
    """
    Build a structured, hierarchical mind map deterministically without LLM dependency.
    Groups concepts by document themes or page clusters and assigns proper node types and relationships.
    """
    doc_title = document.filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').title()
    root_id = "root"

    # If no concepts extracted, extract fallback from text
    if not concepts:
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', full_text) if len(p.strip()) > 30]
        if paragraphs:
            concepts = [
                {
                    "name": f"Section {i+1}",
                    "definition": p[:140],
                    "excerpt": p[:140],
                    "page_number": 1
                }
                for i, p in enumerate(paragraphs[:6])
            ]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not enough structured content was found to generate a meaningful mind map."
            )

    # Clean and consolidate concepts
    unique_concepts = consolidate_concepts(concepts)

    # Group concepts into 2-5 major topics based on page numbers or keywords
    topic_groups: Dict[str, List[Dict[str, Any]]] = {}

    for c in unique_concepts:
        name = c["name"]
        page = c["page_number"]
        name_lower = name.lower()

        # Grouping heuristics based on technical domains
        if any(w in name_lower for w in ["handshake", "connection", "syn", "ack", "tcb", "port", "socket"]):
            group = "Connection Management"
        elif any(w in name_lower for w in ["security", "flood", "attack", "rst", "spoof", "hijack", "firewall"]):
            group = "Security & Vulnerabilities"
        elif any(w in name_lower for w in ["dns", "http", "ip", "routing", "protocol", "address", "arp"]):
            group = "Protocols & Addressing"
        elif any(w in name_lower for w in ["css", "html", "style", "layout", "presentation", "syntax"]):
            group = "Web Presentation & Styles"
        elif any(w in name_lower for w in ["function", "loop", "variable", "syntax", "python", "datatype"]):
            group = "Core Language Syntax"
        else:
            # Group by page cluster
            if page <= 2:
                group = "Foundational Concepts"
            elif page <= 4:
                group = "Core Architecture & Processes"
            else:
                group = "Advanced Applications"

        topic_groups.setdefault(group, []).append(c)

    # Ensure 2 to 6 topics
    topic_children: List[MindMapNode] = []
    topic_idx = 1

    for group_name, group_concepts in topic_groups.items():
        sub_nodes: List[MindMapNode] = []
        for c_idx, c in enumerate(group_concepts[:6]):
            node_id = f"node-{topic_idx}-{c_idx+1}"
            label = c["name"]

            # Determine appropriate node type
            desc = c.get("definition") or c.get("excerpt") or ""
            desc_lower = desc.lower()
            if any(w in desc_lower for w in ["step", "sequence", "process", "procedure", "algorithm", "cycle"]):
                n_type = "process"
                rel = "leads_to" if c_idx > 0 else "part_of"
            elif any(w in desc_lower for w in ["example", "such as", "for instance", "e.g."]):
                n_type = "example"
                rel = "example_of"
            elif any(w in desc_lower for w in ["defined as", "refers to", "denotes"]):
                n_type = "definition"
                rel = "part_of"
            else:
                n_type = "concept"
                rel = "contains" if c_idx == 0 else "depends_on"

            sources = [
                SourceEvidence(
                    page=c.get("page_number", 1),
                    chunk_id=f"doc_{document.id}_p{c.get('page_number', 1)}",
                    excerpt=c.get("excerpt") or c.get("definition") or label,
                    confidence=0.92
                )
            ]

            sub_nodes.append(
                MindMapNode(
                    id=node_id,
                    label=label,
                    type=n_type,
                    description=desc,
                    relationship=rel,
                    children=[],
                    sources=sources
                )
            )

        # Topic Node
        topic_id = f"topic-{topic_idx}"
        topic_excerpt = sub_nodes[0].sources[0].excerpt if sub_nodes and sub_nodes[0].sources else f"Core topic: {group_name}"
        topic_page = sub_nodes[0].sources[0].page if sub_nodes and sub_nodes[0].sources else 1

        topic_children.append(
            MindMapNode(
                id=topic_id,
                label=group_name,
                type="topic",
                description=f"Core thematic area encompassing {len(sub_nodes)} concepts.",
                relationship="contains",
                children=sub_nodes,
                sources=[
                    SourceEvidence(
                        page=topic_page,
                        chunk_id=f"doc_{document.id}_topic_{topic_idx}",
                        excerpt=topic_excerpt,
                        confidence=0.95
                    )
                ]
            )
        )
        topic_idx += 1

    root_node = MindMapNode(
        id=root_id,
        label=doc_title,
        type="root",
        description=f"Central knowledge structure for {document.filename}.",
        relationship=None,
        children=topic_children,
        sources=[
            SourceEvidence(
                page=1,
                chunk_id=f"doc_{document.id}_root",
                excerpt=full_text[:140],
                confidence=1.0
            )
        ]
    )

    return root_node


def generate_llm_mind_map(
    document: Document,
    concepts: List[Dict[str, Any]],
    full_text: str
) -> Optional[MindMapNode]:
    """
    Synthesize an intelligent, grounded mind map hierarchy using local Ollama Llama 3.2.
    Adheres strictly to the MindMapNode schema.
    """
    doc_title = document.filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').title()
    unique_concepts = consolidate_concepts(concepts)

    if not unique_concepts:
        return None

    # Format structured concept evidence
    concepts_formatted = []
    for idx, c in enumerate(unique_concepts[:18]):
        concepts_formatted.append(
            f"Concept {idx+1}: {c['name']} (Page {c.get('page_number', 1)})\n"
            f"  Definition: {c.get('definition', '')}\n"
            f"  Excerpt: \"{c.get('excerpt', '')}\""
        )
    evidence_block = "\n".join(concepts_formatted)

    system_prompt = (
        "You are Cognidocs AI Knowledge Architect. "
        "Transform the provided document concepts and excerpts into a structured hierarchical Mind Map. "
        "STRICT REQUIREMENTS:\n"
        "1. Exactly ONE Root node representing the overall document topic.\n"
        "2. 3 to 6 Major Topic nodes representing high-level themes.\n"
        "3. 2 to 5 Subtopics, Concepts, Definitions, or Processes under each major topic.\n"
        "4. Valid node types: 'root', 'topic', 'subtopic', 'concept', 'definition', 'process', 'example'.\n"
        "5. Valid relationships to parent: 'contains', 'depends_on', 'causes', 'related_to', 'example_of', 'part_of', 'leads_to'.\n"
        "6. Every node must cite exact page numbers and excerpts strictly from the provided EVIDENCE. NEVER invent page numbers or quotes.\n"
        "7. Return EXCLUSIVELY valid JSON conforming to the schema."
    )

    prompt = f"""DOCUMENT TITLE: {doc_title}

DOCUMENT EVIDENCE:
----------------
{evidence_block}
----------------

JSON SCHEMA REQUIREMENT:
{{
  "root": {{
    "id": "root",
    "label": "{doc_title}",
    "type": "root",
    "description": "High level overview of {doc_title}",
    "relationship": null,
    "sources": [
      {{ "page": 1, "excerpt": "Supporting quote...", "confidence": 0.95 }}
    ],
    "children": [
      {{
        "id": "topic-1",
        "label": "Major Topic Name",
        "type": "topic",
        "description": "Topic explanation",
        "relationship": "contains",
        "sources": [
          {{ "page": 1, "excerpt": "Supporting quote from evidence...", "confidence": 0.95 }}
        ],
        "children": [
          {{
            "id": "concept-1-1",
            "label": "Subtopic or Concept Name",
            "type": "concept",
            "description": "Clear grounded description",
            "relationship": "part_of",
            "sources": [
              {{ "page": 1, "excerpt": "Supporting quote from evidence...", "confidence": 0.90 }}
            ],
            "children": []
          }}
        ]
      }}
    ]
  }}
}}
"""

    try:
        raw_output = query_ollama(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.15
        )
        data = extract_json_from_text(raw_output)
        if not isinstance(data, dict):
            logger.warning("Ollama did not return a JSON dictionary for mind map.")
            return None

        root_dict = data.get("root") if "root" in data else data

        # Validate recursively via Pydantic
        root_node = MindMapNode.model_validate(root_dict)
        # Ensure root node has at least 2 children
        if len(root_node.children) >= 2:
            return root_node
        else:
            logger.info("LLM generated fewer than 2 topics, falling back to deterministic.")
            return None

    except Exception as e:
        logger.warning(f"Ollama Mind Map generation failed or invalid JSON: {e}")
        return None


def generate_document_mind_map_service(
    document_id: int,
    user_id: int,
    db: Session,
    force_refresh: bool = False
) -> MindMapResponse:
    """
    Complete end-to-end Mind Map service:
    1. Validates document existence and authenticated user ownership.
    2. Checks content SHA-256 hash against SQLite cache (instant retrieval if clean).
    3. Extracts and consolidates canonical concepts.
    4. Generates hierarchical graph via Ollama Llama 3.2 (with deterministic semantic fallback).
    5. Caches and persists result into 'document_mind_maps'.
    """
    # 1. Ownership & existence check
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id)
        .first()
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document #{document_id} not found or you do not have permission to access it."
        )

    # 2. Fast text & content hash retrieval (instant, zero LLM overhead)
    full_text, content_hash = get_document_text_and_hash(document, db, user_id)

    # 3. Check persistent cache BEFORE concept extraction
    if not force_refresh and content_hash:
        cached_record = (
            db.query(DocumentMindMap)
            .filter(
                DocumentMindMap.user_id == user_id,
                DocumentMindMap.document_id == document_id,
                DocumentMindMap.content_hash == content_hash
            )
            .first()
        )
        if cached_record and cached_record.mind_map_json:
            try:
                cached_data = cached_record.mind_map_json
                cached_data["cached"] = True
                return MindMapResponse.model_validate(cached_data)
            except Exception as e:
                logger.warning(f"Failed to load cached mind map JSON: {e}")

    # 4. Cache miss or force_refresh: extract concepts
    concepts, full_text, content_hash = get_or_extract_document_concepts(
        document, db, user_id, full_text=full_text, content_hash=content_hash
    )

    # 5. Generate hierarchy
    generation_method = "ollama_llama3_2"
    root_node = generate_llm_mind_map(document, concepts, full_text)

    if not root_node:
        logger.info(f"Using deterministic fallback for document #{document_id} mind map.")
        generation_method = "deterministic_semantic_fallback"
        root_node = generate_deterministic_mind_map(document, concepts, full_text)

    # 5. Build response
    node_count = count_tree_nodes(root_node)
    doc_title = document.filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').title()

    response = MindMapResponse(
        document_id=document.id,
        document_title=doc_title,
        is_handwritten=bool(document.is_handwritten),
        content_hash=content_hash,
        node_count=node_count,
        root=root_node,
        cached=False,
        generation_method=generation_method
    )

    # 6. Save/update cache in SQLite
    response_dict = response.model_dump()
    existing_entry = (
        db.query(DocumentMindMap)
        .filter(
            DocumentMindMap.user_id == user_id,
            DocumentMindMap.document_id == document_id
        )
        .first()
    )

    if existing_entry:
        existing_entry.content_hash = content_hash
        existing_entry.mind_map_json = response_dict
    else:
        new_entry = DocumentMindMap(
            user_id=user_id,
            document_id=document_id,
            content_hash=content_hash,
            mind_map_json=response_dict
        )
        db.add(new_entry)

    db.commit()

    return response
