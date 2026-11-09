"""
Cognidocs Multi-Document Chat Frontend Verification Suite
Phase 4: Document Selector + Cross-Document Chat UX

Validates frontend components, stylesheets, integration in AskAI.jsx,
production build artifacts, and live API compatibility.
"""

import os
import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
SRC_DIR = FRONTEND_DIR / "src"
COMPONENTS_DIR = SRC_DIR / "components"
PAGES_DIR = SRC_DIR / "pages"
STYLES_DIR = SRC_DIR / "styles"
DIST_DIR = FRONTEND_DIR / "dist"

def test_multi_document_selector_component():
    print("\n--- TEST 1: MultiDocumentSelector Component Validation ---")
    file_path = COMPONENTS_DIR / "MultiDocumentSelector.jsx"
    assert file_path.exists(), f"Missing component: {file_path}"
    content = file_path.read_text(encoding="utf-8")

    # Check search input & clear button
    assert "selector-search-box" in content, "Missing search box container"
    assert "selector-search-input" in content, "Missing search input element"
    assert "selector-search-clear" in content, "Missing clear search button"

    # Check filter tabs
    assert "selector-filter-pills" in content, "Missing filter pills container"
    assert "typeFilter === 'all'" in content, "Missing all types filter"
    assert "typeFilter === 'printed'" in content, "Missing printed filter"
    assert "typeFilter === 'handwritten'" in content, "Missing handwritten filter"

    # Check selected tray & chips
    assert "selector-selected-tray" in content, "Missing selected tray container"
    assert "selected-chip" in content, "Missing selected chip element"
    assert "selected-chip-remove" in content, "Missing chip remove button"

    # Check document grid & cards
    assert "selector-docs-grid" in content, "Missing docs grid"
    assert "selector-doc-card" in content, "Missing doc card element"
    assert "doc-card-checkbox" in content, "Missing custom checkbox"
    assert "badge-hw" in content, "Missing handwritten badge"
    assert "badge-format" in content, "Missing format badge"

    # Check footer actions
    assert "selector-footer" in content, "Missing selector footer"
    assert "onSelectAll" in content, "Missing onSelectAll handler"
    assert "onClear" in content, "Missing onClear handler"
    assert "Done ✓" in content, "Missing Done button"

    print("PASS: MultiDocumentSelector component has all required controls, badges, and filters!")

def test_multi_document_css():
    print("\n--- TEST 2: Multi-Document CSS Stylesheet Validation ---")
    file_path = STYLES_DIR / "multi-document-chat.css"
    assert file_path.exists(), f"Missing stylesheet: {file_path}"
    content = file_path.read_text(encoding="utf-8")

    # Check key classes
    required_classes = [
        ".active-scope-banner",
        ".multi-doc-selector-panel",
        ".selector-search-box",
        ".selector-filter-pills",
        ".filter-pill",
        ".selector-selected-tray",
        ".selected-chip",
        ".selector-docs-grid",
        ".selector-doc-card",
        ".badge-hw",
        ".badge-format",
        ".selector-footer",
        ".multi-doc-sources-summary",
        ".source-nav-link",
        ".followup-questions-container",
        ".followup-chip",
    ]
    for cls in required_classes:
        assert cls in content, f"Missing CSS class: {cls}"

    print(f"PASS: multi-document-chat.css contains all {len(required_classes)} required style rules!")

def test_ask_ai_integration():
    print("\n--- TEST 3: AskAI.jsx Integration Validation ---")
    file_path = PAGES_DIR / "AskAI.jsx"
    assert file_path.exists(), f"Missing AskAI page: {file_path}"
    content = file_path.read_text(encoding="utf-8")

    # Check component imports
    assert "MultiDocumentSelector" in content, "AskAI must import MultiDocumentSelector"
    assert "multi-document-chat.css" in content, "AskAI must import multi-document-chat.css"

    # Check active scope banner
    assert "active-scope-banner" in content, "Missing active scope banner"
    assert "selectedDocNames" in content, "Missing selectedDocNames helper"

    # Check MultiDocumentSelector mounting
    assert "<MultiDocumentSelector" in content, "Missing MultiDocumentSelector JSX tag"
    assert "onToggleDoc={handleToggleDoc}" in content, "Missing onToggleDoc prop binding"

    # Check dynamic loading progress states
    assert "LOADING_STEPS" in content, "Missing LOADING_STEPS array"
    assert "currentLoadingStatus" in content, "Missing currentLoadingStatus state"

    # Check follow-up questions chips
    assert "followup-questions-container" in content, "Missing follow-up questions container"
    assert "followup-chip" in content, "Missing follow-up chip element"
    assert "handleAskAI(fq)" in content, "Clicking chip must invoke handleAskAI"

    # Check cross-document evidence summary
    assert "multi-doc-sources-summary" in content, "Missing cross-document evidence summary"
    assert "Cross-Document Evidence:" in content, "Missing evidence summary text"

    # Check source card badges and direct navigation
    assert "source-type-pill" in content, "Missing source type pill"
    assert "HANDWRITTEN" in content, "Missing HANDWRITTEN badge"
    assert "source-nav-link" in content, "Missing direct source nav links"
    assert "/handwritten/" in content, "Missing navigation link to HandwrittenStudio"
    assert "/documents" in content, "Missing navigation link to Documents"

    # Check citation tooltip
    assert "sourceTypeTag" in content, "Missing source type in citation tooltip"

    print("PASS: AskAI.jsx successfully integrates all Phase 4 features!")

def test_production_build_artifacts():
    print("\n--- TEST 4: Production Build Artifacts Validation ---")
    assert DIST_DIR.exists(), f"Missing dist folder: {DIST_DIR}"
    index_html = DIST_DIR / "index.html"
    assert index_html.exists(), "Missing dist/index.html"

    assets_dir = DIST_DIR / "assets"
    assert assets_dir.exists(), "Missing dist/assets"

    js_files = list(assets_dir.glob("*.js"))
    css_files = list(assets_dir.glob("*.css"))
    assert len(js_files) > 0, "No bundled JS files found"
    assert len(css_files) > 0, "No bundled CSS files found"

    print(f"PASS: Production build verified! Bundled JS ({js_files[0].name}, {js_files[0].stat().st_size} bytes), CSS ({css_files[0].name}, {css_files[0].stat().st_size} bytes)")

def test_live_api_response_contract():
    print("\n--- TEST 5: Live API Contract & Scope Validation ---")
    sys.path.insert(0, str(ROOT_DIR / "backend"))
    from app.core.database import SessionLocal
    from app.models.user import User
    from app.core.security import create_access_token
    from fastapi.testclient import TestClient
    from app.main import app

    db = SessionLocal()
    user = db.query(User).filter(User.email == "nivivini0602@gmail.com").first()
    assert user is not None, "Test user not found"
    token = create_access_token(data={"sub": str(user.id)})
    db.close()

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # Verify Multi-Document query returns all required contract fields for Phase 4 UX
    payload = {
        "query": "What is TCP and UDP?",
        "document_ids": [48, 49],
        "top_k": 4
    }
    response = client.post("/documents/ask", json=payload, headers=headers)
    assert response.status_code == 200, f"Ask API failed: {response.text}"
    data = response.json()

    assert "answer" in data, "Missing 'answer' field"
    assert "results" in data, "Missing 'results' field"
    assert "follow_up_questions" in data, "Missing 'follow_up_questions' field"
    assert isinstance(data["follow_up_questions"], list), "follow_up_questions must be a list"
    assert len(data["follow_up_questions"]) > 0, "follow_up_questions must have suggestions"

    # Verify source structure
    for src in data["results"]:
        assert "document_title" in src, "Source must include 'document_title'"
        assert "source_type" in src, "Source must include 'source_type'"
        assert "page_number" in src, "Source must include 'page_number'"
        assert "citation_index" in src, "Source must include 'citation_index'"

    print(f"PASS: API Contract verified! {len(data['results'])} sources and {len(data['follow_up_questions'])} follow-up questions returned!")

def main():
    print("=" * 60)
    print("COGNIDOCS MULTI-DOCUMENT CHAT FRONTEND VALIDATION")
    print("=" * 60)
    test_multi_document_selector_component()
    test_multi_document_css()
    test_ask_ai_integration()
    test_production_build_artifacts()
    test_live_api_response_contract()
    print("\n" + "=" * 60)
    print("ALL 5 FRONTEND VALIDATION SUITES PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    main()
