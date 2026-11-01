import { useState, useEffect } from 'react'
import {
    FileText,
    Sparkles,
    RefreshCw,
    Copy,
    Check,
    AlertTriangle,
    Zap,
    BookOpen,
    Target,
    Layers,
    Clock,
    Tag
} from 'lucide-react'
import { apiRequest } from '../../services/api'

export default function HandwrittenSummaryTab({ documentId, transcriptionUpdated }) {
    const [summaryType, setSummaryType] = useState('detailed') // 'quick' | 'detailed' | 'exam_revision'
    const [summary, setSummary] = useState(null)
    const [loading, setLoading] = useState(false)
    const [generating, setGenerating] = useState(false)
    const [error, setError] = useState(null)
    const [copiedAll, setCopiedAll] = useState(false)
    const [copiedTerm, setCopiedTerm] = useState(null)

    // Load existing summary for current mode
    const fetchSummary = async (mode = summaryType) => {
        try {
            setLoading(true)
            setError(null)
            const res = await apiRequest(`/handwritten/${documentId}/summary?type=${mode}`)
            setSummary(res?.summary || null)
        } catch (err) {
            console.error('Fetch summary error:', err)
            setError(err.message || 'Failed to load study summary.')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (documentId) {
            fetchSummary(summaryType)
        }
    }, [documentId, summaryType, transcriptionUpdated])

    // Generate or regenerate summary
    const handleGenerate = async (forceType = summaryType) => {
        try {
            setGenerating(true)
            setError(null)
            const res = await apiRequest(`/handwritten/${documentId}/summary`, {
                method: 'POST',
                body: JSON.stringify({ summary_type: forceType })
            })
            setSummary(res?.summary || null)
        } catch (err) {
            console.error('Generate summary error:', err)
            setError(err.message || 'Failed to generate study summary.')
        } finally {
            setGenerating(false)
        }
    }

    const handleCopyAll = () => {
        if (!summary) return
        const text = `# ${summary.title || 'Study Summary'}\n\n` +
            `## Overview\n${summary.overview || ''}\n\n` +
            `## Key Takeaways\n${(summary.takeaways || []).map(t => `- ${t}`).join('\n')}\n\n` +
            `## Study Notes\n${summary.detailed_content || ''}\n\n` +
            `## Key Terminology\n${(summary.key_terms || []).map(k => `- **${k.term}** (Page ${k.page_number}): ${k.definition}`).join('\n')}`

        navigator.clipboard.writeText(text)
        setCopiedAll(true)
        setTimeout(() => setCopiedAll(false), 2000)
    }

    const handleCopyTerm = (termText, id) => {
        navigator.clipboard.writeText(termText)
        setCopiedTerm(id)
        setTimeout(() => setCopiedTerm(null), 1800)
    }

    // Helper to render markdown headings & paragraphs
    const renderMarkdown = (content) => {
        if (!content) return null
        const lines = content.split('\n')
        return lines.map((line, idx) => {
            if (line.startsWith('### ')) {
                return <h4 key={idx} className="intel-h4">{line.replace('### ', '')}</h4>
            }
            if (line.startsWith('## ')) {
                return <h3 key={idx} className="intel-h3">{line.replace('## ', '')}</h3>
            }
            if (line.startsWith('# ')) {
                return <h2 key={idx} className="intel-h2">{line.replace('# ', '')}</h2>
            }
            if (line.startsWith('- ') || line.startsWith('* ')) {
                return (
                    <li key={idx} className="intel-bullet-item">
                        {line.substring(2)}
                    </li>
                )
            }
            if (!line.trim()) {
                return <div key={idx} style={{ height: '8px' }} />
            }
            return <p key={idx} className="intel-paragraph">{line}</p>
        })
    }

    return (
        <div className="intel-tab-container">
            {/* Top Toolbar: Mode Switcher & Actions */}
            <div className="intel-toolbar">
                <div className="intel-mode-group">
                    <button
                        type="button"
                        className={`intel-mode-btn ${summaryType === 'quick' ? 'active' : ''}`}
                        onClick={() => setSummaryType('quick')}
                    >
                        <Zap size={14} />
                        <span>Quick Summary</span>
                    </button>
                    <button
                        type="button"
                        className={`intel-mode-btn ${summaryType === 'detailed' ? 'active' : ''}`}
                        onClick={() => setSummaryType('detailed')}
                    >
                        <BookOpen size={14} />
                        <span>Detailed Notes</span>
                    </button>
                    <button
                        type="button"
                        className={`intel-mode-btn ${summaryType === 'exam_revision' ? 'active' : ''}`}
                        onClick={() => setSummaryType('exam_revision')}
                    >
                        <Target size={14} />
                        <span>Exam Revision</span>
                    </button>
                </div>

                <div className="intel-actions-group">
                    {summary && (
                        <button
                            type="button"
                            className="btn-studio-action"
                            onClick={handleCopyAll}
                            title="Copy full study summary markdown"
                        >
                            {copiedAll ? <Check size={13} style={{ color: '#34d399' }} /> : <Copy size={13} />}
                            <span>{copiedAll ? 'Copied Markdown!' : 'Copy Summary'}</span>
                        </button>
                    )}
                    <button
                        type="button"
                        className="btn-studio-action btn-studio-primary"
                        onClick={() => handleGenerate(summaryType)}
                        disabled={generating}
                    >
                        <Sparkles size={13} className={generating ? 'spin-icon' : ''} />
                        <span>{generating ? 'Synthesizing...' : (summary ? 'Regenerate' : 'Generate Summary')}</span>
                    </button>
                </div>
            </div>

            {/* Outdated Notification Banner */}
            {summary && summary.is_outdated && (
                <div className="intel-outdated-banner">
                    <div className="outdated-content">
                        <AlertTriangle size={18} className="outdated-icon" />
                        <div>
                            <strong>Transcription Modified</strong>
                            <p>Handwriting transcription has changed since this summary was synthesized. Regenerate to incorporate the latest changes.</p>
                        </div>
                    </div>
                    <button
                        type="button"
                        className="btn-outdated-regen"
                        onClick={() => handleGenerate(summaryType)}
                        disabled={generating}
                    >
                        <RefreshCw size={12} className={generating ? 'spin-icon' : ''} />
                        <span>{generating ? 'Updating...' : 'Regenerate Now'}</span>
                    </button>
                </div>
            )}

            {/* Error Message */}
            {error && (
                <div className="intel-error-banner">
                    <AlertTriangle size={16} />
                    <span>{error}</span>
                </div>
            )}

            {/* Loading / Generating State */}
            {generating && (
                <div className="intel-generating-card">
                    <div className="intel-spinner-orb">
                        <Sparkles size={28} className="spin-icon" style={{ color: '#38bdf8' }} />
                    </div>
                    <h4>Synthesizing Handwritten Notes...</h4>
                    <p>Ollama Llama 3.2 is analyzing your transcribed pages, cross-referencing citations, and building a structured {summaryType.replace('_', ' ')} study guide.</p>
                    <div className="intel-progress-bar-wrap">
                        <div className="intel-progress-bar-fill" />
                    </div>
                </div>
            )}

            {/* Empty State */}
            {!summary && !generating && !loading && (
                <div className="intel-empty-card">
                    <div className="empty-icon-wrap">
                        <FileText size={40} style={{ color: '#8b5cf6' }} />
                    </div>
                    <h3>Transform Handwritten Notes into Study Guides</h3>
                    <p>
                        Generate grounded academic overviews, bulleted takeaways, in-depth lecture notes,
                        and key concept glossaries directly from your handwriting transcription.
                    </p>
                    <div className="empty-features-grid">
                        <div className="empty-feat-item">
                            <Zap size={16} style={{ color: '#38bdf8' }} />
                            <span><strong>Quick Summary:</strong> Rapid 2-minute overview for pre-class review.</span>
                        </div>
                        <div className="empty-feat-item">
                            <BookOpen size={16} style={{ color: '#a855f7' }} />
                            <span><strong>Detailed Notes:</strong> Full hierarchical breakdown with source citations.</span>
                        </div>
                        <div className="empty-feat-item">
                            <Target size={16} style={{ color: '#ec4899' }} />
                            <span><strong>Exam Revision:</strong> High-yield formulas, definitions, and memory checklist.</span>
                        </div>
                    </div>
                    <button
                        type="button"
                        className="btn-intel-primary"
                        onClick={() => handleGenerate(summaryType)}
                    >
                        <Sparkles size={16} />
                        <span>Generate {summaryType === 'exam_revision' ? 'Exam Revision' : summaryType === 'quick' ? 'Quick' : 'Detailed'} Summary</span>
                    </button>
                </div>
            )}

            {/* Summary Content View */}
            {summary && !generating && (
                <div className="intel-content-layout">
                    {/* Header Details */}
                    <div className="summary-title-card">
                        <div className="summary-meta-row">
                            <span className="summary-type-badge">
                                {summaryType === 'quick' && <Zap size={12} />}
                                {summaryType === 'detailed' && <BookOpen size={12} />}
                                {summaryType === 'exam_revision' && <Target size={12} />}
                                <span>{summary.summary_type ? summary.summary_type.replace('_', ' ').toUpperCase() : 'STUDY GUIDE'}</span>
                            </span>
                            {summary.created_at && (
                                <span className="summary-date-badge">
                                    <Clock size={12} />
                                    <span>{new Date(summary.created_at).toLocaleDateString()}</span>
                                </span>
                            )}
                        </div>
                        <h2 className="summary-doc-title">{summary.title || 'Handwritten Notes Study Guide'}</h2>
                    </div>

                    {/* Section 1: Executive Overview */}
                    {summary.overview && (
                        <div className="intel-section-card overview-card">
                            <div className="section-card-header">
                                <span className="section-dot cyan" />
                                <h3>Executive Overview</h3>
                            </div>
                            <p className="overview-text">{summary.overview}</p>
                        </div>
                    )}

                    {/* Section 2: Key Takeaways */}
                    {summary.takeaways && summary.takeaways.length > 0 && (
                        <div className="intel-section-card takeaways-card">
                            <div className="section-card-header">
                                <span className="section-dot violet" />
                                <h3>Key Takeaways ({summary.takeaways.length})</h3>
                            </div>
                            <div className="takeaways-grid">
                                {summary.takeaways.map((takeaway, idx) => (
                                    <div key={idx} className="takeaway-item">
                                        <div className="takeaway-icon-pill">
                                            <Check size={12} />
                                        </div>
                                        <span className="takeaway-text">{takeaway}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Section 3: Structured Study Guide */}
                    {summary.detailed_content && (
                        <div className="intel-section-card content-card">
                            <div className="section-card-header">
                                <span className="section-dot pink" />
                                <h3>Structured Study Notes</h3>
                            </div>
                            <div className="markdown-body">
                                {renderMarkdown(summary.detailed_content)}
                            </div>
                        </div>
                    )}

                    {/* Section 4: Key Terminology Glossary */}
                    {summary.key_terms && summary.key_terms.length > 0 && (
                        <div className="intel-section-card glossary-card">
                            <div className="section-card-header">
                                <span className="section-dot green" />
                                <h3>Key Terminology & Definitions ({summary.key_terms.length})</h3>
                            </div>
                            <div className="terms-grid">
                                {summary.key_terms.map((item, idx) => (
                                    <div key={idx} className="term-card">
                                        <div className="term-card-top">
                                            <h4 className="term-name">{item.term}</h4>
                                            <div className="term-actions">
                                                {item.page_number && (
                                                    <span className="page-citation-pill">
                                                        Page {item.page_number}
                                                    </span>
                                                )}
                                                <button
                                                    type="button"
                                                    className="btn-copy-term"
                                                    onClick={() => handleCopyTerm(item.definition, idx)}
                                                    title="Copy definition"
                                                >
                                                    {copiedTerm === idx ? <Check size={11} style={{ color: '#34d399' }} /> : <Copy size={11} />}
                                                </button>
                                            </div>
                                        </div>
                                        <p className="term-def">{item.definition}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
