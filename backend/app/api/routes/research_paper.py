from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.research_paper import ResearchAnalysisRequest, ResearchAnalysisResponse
from app.services.research.paper_analysis_service import (
    analyze_research_paper,
    get_cached_research_analysis,
)

router = APIRouter(
    prefix="/documents",
    tags=["Research Paper Analyzer"],
)


@router.post("/{document_id}/research-analysis", response_model=ResearchAnalysisResponse)
def analyze_document_research_paper(
    document_id: int,
    payload: ResearchAnalysisRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Authenticate user, verify document ownership, check content hash cache,
    and run source-grounded structured Research Paper Analysis when needed.
    """
    req = payload or ResearchAnalysisRequest()
    return analyze_research_paper(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
        force_refresh=req.force_refresh,
        classification_override=req.classification_override,
        skip_llm=req.skip_llm,
    )


@router.get("/{document_id}/research-analysis", response_model=ResearchAnalysisResponse)
def get_document_research_analysis(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve cached source-grounded Research Paper Analysis for an owned document."""
    return get_cached_research_analysis(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )

