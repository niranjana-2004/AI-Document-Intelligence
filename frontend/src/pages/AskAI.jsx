import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { apiRequest } from '../services/api'
import '../App.css'

/**
 * Normalizes completed conversation history to strictly respect backend constraints:
 * - Only completed, valid user/assistant exchanges
 * - At most the latest 6 prior messages
 * - Non-empty after trimming, at most 2,000 characters per message
 * - Total cumulative history content <= 6,000 characters
 * - Prioritizes recent dialogue turns by truncating older content if needed
 */
function normalizeConversationHistory(messagesList) {
    if (!Array.isArray(messagesList) || messagesList.length === 0) {
        return null
    }

    // Step 1: Extract only completed user/assistant exchanges
    const completedTurns = []
    for (let i = 0; i < messagesList.length; i++) {
        const msg = messagesList[i]
        if (!msg || msg.status === 'failed') continue

        if (msg.role === 'user') {
            const nextMsg = messagesList[i + 1]
            if (
                nextMsg &&
                nextMsg.role === 'assistant' &&
                nextMsg.status !== 'failed' &&
                typeof nextMsg.content === 'string' &&
                nextMsg.content.trim().length > 0 &&
                typeof msg.content === 'string' &&
                msg.content.trim().length > 0
            ) {
                completedTurns.push({ role: 'user', content: msg.content.trim() })
                completedTurns.push({ role: 'assistant', content: nextMsg.content.trim() })
                i++ // Skip paired assistant message
            }
        }
    }

    if (completedTurns.length === 0) {
        return null
    }

    // Step 2: At most the latest 6 messages
    const recentTurns = completedTurns.slice(-6)

    // Step 3: Per-message max 2,000 characters
    const perMessageCapped = recentTurns.map((turn) => {
        let text = turn.content
        if (text.length > 2000) {
            text = text.slice(0, 2000).trim()
        }
        return {
            role: turn.role,
            content: text,
        }
    }).filter((turn) => turn.content.length > 0)

    if (perMessageCapped.length === 0) {
        return null
    }

    // Step 4: Total cumulative content <= 6,000 characters (prioritize newest turns)
    const MAX_TOTAL_CHARS = 6000
    let remainingBudget = MAX_TOTAL_CHARS
    const result = []

    for (let i = perMessageCapped.length - 1; i >= 0; i--) {
        const turn = perMessageCapped[i]
        if (remainingBudget <= 0) break

        if (turn.content.length <= remainingBudget) {
            result.unshift(turn)
            remainingBudget -= turn.content.length
        } else {
            const truncated = turn.content.slice(0, remainingBudget).trim()
            if (truncated.length > 0) {
                result.unshift({
                    role: turn.role,
                    content: truncated,
                })
                remainingBudget -= truncated.length
            }
            break
        }
    }

    return result.length > 0 ? result : null
}

