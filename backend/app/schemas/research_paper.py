from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

MISSING_FIELD_TEXT = "Not explicitly stated in the paper."


FactType = Literal["explicit", "derived", "inferred", "missing"]


class SourceReference(BaseModel):
    """Exact document provenance attached to every grounded claim or numerical datum."""
    document_id: int
    page: int = Field(default=1, ge=1)
    section: Optional[str] = None
    chunk_id: Optional[int] = None
    figure_or_table: Optional[str] = None
    excerpt: str = ""
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class EvidenceItem(BaseModel):
    """Indexed verifiable evidence record consumed by the frontend Evidence Drawer."""
    id: str
    claim: str
    fact_type: FactType = "explicit"
    source: SourceReference
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class GroundedField(BaseModel):
    """Structured field value linked directly to supporting evidence IDs and sources."""
    value: str = MISSING_FIELD_TEXT
    fact_type: FactType = "missing"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: List[str] = Field(default_factory=list)
    sources: List[SourceReference] = Field(default_factory=list)


class PaperDetectionResult(BaseModel):
    is_research_paper: bool
    confidence: float = Field(ge=0.0, le=1.0)
    classification: Literal["research_paper", "borderline_technical", "non_research"]
    manual_override: Optional[Literal["research_paper", "non_research"]] = None
    signals: List[str] = Field(default_factory=list)
    missing_signals: List[str] = Field(default_factory=list)
    rationale: str = ""


class SectionNode(BaseModel):
    id: str
    title: str
    normalized_role: str = "other"
    level: int = Field(default=1, ge=1, le=4)
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    chunk_ids: List[int] = Field(default_factory=list)
    preview: str = ""
    children: List[SectionNode] = Field(default_factory=list)


SectionNode.model_rebuild()


class NumericalFinding(BaseModel):
    id: str
    metric_name: str
    original_value: str
    unit: Optional[str] = None
    experimental_context: str = ""
    fact_type: Literal["explicit", "derived"] = "explicit"
    source: SourceReference
    evidence_id: Optional[str] = None
    confidence: float = Field(default=0.88, ge=0.0, le=1.0)


class TableFigureRef(BaseModel):
    id: str
    label: str
    kind: Literal["table", "figure", "algorithm", "equation"]
    page: int = Field(default=1, ge=1)
    chunk_id: Optional[int] = None
    section: Optional[str] = None
    caption_or_context: str = ""
    visually_parsed: bool = False


class TablesAndFiguresSummary(BaseModel):
    items: List[TableFigureRef] = Field(default_factory=list)
    visual_parsing_limitation: str = (
        "Figures, charts, and complex multi-column tables are referenced from extracted document text/captions; "
        "raw chart pixels and visual table layouts are not visually parsed in Phase 1."
    )


class BasicInformationSection(BaseModel):
    title: GroundedField
    authors: GroundedField
    affiliation: GroundedField
    abstract: GroundedField
    keywords: GroundedField
    publication_info: GroundedField


class ResearchContextSection(BaseModel):
    research_domain: GroundedField
    problem_statement: GroundedField
    motivation: GroundedField
    research_objective: GroundedField
    research_questions: GroundedField
    hypothesis: GroundedField


class MethodologySection(BaseModel):
    methodology_type: GroundedField
    proposed_approach: GroundedField
    algorithms_models: GroundedField
    architecture: GroundedField
    framework_tools: GroundedField
    dataset: GroundedField
    dataset_size: GroundedField
    preprocessing: GroundedField
    experimental_setup: GroundedField


class EvaluationSection(BaseModel):
    evaluation_metrics: GroundedField
    baseline_methods: GroundedField
    experiments: GroundedField
    results: GroundedField
    numerical_findings: GroundedField
    comparisons: GroundedField


class ConclusionSection(BaseModel):
    main_conclusions: GroundedField
    limitations: GroundedField
    future_work: GroundedField


class AnalysisTimings(BaseModel):
    detection_ms: float = 0.0
    extraction_ms: float = 0.0
    llm_ms: float = 0.0
    total_ms: float = 0.0
    cache_retrieval_ms: float = 0.0


class ResearchAnalysisRequest(BaseModel):
    force_refresh: bool = False
    classification_override: Optional[Literal["auto", "research_paper", "non_research"]] = None
    skip_llm: bool = Field(
        default=False,
        description="Optional diagnostic flag to run fast deterministic extraction only.",
    )


class ResearchAnalysisResponse(BaseModel):
    document_id: int
    document_filename: str
    document_type: str
    is_handwritten: bool = False
    content_hash: str
    analysis_version: str
    status: Literal["generating", "completed", "failed"] = "completed"
    is_outdated: bool = False
    cached: bool = False
    analysis_mode: Literal["ollama_hybrid", "deterministic_fallback"] = "deterministic_fallback"
    pages_count: int = 1
    sections_count: int = 0
    evidence_count: int = 0
    evidence_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    generated_at: Optional[str] = None
    paper_detection: PaperDetectionResult
    basic_information: BasicInformationSection
    research_context: ResearchContextSection
    methodology: MethodologySection
    evaluation: EvaluationSection
    conclusion: ConclusionSection
    sections: List[SectionNode] = Field(default_factory=list)
    numerical_data: List[NumericalFinding] = Field(default_factory=list)
    tables_and_figures: TablesAndFiguresSummary = Field(default_factory=TablesAndFiguresSummary)
    evidence: Dict[str, EvidenceItem] = Field(default_factory=dict)
    timings: AnalysisTimings = Field(default_factory=AnalysisTimings)

