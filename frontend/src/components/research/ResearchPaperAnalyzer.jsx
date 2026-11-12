import { useState, useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
    FlaskConical,
    RefreshCw,
    BookOpen,
    Cpu,
    BarChart3,
    ListTree,
    Table2,
    FileSearch,
    CheckCircle2,
    AlertTriangle,
    Compass,
    Layers,
} from 'lucide-react'
import {
    apiRequest,
    analyzeResearchPaper,
    getResearchPaperAnalysis,
} from '../../services/api'
import { flattenSectionHierarchy, getFactTypeMeta } from '../../utils/researchPaperUtils'
import PaperOverview from './PaperOverview'
import PaperSectionCard from './PaperSectionCard'
import EvidenceDrawer from './EvidenceDrawer'
import '../../styles/research-paper.css'

const CONTEXT_FIELDS = [
    { key: 'research_domain', label: 'Research Domain' },
    { key: 'problem_statement', label: 'Problem Statement' },
    { key: 'motivation', label: 'Motivation' },
    { key: 'research_objective', label: 'Research Objective' },
    { key: 'research_questions', label: 'Research Questions' },
    { key: 'hypothesis', label: 'Hypothesis' },
]

const METHODOLOGY_FIELDS = [
    { key: 'methodology_type', label: 'Methodology Type' },
    { key: 'proposed_approach', label: 'Proposed Approach' },
    { key: 'algorithms_models', label: 'Algorithms & Models' },
    { key: 'architecture', label: 'System Architecture' },
    { key: 'framework_tools', label: 'Frameworks & Tools' },
    { key: 'dataset', label: 'Datasets' },
    { key: 'dataset_size', label: 'Dataset Size' },
    { key: 'preprocessing', label: 'Preprocessing' },
    { key: 'experimental_setup', label: 'Experimental Setup' },
]

const EVALUATION_FIELDS = [
    { key: 'evaluation_metrics', label: 'Evaluation Metrics' },
    { key: 'baseline_methods', label: 'Baselines & Prior Art' },
    { key: 'experiments', label: 'Experiments Conducted' },
    { key: 'results', label: 'Reported Results' },
    { key: 'numerical_findings', label: 'Key Numerical Findings' },
    { key: 'comparisons', label: 'Performance Comparisons' },
]

const CONCLUSION_FIELDS = [
    { key: 'main_conclusions', label: 'Main Conclusions' },
    { key: 'limitations', label: 'Stated Limitations' },
    { key: 'future_work', label: 'Future Work' },
]