function AskAI() {
    const [question, setQuestion] = useState('')
    const [messages, setMessages] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    // Per-message UI states
    const [copiedMsgId, setCopiedMsgId] = useState(null)
    const [highlightedCitation, setHighlightedCitation] = useState(null) // { msgId, num }
    const [expandedSourceExcerpts, setExpandedSourceExcerpts] = useState({}) // `${msgId}-${num}`: boolean
    const [expandedSourcesDrawers, setExpandedSourcesDrawers] = useState({}) // `${msgId}`: boolean

    // Knowledge Scope states
    const [documents, setDocuments] = useState([])
    const [docsLoading, setDocsLoading] = useState(true)
    const [docsError, setDocsError] = useState('')
    const [scopeMode, setScopeMode] = useState('all') // 'all' | 'specific'
    const [selectedDocIds, setSelectedDocIds] = useState([])
    const [isDocPickerOpen, setIsDocPickerOpen] = useState(false)

    const textareaRef = useRef(null)
    const messagesEndRef = useRef(null)
    const activeRequestIdRef = useRef(0)
    const abortControllerRef = useRef(null)

    // Document-aware suggested questions states & cancellation guards
    const [suggestedQuestions, setSuggestedQuestions] = useState([])
    const [suggestionsLoading, setSuggestionsLoading] = useState(false)
    const suggestionsRequestIdRef = useRef(0)
    const suggestionsAbortControllerRef = useRef(null)

    const fetchSuggestedQuestions = async (forcedScopeMode = scopeMode, forcedDocIds = selectedDocIds) => {
        // Cancel any pending suggestion request
        if (suggestionsAbortControllerRef.current) {
            suggestionsAbortControllerRef.current.abort()
            suggestionsAbortControllerRef.current = null
        }

        // In Specific mode with 0 docs selected, or when no documents exist
        if (forcedScopeMode === 'specific' && (!Array.isArray(forcedDocIds) || forcedDocIds.length === 0)) {
            setSuggestedQuestions([])
            setSuggestionsLoading(false)
            return
        }

        if (documents.length === 0 && !docsLoading) {
            setSuggestedQuestions([])
            setSuggestionsLoading(false)
            return
        }

        const currentReqId = ++suggestionsRequestIdRef.current
        const abortController = new AbortController()
        suggestionsAbortControllerRef.current = abortController

        setSuggestedQuestions([])
        setSuggestionsLoading(true)

        try {
            const payload = {
                document_ids: forcedScopeMode === 'specific' ? forcedDocIds : null,
            }
            const data = await apiRequest('/documents/suggested-questions', {
                method: 'POST',
                signal: abortController.signal,
                body: JSON.stringify(payload),
            })

            if (currentReqId !== suggestionsRequestIdRef.current) {
                return
            }

            const questionsList = Array.isArray(data?.questions) ? data.questions : []
            setSuggestedQuestions(questionsList)
        } catch (err) {
            if (currentReqId !== suggestionsRequestIdRef.current || err?.name === 'AbortError') {
                return
            }
            console.warn('Failed to fetch suggested questions:', err)
            setSuggestedQuestions([])
        } finally {
            if (currentReqId === suggestionsRequestIdRef.current) {
                setSuggestionsLoading(false)
            }
        }
    }

    useEffect(() => {
        fetchDocuments()
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort()
            }
            if (suggestionsAbortControllerRef.current) {
                suggestionsAbortControllerRef.current.abort()
            }
        }
    }, [])

    // Refresh suggested questions on scope changes or when document collection finishes loading
    useEffect(() => {
        if (!docsLoading) {
            fetchSuggestedQuestions(scopeMode, selectedDocIds)
        }
        return () => {
            if (suggestionsAbortControllerRef.current) {
                suggestionsAbortControllerRef.current.abort()
            }
        }
    }, [scopeMode, selectedDocIds, documents.length, docsLoading])

    // Auto-scroll to bottom of conversation thread on new messages or loading
    useEffect(() => {
        if (messages.length > 0 || loading) {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
        }
    }, [messages.length, loading])

    // Clear citation highlight after 2.8s
    useEffect(() => {
        if (highlightedCitation != null) {
            const timer = setTimeout(() => {
                setHighlightedCitation(null)
            }, 2800)
            return () => clearTimeout(timer)
        }
    }, [highlightedCitation])

    const fetchDocuments = async () => {
        try {
            setDocsLoading(true)
            setDocsError('')
            const data = await apiRequest('/documents/')
            const list = Array.isArray(data)
                ? data
                : (data && Array.isArray(data.documents) ? data.documents : [])
            setDocuments(list)
        } catch (err) {
            console.error('Error fetching documents for Ask AI:', err)
            setDocsError(err.message || 'Unable to load documents.')
        } finally {
            setDocsLoading(false)
        }
    }

    // Document Scope handlers with request cancellation & conversation reset
    const handleScopeModeChange = (newMode) => {
        if (newMode !== scopeMode) {
            activeRequestIdRef.current++
            if (abortControllerRef.current) {
                abortControllerRef.current.abort()
                abortControllerRef.current = null
            }
            setLoading(false)
            if (messages.length > 0) {
                setMessages([])
            }
            setError('')
            setSuggestedQuestions([])
            setScopeMode(newMode)
            if (newMode === 'specific') {
                setIsDocPickerOpen(true)
            } else {
                setIsDocPickerOpen(false)
            }
        }
    }

    const handleToggleDoc = (docId) => {
        activeRequestIdRef.current++
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
            abortControllerRef.current = null
        }
        setLoading(false)
        if (messages.length > 0) {
            setMessages([])
        }
        setError('')
        setSuggestedQuestions([])
        setSelectedDocIds((prev) =>
            prev.includes(docId)
                ? prev.filter((id) => id !== docId)
                : [...prev, docId]
        )
    }

    const handleSelectAllDocs = () => {
        activeRequestIdRef.current++
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
            abortControllerRef.current = null
        }
        setLoading(false)
        if (messages.length > 0) {
            setMessages([])
        }
        setError('')
        setSuggestedQuestions([])
        setSelectedDocIds(documents.map((d) => d.id))
    }

    const handleClearDocs = () => {
        activeRequestIdRef.current++
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
            abortControllerRef.current = null
        }
        setLoading(false)
        if (messages.length > 0) {
            setMessages([])
        }
        setError('')
        setSuggestedQuestions([])
        setSelectedDocIds([])
    }

    // New Chat handler: cancels pending requests, clears conversation messages, preserves document scope
    const handleNewChat = () => {
        activeRequestIdRef.current++
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
            abortControllerRef.current = null
        }
        setLoading(false)
        setMessages([])
        setQuestion('')
        setError('')
        setHighlightedCitation(null)
        setExpandedSourceExcerpts({})
        setExpandedSourcesDrawers({})
        textareaRef.current?.focus()
        fetchSuggestedQuestions(scopeMode, selectedDocIds)
    }

    const getFileTypeBadge = (doc) => {
        if (doc.filename && doc.filename.includes('.')) {
            const ext = doc.filename.split('.').pop()
            if (ext) return ext.toUpperCase()
        }
        if (doc.document_type) {
            if (doc.document_type.includes('pdf')) return 'PDF'
            if (doc.document_type.includes('word') || doc.document_type.includes('docx')) return 'DOCX'
            if (doc.document_type.includes('text') || doc.document_type.includes('plain')) return 'TXT'
        }
        return 'DOC'
    }

    const getFileIcon = (badge) => {
        switch (badge) {
            case 'PDF':
                return '📄'
            case 'DOCX':
            case 'DOC':
                return '📝'
            case 'TXT':
                return '📃'
            default:
                return '📃'
        }
    }

    const isSubmitDisabled =
        loading ||
        !question.trim() ||
        (scopeMode === 'specific' && selectedDocIds.length === 0) ||
        (!docsLoading && documents.length === 0)

    const handleAskAI = async (overrideQuery = null) => {
        const queryText = (typeof overrideQuery === 'string' ? overrideQuery : question).trim()
        if (!queryText || loading) {
            return
        }

        if (scopeMode === 'specific' && selectedDocIds.length === 0) {
            setError('Please select at least one document or switch to All Documents.')
            return
        }

        if (documents.length === 0 && !docsLoading) {
            setError('No documents available to query. Please upload documents on the Documents page first.')
            return
        }

        // Format prior history turns (latest completed exchanges, max 6 messages, capped to limits)
        const historyPayload = normalizeConversationHistory(messages)

        // Cancel any in-flight request and generate a new request generation ID
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
        }
        const abortController = new AbortController()
        abortControllerRef.current = abortController
        const currentRequestId = ++activeRequestIdRef.current

        // Optimistically append user message to chat thread
        const userMsg = {
            id: `user-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
            role: 'user',
            content: queryText,
            timestamp: new Date().toISOString(),
        }

        setMessages((prev) => [...prev, userMsg])
        setQuestion('')
        setError('')
        setLoading(true)

        try {
            const data = await apiRequest(
                '/documents/ask',
                {
                    method: 'POST',
                    signal: abortController.signal,
                    body: JSON.stringify({
                        query: queryText,
                        document_id: null,
                        document_ids: scopeMode === 'specific' ? selectedDocIds : null,
                        top_k: 6,
                        conversation_history: historyPayload,
                    }),
                }
            )

            // Guard against stale response if scope changed or New Chat was triggered
            if (currentRequestId !== activeRequestIdRef.current) {
                return
            }

            const aiAnswer =
                data?.answer ||
                data?.response ||
                data?.result ||
                'No answer returned.'

            const sourcesList = Array.isArray(data?.results) ? data.results : []

            const asstMsg = {
                id: `asst-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
                role: 'assistant',
                content: aiAnswer,
                sources: sourcesList,
                timestamp: new Date().toISOString(),
            }

            setMessages((prev) => [...prev, asstMsg])
        } catch (err) {
            // If request was superseded or cancelled, ignore silently
            if (currentRequestId !== activeRequestIdRef.current) {
                return
            }
            if (err?.name === 'AbortError') {
                return
            }

            console.error('Ask AI error:', err)
            // Remove failed optimistic user message so it does not pollute the thread or subsequent history
            setMessages((prev) => prev.filter((m) => m.id !== userMsg.id))
            // Restore query text in textarea so user input is not lost
            setQuestion(queryText)
            setError(err.message || 'Failed to get an answer.')
        } finally {
            if (currentRequestId === activeRequestIdRef.current) {
                setLoading(false)
            }
        }
    }

    const handleSuggestedQuestion = (suggestion) => {
        if (loading || !suggestion) return
        handleAskAI(suggestion)
    }

    const handleCitationClick = (msgId, citationIndex) => {
        // Ensure sources drawer is open for this message so the card exists in DOM
        setExpandedSourcesDrawers((prev) => ({
            ...prev,
            [msgId]: true,
        }))
        setHighlightedCitation({ msgId, num: citationIndex })

        // Scroll to the specific source card
        setTimeout(() => {
            const targetId = `source-card-${msgId}-${citationIndex}`
            const element = document.getElementById(targetId)
            if (element) {
                element.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
                if (typeof element.focus === 'function') {
                    element.focus({ preventScroll: true })
                }
            }
        }, 50)
    }

    const toggleSourcesDrawer = (msgId) => {
        setExpandedSourcesDrawers((prev) => ({
            ...prev,
            [msgId]: !prev[msgId],
        }))
    }

    const toggleSourceExcerpt = (msgId, citationIndex) => {
        const key = `${msgId}-${citationIndex}`
        setExpandedSourceExcerpts((prev) => ({
            ...prev,
            [key]: !prev[key],
        }))
    }

    const handleCopyAnswer = async (msgId, text) => {
        if (!text) return
        try {
            if (navigator?.clipboard?.writeText) {
                await navigator.clipboard.writeText(text)
                setCopiedMsgId(msgId)
                setTimeout(() => setCopiedMsgId(null), 2000)
            }
        } catch (err) {
            console.error('Copy to clipboard failed:', err)
        }
    }

    const formatTimestamp = (isoString) => {
        if (!isoString) return ''
        try {
            const date = new Date(isoString)
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        } catch {
            return ''
        }
    }

    const renderInlineCitations = (text, sourceList, msgId) => {
        if (!text) return null

        const parts = text.split(/(\[\s*\d+(?:\s*,\s*\d+)*\s*\])/g)

        return parts.map((part, index) => {
            const bracketMatch = part.match(/^\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]$/)
            if (!bracketMatch) {
                return part
            }

            const rawNums = bracketMatch[1]
                .split(',')
                .map((s) => parseInt(s.trim(), 10))
                .filter((n) => !isNaN(n))

            if (rawNums.length === 0) {
                return part
            }

            return (
                <span key={`cite-group-${index}`} className="citation-group">
                    {rawNums.map((num, numIdx) => {
                        const matchingSource = sourceList?.find(
                            (s) => Number(s.citation_index) === num
                        )

                        if (!matchingSource) {
                            return (
                                <span key={`plain-${num}-${numIdx}`} className="citation-plain">
                                    [{num}]
                                </span>
                            )
                        }

                        const filename = matchingSource.filename || `Document #${matchingSource.document_id || num}`
                        const pageLabel = matchingSource.page_number != null
                            ? `Page ${matchingSource.page_number}`
                            : 'Page unavailable'

                        const isHighlighted =
                            highlightedCitation &&
                            highlightedCitation.msgId === msgId &&
                            highlightedCitation.num === num

                        return (
                            <button
                                key={`pill-${num}-${numIdx}`}
                                type="button"
                                className={`citation-pill ${isHighlighted ? 'citation-pill-active' : ''}`}
                                onClick={() => handleCitationClick(msgId, num)}
                                title={`View Source ${num}: ${filename} (${pageLabel})`}
                                aria-label={`Source ${num}: ${filename}, ${pageLabel}`}
                            >
                                <span className="citation-pill-bracket">[</span>
                                <span className="citation-pill-num">{num}</span>
                                <span className="citation-pill-bracket">]</span>
                            </button>
                        )
                    })}
                </span>
            )
        })
    }

    const renderFormattedAnswer = (answerText, sourceList, msgId) => {
        if (!answerText) return null

        const blocks = answerText
            .split(/\n\n+/)
            .map((b) => b.trim())
            .filter((b) => b.length > 0)

        return blocks.map((block, blockIdx) => {
            const lines = block
                .split('\n')
                .map((l) => l.trim())
                .filter((l) => l.length > 0)

            const isNumberedList = lines.length > 0 && lines.every((l) => /^\d+\.\s+/.test(l))
            if (isNumberedList) {
                return (
                    <ol key={`ol-${blockIdx}`} className="answer-list">
                        {lines.map((line, lineIdx) => {
                            const cleanLine = line.replace(/^\d+\.\s+/, '')
                            return (
                                <li key={`li-${lineIdx}`} className="answer-list-item">
                                    {renderInlineCitations(cleanLine, sourceList, msgId)}
                                </li>
                            )
                        })}
                    </ol>
                )
            }

            const isBulletList = lines.length > 0 && lines.every((l) => /^[-*•]\s+/.test(l))
            if (isBulletList) {
                return (
                    <ul key={`ul-${blockIdx}`} className="answer-list">
                        {lines.map((line, lineIdx) => {
                            const cleanLine = line.replace(/^[-*•]\s+/, '')
                            return (
                                <li key={`li-${lineIdx}`} className="answer-list-item">
                                    {renderInlineCitations(cleanLine, sourceList, msgId)}
                                </li>
                            )
                        })}
                    </ul>
                )
            }

            return (
                <p key={`p-${blockIdx}`} className="answer-paragraph">
                    {lines.map((line, lineIdx) => (
                        <span key={`line-${lineIdx}`}>
                            {lineIdx > 0 && <br />}
                            {renderInlineCitations(line, sourceList, msgId)}
                        </span>
                    ))}
                </p>
            )
        })
    }

    return (
        <main className="ask-ai-page chat-layout-page">
            {/* =================================
                COMPACT CHAT TOPBAR
            ================================= */}
            <header className="chat-topbar" aria-label="Ask AI Toolbar">
                <div className="chat-topbar-left">
                    <div className="chat-title-group">
                        <span className="chat-title-icon" aria-hidden="true">✦</span>
                        <h2 className="chat-title">Ask AI</h2>
                        <span className="chat-scope-badge">Grounded Reasoning</span>
                    </div>

                    {/* Compact Knowledge Scope Bar */}
                    <div className="compact-scope-bar" role="radiogroup" aria-label="Knowledge Scope">
                        <button
                            type="button"
                            role="radio"
                            aria-checked={scopeMode === 'all'}
                            className={`compact-scope-pill ${scopeMode === 'all' ? 'active' : ''}`}
                            onClick={() => handleScopeModeChange('all')}
                            disabled={loading}
                        >
                            <span className="scope-pill-icon" aria-hidden="true">🌐</span>
                            <span>All Documents</span>
                            {documents.length > 0 && (
                                <span className="scope-count-badge">{documents.length}</span>
                            )}
                        </button>

                        <button
                            type="button"
                            role="radio"
                            aria-checked={scopeMode === 'specific'}
                            className={`compact-scope-pill ${scopeMode === 'specific' ? 'active' : ''}`}
                            onClick={() => handleScopeModeChange('specific')}
                            disabled={loading}
                        >
                            <span className="scope-pill-icon" aria-hidden="true">📑</span>
                            <span>Specific</span>
                            {selectedDocIds.length > 0 && (
                                <span className="scope-count-badge scope-count-active">
                                    {selectedDocIds.length}
                                </span>
                            )}
                        </button>

                        {scopeMode === 'specific' && (
                            <button
                                type="button"
                                className={`scope-picker-toggle-btn ${isDocPickerOpen ? 'open' : ''}`}
                                onClick={() => setIsDocPickerOpen((prev) => !prev)}
                                disabled={loading}
                                title="Toggle document selection panel"
                                aria-expanded={isDocPickerOpen}
                            >
                                <span>{selectedDocIds.length} of {documents.length} selected</span>
                                <span className="dropdown-caret" aria-hidden="true">{isDocPickerOpen ? '▴' : '▾'}</span>
                            </button>
                        )}
                    </div>
                </div>

                <div className="chat-topbar-right">
                    {messages.length > 0 && (
                        <button
                            type="button"
                            className="chat-new-chat-btn"
                            onClick={handleNewChat}
                            disabled={loading}
                            title="Clear conversation and start a new inquiry"
                            aria-label="Start a new chat"
                        >
                            <span className="new-chat-plus" aria-hidden="true">+</span>
                            <span>New Chat</span>
                        </button>
                    )}
                </div>
            </header>

            {/* =================================
                COLLAPSIBLE DOCUMENT SELECTOR PANEL
            ================================= */}
            {scopeMode === 'specific' && isDocPickerOpen && (
                <section className="scope-picker-panel" aria-label="Select Documents for AI Scope">
                    <div className="scope-picker-header">
                        <span className="scope-picker-title">
                            Select documents to ground your inquiry ({selectedDocIds.length} of {documents.length} selected)
                        </span>
                        <div className="scope-picker-actions">
                            <button
                                type="button"
                                className="scope-chip-btn"
                                onClick={handleSelectAllDocs}
                                disabled={loading || selectedDocIds.length === documents.length}
                            >
                                Select All
                            </button>
                            <button
                                type="button"
                                className="scope-chip-btn"
                                onClick={handleClearDocs}
                                disabled={loading || selectedDocIds.length === 0}
                            >
                                Clear
                            </button>
                            <button
                                type="button"
                                className="scope-chip-btn scope-chip-close"
                                onClick={() => setIsDocPickerOpen(false)}
                            >
                                Done ✓
                            </button>
                        </div>
                    </div>

                    {documents.length === 0 ? (
                        <p className="scope-picker-empty">
                            No documents found. Please upload documents on the{' '}
                            <Link to="/documents" className="scope-link">Documents</Link> page.
                        </p>
                    ) : (
                        <div className="scope-picker-grid" role="group" aria-label="Selectable documents">
                            {documents.map((doc) => {
                                const isSelected = selectedDocIds.includes(doc.id)
                                const typeBadge = getFileTypeBadge(doc)
                                return (
                                    <label
                                        key={doc.id}
                                        className={`scope-picker-item ${isSelected ? 'selected' : ''} ${loading ? 'disabled' : ''}`}
                                    >
                                        <input
                                            type="checkbox"
                                            className="scope-picker-checkbox"
                                            checked={isSelected}
                                            onChange={() => handleToggleDoc(doc.id)}
                                            disabled={loading}
                                            aria-label={`Select ${doc.filename}`}
                                        />
                                        <span className="scope-picker-doc-icon" aria-hidden="true">
                                            {getFileIcon(typeBadge)}
                                        </span>
                                        <span className="scope-picker-doc-name" title={doc.filename}>
                                            {doc.filename}
                                        </span>
                                        <span className="scope-picker-badge">{typeBadge}</span>
                                    </label>
                                )
                            })}
                        </div>
                    )}

                    {selectedDocIds.length === 0 && (
                        <p className="scope-picker-warning" role="alert">
                            ⚠️ Please select at least one document to ask a question.
                        </p>
                    )}
                </section>
            )}

            {/* Document repository loading / error alerts */}
            {docsLoading && (
                <div className="scope-status-banner">
                    <span className="scope-spinner" aria-hidden="true"></span>
                    <span>Connecting to document repository...</span>
                </div>
            )}

            {docsError && (
                <div className="scope-status-banner scope-status-error" role="alert">
                    <span>⚠️ {docsError}</span>
                    <button type="button" className="scope-retry-link" onClick={fetchDocuments}>
                        Retry
                    </button>
                </div>
            )}

            {!docsLoading && !docsError && documents.length === 0 && (
                <div className="scope-status-banner scope-status-empty" role="alert">
                    <span>📂 No documents uploaded yet.</span>
                    <Link to="/documents" className="scope-retry-link">Upload documents</Link>
                </div>
            )}

            {/* =================================
                CHAT SCROLL CONTAINER & THREAD
            ================================= */}
            <div className="chat-scroll-container">
                {/* EMPTY STATE */}
                {messages.length === 0 && !loading && (
                    <section className="chat-empty-state" aria-label="Ask AI overview">
                        <div className="chat-empty-glow-icon" aria-hidden="true">✦</div>
                        <h3 className="chat-empty-title">Cognidocs Intelligence Ready</h3>
                        <p className="chat-empty-desc">
                            Ask anything about your uploaded documents. Cognidocs AI retrieves exact passages and formulates context-grounded answers with traceable citations.
                        </p>

                        <div className="chat-suggestions-wrap">
                            <span className="chat-suggestions-label">
                                {scopeMode === 'specific' ? 'Document Suggestions' : 'Collection Inquiries'}
                            </span>
                            {suggestionsLoading ? (
                                <div className="chat-suggestions-loading" aria-label="Generating document-aware suggestions">
                                    <span className="suggestion-spinner" aria-hidden="true"></span>
                                    <span className="suggestion-loading-text">Generating document-aware suggestions...</span>
                                </div>
                            ) : scopeMode === 'specific' && selectedDocIds.length === 0 ? (
                                <p className="chat-suggestions-hint">
                                    Select one or more documents above to generate tailored inquiry suggestions.
                                </p>
                            ) : suggestedQuestions.length > 0 ? (
                                <div className="chat-suggestions-chips">
                                    {suggestedQuestions.map((suggestion) => (
                                        <button
                                            key={suggestion}
                                            type="button"
                                            className="chat-suggestion-chip"
                                            onClick={() => handleSuggestedQuestion(suggestion)}
                                            disabled={loading}
                                            title={`Ask: "${suggestion}"`}
                                        >
                                            <span className="suggestion-sparkle" aria-hidden="true">✨</span>
                                            <span>{suggestion}</span>
                                        </button>
                                    ))}
                                </div>
                            ) : !docsLoading && documents.length > 0 ? (
                                <p className="chat-suggestions-hint">
                                    Ask any question about your documents in the composer below.
                                </p>
                            ) : null}
                        </div>
                    </section>
                )}

                {/* CONVERSATION MESSAGES */}
                {messages.length > 0 && (
                    <div className="chat-thread-container" aria-label="Conversation thread">
                        {messages.map((msg, idx) => {
                            if (msg.role === 'user') {
                                return (
                                    <div key={msg.id} className="chat-row chat-row-user">
                                        <div className="chat-bubble-user" tabIndex={0}>
                                            <p className="chat-user-text">{msg.content}</p>
                                            <span className="chat-user-time">
                                                {formatTimestamp(msg.timestamp)}
                                            </span>
                                        </div>
                                    </div>
                                )
                            }

                            // Assistant message
                            const sortedSources = Array.isArray(msg.sources)
                                ? [...msg.sources].sort(
                                      (a, b) => (Number(a.citation_index) || 0) - (Number(b.citation_index) || 0)
                                  )
                                : []

                            const isDrawerExpanded = Boolean(expandedSourcesDrawers[msg.id])

                            return (
                                <div key={msg.id} className="chat-row chat-row-assistant">
                                    <div className="assistant-avatar" aria-hidden="true">
                                        <span>✦</span>
                                    </div>

                                    <div className="assistant-bubble-column">
                                        <article
                                            className="chat-bubble-assistant"
                                            aria-label={`Assistant response ${idx + 1}`}
                                        >
                                            <div className="assistant-body">
                                                {renderFormattedAnswer(msg.content, msg.sources, msg.id)}
                                            </div>

                                            <div className="assistant-bubble-footer">
                                                <span className="assistant-time">
                                                    {formatTimestamp(msg.timestamp)}
                                                </span>
                                                <button
                                                    type="button"
                                                    className="assistant-copy-btn"
                                                    onClick={() => handleCopyAnswer(msg.id, msg.content)}
                                                    aria-label="Copy answer text"
                                                >
                                                    {copiedMsgId === msg.id ? 'Copied ✨' : 'Copy'}
                                                </button>
                                            </div>
                                        </article>

                                        {/* UNIFIED COMPACT SOURCES DRAWER */}
                                        {sortedSources.length > 0 && (
                                            <div className="chat-sources-container">
                                                <button
                                                    type="button"
                                                    className={`sources-drawer-btn ${isDrawerExpanded ? 'expanded' : ''}`}
                                                    onClick={() => toggleSourcesDrawer(msg.id)}
                                                    aria-expanded={isDrawerExpanded}
                                                    title="Toggle verified supporting source excerpts"
                                                >
                                                    <span className="sources-drawer-icon" aria-hidden="true">📚</span>
                                                    <span className="sources-drawer-label">
                                                        {sortedSources.length}{' '}
                                                        {sortedSources.length === 1 ? 'Source referenced' : 'Sources referenced'}
                                                    </span>
                                                    <span className="sources-drawer-arrow" aria-hidden="true">
                                                        {isDrawerExpanded ? '▴ Hide' : '▾ View details'}
                                                    </span>
                                                </button>

                                                {isDrawerExpanded && (
                                                    <div className="sources-cards-list">
                                                        {sortedSources.map((source, sIdx) => {
                                                            const citeNum = source.citation_index || (sIdx + 1)
                                                            const isHighlighted =
                                                                highlightedCitation &&
                                                                highlightedCitation.msgId === msg.id &&
                                                                highlightedCitation.num === citeNum
                                                            const excerptKey = `${msg.id}-${citeNum}`
                                                            const isExpanded = Boolean(expandedSourceExcerpts[excerptKey])

                                                            const filename =
                                                                source.filename || `Document #${source.document_id || citeNum}`
                                                            const pageLabel =
                                                                source.page_number != null
                                                                    ? `Page ${source.page_number}`
                                                                    : 'Page N/A'
                                                            const contentText =
                                                                source.content || source.text || 'No text excerpt available.'
                                                            const needsTruncation = contentText.length > 220
                                                            const displayText =
                                                                !needsTruncation || isExpanded
                                                                    ? contentText
                                                                    : `${contentText.slice(0, 220)}...`

                                                            const similarityScore =
                                                                typeof source.similarity === 'number' && !isNaN(source.similarity)
                                                                    ? Math.round(source.similarity * 100)
                                                                    : typeof source.score === 'number' && !isNaN(source.score)
                                                                    ? Math.round(source.score * 100)
                                                                    : null

                                                            return (
                                                                <article
                                                                    key={`src-${msg.id}-${source.chunk_id || source.id || citeNum}`}
                                                                    id={`source-card-${msg.id}-${citeNum}`}
                                                                    className={`compact-source-card ${
                                                                        isHighlighted ? 'source-card-highlighted' : ''
                                                                    }`}
                                                                    tabIndex={0}
                                                                    aria-label={`Source ${citeNum}: ${filename}, ${pageLabel}`}
                                                                >
                                                                    <div className="source-card-topbar">
                                                                        <div className="source-meta-group">
                                                                            <span className="source-idx-pill">
                                                                                [{citeNum}]
                                                                            </span>
                                                                            <span className="source-name" title={filename}>
                                                                                📄 {filename}
                                                                            </span>
                                                                            <span className="source-page-badge">
                                                                                {pageLabel}
                                                                            </span>
                                                                            {similarityScore !== null && (
                                                                                <span
                                                                                    className="source-sim-chip"
                                                                                    title="Semantic retrieval relevance indicator"
                                                                                >
                                                                                    {similarityScore}% match
                                                                                </span>
                                                                            )}
                                                                        </div>

                                                                        {needsTruncation && (
                                                                            <button
                                                                                type="button"
                                                                                className="source-expand-btn"
                                                                                onClick={() => toggleSourceExcerpt(msg.id, citeNum)}
                                                                                aria-expanded={isExpanded}
                                                                            >
                                                                                {isExpanded ? 'Less ▴' : 'More ▾'}
                                                                            </button>
                                                                        )}
                                                                    </div>

                                                                    <p className="source-excerpt-text">
                                                                        {displayText}
                                                                    </p>
                                                                </article>
                                                            )
                                                        })}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )
                        })}

                        {/* SYNTHESIZING TYPING INDICATOR */}
                        {loading && (
                            <div className="chat-row chat-row-assistant chat-row-loading">
                                <div className="assistant-avatar assistant-avatar-pulse" aria-hidden="true">
                                    <span>✦</span>
                                </div>
                                <div className="assistant-bubble-column">
                                    <div className="chat-bubble-assistant chat-bubble-loading">
                                        <div className="chat-typing-dots" aria-label="Synthesizing response">
                                            <span></span>
                                            <span></span>
                                            <span></span>
                                        </div>
                                        <span className="chat-loading-hint">
                                            Scanning document chunks & synthesizing grounded answer...
                                        </span>
                                    </div>
                                </div>
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>
                )}

                {/* Initial loading state when messages array is empty */}
                {messages.length === 0 && loading && (
                    <div className="chat-thread-container">
                        <div className="chat-row chat-row-assistant chat-row-loading">
                            <div className="assistant-avatar assistant-avatar-pulse" aria-hidden="true">
                                <span>✦</span>
                            </div>
                            <div className="assistant-bubble-column">
                                <div className="chat-bubble-assistant chat-bubble-loading">
                                    <div className="chat-typing-dots" aria-label="Synthesizing response">
                                        <span></span>
                                        <span></span>
                                        <span></span>
                                    </div>
                                    <span className="chat-loading-hint">
                                        Scanning document chunks & synthesizing grounded answer...
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* =================================
                MODERN CHAT COMPOSER DOCK
            ================================= */}
            <footer className="chat-composer-wrapper">
                {error && (
                    <div className="chat-error-toast" role="alert">
                        <span className="error-icon" aria-hidden="true">⚠️</span>
                        <span className="error-text">{error}</span>
                        <button
                            type="button"
                            className="error-dismiss-btn"
                            onClick={() => setError('')}
                            aria-label="Dismiss error notification"
                        >
                            ✕
                        </button>
                    </div>
                )}

                <div className={`chat-composer-box ${loading ? 'composer-disabled' : ''}`}>
                    <textarea
                        ref={textareaRef}
                        className="composer-textarea"
                        placeholder={
                            messages.length > 0
                                ? 'Ask a follow-up (e.g., "What are its types?", "Explain the second one")...'
                                : 'Ask anything about your uploaded documents...'
                        }
                        value={question}
                        onChange={(event) => setQuestion(event.target.value)}
                        onKeyDown={(event) => {
                            if (event.key === 'Enter' && !event.shiftKey) {
                                event.preventDefault()
                                if (!isSubmitDisabled) {
                                    handleAskAI()
                                }
                            }
                        }}
                        disabled={loading}
                        rows={1}
                        aria-label="Ask a question about your documents"
                    />

                    <div className="composer-bottom-bar">
                        <div className="composer-info-left">
                            <span className="composer-key-hint">
                                <strong>Enter</strong> to ask · <strong>Shift + Enter</strong> for line break
                            </span>
                            {!docsLoading && documents.length > 0 && (
                                <span className="composer-scope-tag">
                                    {scopeMode === 'all'
                                        ? `Scope: All (${documents.length})`
                                        : `Scope: ${selectedDocIds.length} Selected`}
                                </span>
                            )}
                        </div>

                        <button
                            type="button"
                            className="composer-send-button"
                            onClick={handleAskAI}
                            disabled={isSubmitDisabled}
                            title="Send inquiry"
                            aria-label="Send inquiry"
                        >
                            {loading ? (
                                <span className="send-spinner" aria-hidden="true"></span>
                            ) : (
                                <span className="send-icon" aria-hidden="true">↑</span>
                            )}
                        </button>
                    </div>
                </div>
            </footer>
        </main>
    )
}

export default AskAI
