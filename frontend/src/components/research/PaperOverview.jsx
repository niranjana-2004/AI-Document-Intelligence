import {
    BookOpen,
    CheckCircle2,
    AlertTriangle,
    FileWarning,
    Sparkles,
    Cpu,
    Clock,
    ShieldCheck,
    Layers,
    FileText,
    SlidersHorizontal,
} from 'lucide-react'
import { getDetectionMeta, getFactTypeMeta } from '../../utils/researchPaperUtils'

export default function PaperOverview({
    analysis,
    onInspectField,
    onOverrideClassification,
    loading,
}) {
    if (!analysis) return null

    const detection = analysis.paper_detection || {}
    const detMeta = getDetectionMeta(detection)
    const basic = analysis.basic_information || {}
    const timings = analysis.timings || {}
    const coveragePct = Math.round(Number(analysis.evidence_coverage || 0) * 100)
    const activeOverride = detection.manual_override || 'auto'

    const renderInlineFieldValue = (label, field) => {
        if (!field) return null
        const isMissing = field.fact_type === 'missing'
        const meta = getFactTypeMeta(field.fact_type)
        const sources = Array.isArray(field.sources) ? field.sources : []

        return (
            <div className={`rpa-meta-row ${isMissing ? 'is-missing' : ''}`} key={label}>
                <div className="rpa-meta-label-group">
                    <span className="rpa-meta-label">{label}</span>
                    <span className={`rpa-fact-chip tone-${meta.tone}`}>{meta.label}</span>
                </div>
                <div className="rpa-meta-value-wrap">
                    <p className="rpa-meta-value">{field.value}</p>
                    {sources.length > 0 && (
                        <button
                            type="button"
                            className="rpa-source-trigger"
                            onClick={() => onInspectField(label, field)}
                        >
                            <span>p.{sources[0].page}</span>
                            <span className="rpa-source-dot" aria-hidden="true">•</span>
                            <span>{sources.length} {sources.length === 1 ? 'source' : 'sources'}</span>
                        </button>
                    )}
                </div>
            </div>
        )
    }

    return (
        <section className="rpa-overview-card" aria-label="Research paper overview">
            <div className="rpa-overview-top">
                <div className="rpa-overview-heading">
                    <div className="rpa-badge-strip">
                        <span className={`rpa-detect-badge tone-${detMeta.tone}`}>
                            {detMeta.tone === 'success' ? (
                                <CheckCircle2 size={14} />
                            ) : detMeta.tone === 'warning' ? (
                                <AlertTriangle size={14} />
                            ) : (
                                <FileWarning size={14} />
                            )}
                            <span>{detMeta.label}</span>
                            <strong>{detMeta.confidencePct}%</strong>
                        </span>

                        <span className={`rpa-mode-badge ${analysis.analysis_mode === 'ollama_hybrid' ? 'is-llm' : 'is-det'}`}>
                            {analysis.analysis_mode === 'ollama_hybrid' ? (
                                <Sparkles size={13} />
                            ) : (
                                <Cpu size={13} />
                            )}
                            <span>
                                {analysis.analysis_mode === 'ollama_hybrid'
                                    ? 'Local Ollama + Grounded Hybrid'
                                    : 'Deterministic Grounded Engine'}
                            </span>
                        </span>

                        {analysis.cached && (
                            <span className="rpa-status-pill is-cached">Cached Result</span>
                        )}
                        {analysis.is_outdated && (
                            <span className="rpa-status-pill is-outdated">Outdated — Refresh Recommended</span>
                        )}
                    </div>

                    <h2 className="rpa-paper-title">
                        {basic.title?.fact_type !== 'missing'
                            ? basic.title?.value
                            : analysis.document_filename}
                    </h2>
                    <p className="rpa-detection-rationale">{detection.rationale}</p>
                </div>

                <div className="rpa-override-box">
                    <div className="rpa-override-label">
                        <SlidersHorizontal size={13} />
                        <span>Classification Mode</span>
                    </div>
                    <div className="rpa-override-buttons" role="group" aria-label="Classification override">
                        {[
                            { id: 'auto', label: 'Auto' },
                            { id: 'research_paper', label: 'Research Paper' },
                            { id: 'non_research', label: 'Non-Research' },
                        ].map((opt) => (
                            <button
                                key={opt.id}
                                type="button"
                                disabled={loading}
                                className={`rpa-override-btn ${activeOverride === opt.id ? 'active' : ''}`}
                                onClick={() => onOverrideClassification(opt.id)}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {!detection.is_research_paper && (
                <div className="rpa-non-research-banner" role="status">
                    <AlertTriangle size={17} />
                    <div>
                        <strong>Document does not match standard academic paper structure.</strong>
                        <p>
                            Cognidocs still ran safe grounded extraction without fabricating missing academic fields.
                            If this is a workshop paper or thesis chapter, choose <strong>Research Paper</strong> above to override.
                        </p>
                    </div>
                </div>
            )}

            <div className="rpa-kpi-grid">
                <div className="rpa-kpi-card">
                    <div className="rpa-kpi-icon"><FileText size={16} /></div>
                    <div>
                        <span className="rpa-kpi-value">{analysis.pages_count || 1}</span>
                        <span className="rpa-kpi-label">Pages Indexed</span>
                    </div>
                </div>
                <div className="rpa-kpi-card">
                    <div className="rpa-kpi-icon"><Layers size={16} /></div>
                    <div>
                        <span className="rpa-kpi-value">{analysis.sections_count || 0}</span>
                        <span className="rpa-kpi-label">Detected Sections</span>
                    </div>
                </div>
                <div className="rpa-kpi-card">
                    <div className="rpa-kpi-icon"><ShieldCheck size={16} /></div>
                    <div>
                        <span className="rpa-kpi-value">{coveragePct}%</span>
                        <span className="rpa-kpi-label">
                            Evidence Grounding ({analysis.evidence_count || 0} refs)
                        </span>
                    </div>
                </div>
                <div className="rpa-kpi-card">
                    <div className="rpa-kpi-icon"><Clock size={16} /></div>
                    <div>
                        <span className="rpa-kpi-value">
                            {analysis.cached
                                ? `${Math.round(timings.cache_retrieval_ms || 0)} ms`
                                : `${Math.round(timings.total_ms || 0)} ms`}
                        </span>
                        <span className="rpa-kpi-label">
                            {analysis.cached ? 'Cache Hit Time' : 'Extraction Time'}
                        </span>
                    </div>
                </div>
            </div>

            {(detection.signals?.length > 0 || detection.missing_signals?.length > 0) && (
                <div className="rpa-signals-row">
                    {detection.signals?.map((sig) => (
                        <span key={`sig-${sig}`} className="rpa-signal-tag is-present">
                            + {sig.replace(/_/g, ' ')}
                        </span>
                    ))}
                    {detection.missing_signals?.map((sig) => (
                        <span key={`miss-${sig}`} className="rpa-signal-tag is-absent">
                            - {sig.replace(/_/g, ' ')}
                        </span>
                    ))}
                </div>
            )}

            <div className="rpa-basic-grid">
                {renderInlineFieldValue('Title', basic.title)}
                {renderInlineFieldValue('Authors', basic.authors)}
                {renderInlineFieldValue('Affiliation', basic.affiliation)}
                {renderInlineFieldValue('Publication / Venue', basic.publication_info)}
                {renderInlineFieldValue('Keywords', basic.keywords)}
            </div>

            {basic.abstract && (
                <div className={`rpa-abstract-box ${basic.abstract.fact_type === 'missing' ? 'is-missing' : ''}`}>
                    <div className="rpa-abstract-header">
                        <div className="rpa-abstract-title-wrap">
                            <BookOpen size={15} />
                            <h3>Abstract</h3>
                            <span className={`rpa-fact-chip tone-${getFactTypeMeta(basic.abstract.fact_type).tone}`}>
                                {getFactTypeMeta(basic.abstract.fact_type).label}
                            </span>
                        </div>
                        {basic.abstract.sources?.length > 0 && (
                            <button
                                type="button"
                                className="rpa-source-trigger"
                                onClick={() => onInspectField('Abstract', basic.abstract)}
                            >
                                Inspect Evidence (p.{basic.abstract.sources[0].page})
                            </button>
                        )}
                    </div>
                    <p>{basic.abstract.value}</p>
                </div>
            )}
        </section>
    )
}