export default function ResearchPaperAnalyzer() {
    const [searchParams, setSearchParams] = useSearchParams()
    const [documents, setDocuments] = useState([])
    const [docsLoading, setDocsLoading] = useState(true)
    const [selectedDocId, setSelectedDocId] = useState(() => {
        const p = parseInt(searchParams.get('doc') || '', 10)
        return Number.isFinite(p) ? p : null
    })
    const [analysis, setAnalysis] = useState(null)
    const [analyzing, setAnalyzing] = useState(false)
    const [fastModeOnly, setFastModeOnly] = useState(false)
    const [error, setError] = useState('')
    const [activeTab, setActiveTab] = useState('overview')
    const [drawerOpen, setDrawerOpen] = useState(false)
    const [selectedClaim, setSelectedClaim] = useState(null)

    useEffect(() => {
        let ignore = false
        apiRequest('/documents')
            .then((data) => {
                if (ignore) return
                const list = Array.isArray(data) ? data : (data?.documents || [])
                setDocuments(list)
                setSelectedDocId((prev) => {
                    if (prev && list.some((d) => d.id === prev)) return prev
                    const preferred = list.find((d) => (d.document_type || '').toUpperCase() === 'PDF')
                    return preferred ? preferred.id : (list[0]?.id ?? null)
                })
            })
            .catch((err) => {
                if (!ignore) setError(err.message || 'Failed to load uploaded documents.')
            })
            .finally(() => {
                if (!ignore) setDocsLoading(false)
            })
        return () => {
            ignore = true
        }
    }, [])

    const handleSelectDoc = (docIdStr) => {
        const nextId = parseInt(docIdStr, 10)
        if (!Number.isFinite(nextId)) return
        setSelectedDocId(nextId)
        setSearchParams({ doc: String(nextId) })
        setError('')
    }

    // Try loading cached analysis when switching document (404 means not yet analyzed)
    useEffect(() => {
        if (!selectedDocId) return
        let cancelled = false
        getResearchPaperAnalysis(selectedDocId)
            .then((data) => {
                if (!cancelled) {
                    setError('')
                    setAnalysis(data)
                }
            })
            .catch((err) => {
                if (!cancelled) {
                    if (err?.status === 404) {
                        setError('')
                        setAnalysis(null)
                    } else {
                        setError(err.message || 'Failed to check cached analysis.')
                    }
                }
            })
        return () => {
            cancelled = true
        }
    }, [selectedDocId])

    const handleRunAnalysis = async ({ forceRefresh = false, override = null } = {}) => {
        if (!selectedDocId || analyzing) return
        setAnalyzing(true)
        setError('')
        try {
            const data = await analyzeResearchPaper(selectedDocId, {
                forceRefresh,
                classificationOverride: override,
                skipLlm: fastModeOnly,
            })
            setAnalysis(data)
        } catch (err) {
            setError(err.message || 'Failed to analyze research paper.')
        } finally {
            setAnalyzing(false)
        }
    }

    const handleInspectField = (label, field) => {
        setSelectedClaim({ label, field })
        setDrawerOpen(true)
    }

    const handleInspectNumerical = (item) => {
        setSelectedClaim({
            label: `${item.metric_name}: ${item.original_value}`,
            factType: item.fact_type,
            field: {
                value: item.experimental_context || `${item.metric_name} = ${item.original_value}`,
                fact_type: item.fact_type,
                sources: item.source ? [item.source] : [],
            },
        })
        setDrawerOpen(true)
    }

    const flatSections = useMemo(
        () => flattenSectionHierarchy(analysis?.sections || []),
        [analysis]
    )

    const selectedDoc = useMemo(
        () => documents.find((d) => d.id === selectedDocId) || null,
        [documents, selectedDocId]
    )

    const tableFigureData = analysis?.tables_and_figures || { items: [], visual_parsing_limitation: '' }

    return (
        <div className="rpa-page">
            <header className="rpa-hero">
                <div className="rpa-hero-title">
                    <span className="rpa-hero-icon">
                        <FlaskConical size={22} />
                    </span>
                    <div>
                        <div className="rpa-eyebrow">
                            <span>Source-Grounded Document Intelligence</span>
                            <span className="rpa-phase-pill">Phase 1 · Structured Extraction</span>
                        </div>
                        <h1>Research Paper Analyzer</h1>
                        <p>
                            Identify academic papers from content signals, inspect hierarchical structure,
                            and verify every extracted claim directly against cited pages and excerpts.
                        </p>
                    </div>
                </div>

                <div className="rpa-toolbar">
                    <div className="rpa-doc-select-wrap">
                        <label htmlFor="rpa-doc-select">Target Document</label>
                        <select
                            id="rpa-doc-select"
                            className="rpa-doc-select"
                            value={selectedDocId ?? ''}
                            onChange={(e) => handleSelectDoc(e.target.value)}
                            disabled={docsLoading || analyzing}
                        >
                            {documents.length === 0 ? (
                                <option value="">No uploaded documents available</option>
                            ) : (
                                documents.map((doc) => (
                                    <option key={doc.id} value={doc.id}>
                                        {doc.filename} ({doc.document_type || 'DOC'})
                                    </option>
                                ))
                            )}
                        </select>
                    </div>

                    <label className="rpa-fast-toggle" title="Skip local Ollama refinement and run sub-second deterministic extraction">
                        <input
                            type="checkbox"
                            checked={fastModeOnly}
                            onChange={(e) => setFastModeOnly(e.target.checked)}
                            disabled={analyzing}
                        />
                        <span>Fast Deterministic Mode</span>
                    </label>

                    <div className="rpa-action-group">
                        <button
                            type="button"
                            className="rpa-primary-btn"
                            disabled={!selectedDocId || analyzing}
                            onClick={() => handleRunAnalysis({ forceRefresh: Boolean(analysis) })}
                        >
                            <RefreshCw size={15} className={analyzing ? 'rpa-spin' : ''} />
                            <span>
                                {analyzing
                                    ? 'Analyzing Paper...'
                                    : analysis
                                        ? 'Re-analyze Paper'
                                        : 'Analyze Paper'}
                            </span>
                        </button>

                        {analysis && (
                            <button
                                type="button"
                                className="rpa-secondary-btn"
                                onClick={() => {
                                    setSelectedClaim(null)
                                    setDrawerOpen(true)
                                }}
                            >
                                <FileSearch size={15} />
                                <span>Evidence Index ({analysis.evidence_count || 0})</span>
                            </button>
                        )}
                    </div>
                </div>
            </header>

            {error && (
                <div className="rpa-error-banner" role="alert">
                    <AlertTriangle size={17} />
                    <span>{error}</span>
                </div>
            )}

            {analyzing && !analysis && (
                <div className="rpa-loading-panel">
                    <RefreshCw size={24} className="rpa-spin" />
                    <div>
                        <h3>Extracting Structured Sections &amp; Grounding Evidence...</h3>
                        <p>
                            Detecting academic layout, mapping section hierarchy, extracting metrics,
                            and verifying citations against {selectedDoc?.filename || 'the selected document'}.
                        </p>
                    </div>
                </div>
            )}

            {!analyzing && !analysis && selectedDocId && (
                <div className="rpa-empty-state">
                    <BookOpen size={36} />
                    <h2>No Structured Analysis Saved Yet</h2>
                    <p>
                        Click <strong>Analyze Paper</strong> to run source-grounded structured extraction on{' '}
                        <code>{selectedDoc?.filename}</code>.
                    </p>
                    <button
                        type="button"
                        className="rpa-primary-btn"
                        onClick={() => handleRunAnalysis({ forceRefresh: false })}
                    >
                        <FlaskConical size={16} />
                        <span>Run Research Paper Analysis</span>
                    </button>
                </div>
            )}

            {analysis && (
                <>
                    <PaperOverview
                        analysis={analysis}
                        loading={analyzing}
                        onInspectField={handleInspectField}
                        onOverrideClassification={(override) =>
                            handleRunAnalysis({ forceRefresh: true, override })
                        }
                    />

                    <nav className="rpa-tab-bar" aria-label="Analysis views">
                        {[
                            { id: 'overview', label: 'Context & Methodology', icon: Compass },
                            { id: 'evaluation', label: 'Evaluation & Metrics', icon: BarChart3 },
                            { id: 'structure', label: `Sections (${flatSections.length}) & Figures (${tableFigureData.items?.length || 0})`, icon: ListTree },
                        ].map((tab) => {
                            const TabIcon = tab.icon
                            return (
                                <button
                                    key={tab.id}
                                    type="button"
                                    className={`rpa-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                                    onClick={() => setActiveTab(tab.id)}
                                >
                                    <TabIcon size={15} />
                                    <span>{tab.label}</span>
                                </button>
                            )
                        })}
                    </nav>

                    {activeTab === 'overview' && (
                        <div className="rpa-two-col">
                            <PaperSectionCard
                                title="Research Context"
                                subtitle="Domain, problem framing, objectives & hypotheses"
                                icon={Compass}
                                sectionData={analysis.research_context}
                                fieldDefinitions={CONTEXT_FIELDS}
                                onInspectField={handleInspectField}
                            />
                            <PaperSectionCard
                                title="Methodology"
                                subtitle="Proposed approach, algorithms, datasets & setup"
                                icon={Cpu}
                                sectionData={analysis.methodology}
                                fieldDefinitions={METHODOLOGY_FIELDS}
                                onInspectField={handleInspectField}
                            />
                        </div>
                    )}

                    {activeTab === 'evaluation' && (
                        <div className="rpa-eval-stack">
                            <div className="rpa-two-col">
                                <PaperSectionCard
                                    title="Evaluation & Benchmarks"
                                    subtitle="Metrics, baselines, experiments & comparisons"
                                    icon={BarChart3}
                                    sectionData={analysis.evaluation}
                                    fieldDefinitions={EVALUATION_FIELDS}
                                    onInspectField={handleInspectField}
                                />
                                <PaperSectionCard
                                    title="Conclusions & Scope"
                                    subtitle="Summary outcomes, limitations & stated future work"
                                    icon={CheckCircle2}
                                    sectionData={analysis.conclusion}
                                    fieldDefinitions={CONCLUSION_FIELDS}
                                    onInspectField={handleInspectField}
                                />
                            </div>

                            <section className="rpa-section-card">
                                <header className="rpa-section-header">
                                    <div className="rpa-section-title-group">
                                        <span className="rpa-section-icon"><BarChart3 size={17} /></span>
                                        <div>
                                            <h3>Extracted Numerical Findings &amp; Derived Deltas</h3>
                                            <p>Original units preserved verbatim; derived deltas explicitly marked</p>
                                        </div>
                                    </div>
                                    <span className="rpa-section-count">
                                        {analysis.numerical_data?.length || 0} items
                                    </span>
                                </header>

                                {(!analysis.numerical_data || analysis.numerical_data.length === 0) ? (
                                    <p className="rpa-empty-inline">
                                        No structured numerical metrics detected in extracted text.
                                    </p>
                                ) : (
                                    <div className="rpa-table-wrap">
                                        <table className="rpa-data-table">
                                            <thead>
                                                <tr>
                                                    <th>Metric</th>
                                                    <th>Value</th>
                                                    <th>Unit</th>
                                                    <th>Fact Type</th>
                                                    <th>Experimental Context</th>
                                                    <th>Source</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {analysis.numerical_data.map((item) => {
                                                    const meta = getFactTypeMeta(item.fact_type)
                                                    return (
                                                        <tr key={item.id}>
                                                            <td className="rpa-cell-strong">{item.metric_name}</td>
                                                            <td className="rpa-cell-num">{item.original_value}</td>
                                                            <td>{item.unit || '—'}</td>
                                                            <td>
                                                                <span className={`rpa-fact-chip tone-${meta.tone}`}>
                                                                    {meta.label}
                                                                </span>
                                                            </td>
                                                            <td className="rpa-cell-context">{item.experimental_context}</td>
                                                            <td>
                                                                <button
                                                                    type="button"
                                                                    className="rpa-source-trigger"
                                                                    onClick={() => handleInspectNumerical(item)}
                                                                >
                                                                    p.{item.source?.page || 1}
                                                                </button>
                                                            </td>
                                                        </tr>
                                                    )
                                                })}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </section>
                        </div>
                    )}

                    {activeTab === 'structure' && (
                        <div className="rpa-two-col">
                            <section className="rpa-section-card">
                                <header className="rpa-section-header">
                                    <div className="rpa-section-title-group">
                                        <span className="rpa-section-icon"><Layers size={17} /></span>
                                        <div>
                                            <h3>Detected Section Hierarchy</h3>
                                            <p>Original paper headings preserved; dotted ToC lines filtered</p>
                                        </div>
                                    </div>
                                    <span className="rpa-section-count">{flatSections.length} sections</span>
                                </header>

                                {flatSections.length === 0 ? (
                                    <p className="rpa-empty-inline">
                                        No explicit hierarchical headings detected in document chunks.
                                    </p>
                                ) : (
                                    <ul className="rpa-outline-list">
                                        {flatSections.map((sec) => (
                                            <li
                                                key={sec.id}
                                                className={`rpa-outline-item depth-${Math.min(3, sec.depth || 0)}`}
                                            >
                                                <div className="rpa-outline-top">
                                                    <span className="rpa-outline-title">{sec.title}</span>
                                                    <div className="rpa-outline-meta">
                                                        <span className="rpa-role-pill">{sec.normalized_role}</span>
                                                        {sec.page_start != null && (
                                                            <span className="rpa-page-pill">
                                                                {sec.page_end && sec.page_end !== sec.page_start
                                                                    ? `pp.${sec.page_start}–${sec.page_end}`
                                                                    : `p.${sec.page_start}`}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                                {sec.preview && <p className="rpa-outline-preview">{sec.preview}</p>}
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </section>

                            <section className="rpa-section-card">
                                <header className="rpa-section-header">
                                    <div className="rpa-section-title-group">
                                        <span className="rpa-section-icon"><Table2 size={17} /></span>
                                        <div>
                                            <h3>Tables, Figures, Algorithms &amp; Equations</h3>
                                            <p>Indexed from document text captions and inline references</p>
                                        </div>
                                    </div>
                                    <span className="rpa-section-count">
                                        {tableFigureData.items?.length || 0} refs
                                    </span>
                                </header>

                                {tableFigureData.visual_parsing_limitation && (
                                    <div className="rpa-visual-limit-banner">
                                        <AlertTriangle size={15} />
                                        <span>{tableFigureData.visual_parsing_limitation}</span>
                                    </div>
                                )}

                                {(!tableFigureData.items || tableFigureData.items.length === 0) ? (
                                    <p className="rpa-empty-inline">
                                        No numbered Table, Figure, Algorithm, or Equation references found.
                                    </p>
                                ) : (
                                    <div className="rpa-tf-list">
                                        {tableFigureData.items.map((ref) => (
                                            <div key={ref.id} className="rpa-tf-item">
                                                <div className="rpa-tf-top">
                                                    <strong>{ref.label}</strong>
                                                    <div className="rpa-tf-pills">
                                                        <span className="rpa-role-pill">{ref.kind}</span>
                                                        <span className="rpa-page-pill">p.{ref.page || 1}</span>
                                                        {ref.section && <span className="rpa-sec-pill">{ref.section}</span>}
                                                    </div>
                                                </div>
                                                {ref.caption_or_context && <p>{ref.caption_or_context}</p>}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </section>
                        </div>
                    )}
                </>
            )}

            <EvidenceDrawer
                isOpen={drawerOpen}
                onClose={() => setDrawerOpen(false)}
                selectedClaim={selectedClaim}
                analysis={analysis}
            />
        </div>
    )
}
