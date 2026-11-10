import { useState, useEffect, useRef } from 'react'
import {
    MessageSquare,
    Send,
    Trash2,
    Sparkles,
    Bot,
    User as UserIcon,
    AlertTriangle,
    BookOpen,
    Quote,
    RefreshCw
} from 'lucide-react'
import { apiRequest } from '../../services/api'

export default function HandwrittenChatTab({ documentId, transcriptionUpdated }) {
    const [messages, setMessages] = useState([])
    const [inputQuestion, setInputQuestion] = useState('')
    const [loading, setLoading] = useState(false)
    const [sending, setSending] = useState(false)
    const [error, setError] = useState(null)
    const [clearing, setClearing] = useState(false)
    const messagesEndRef = useRef(null)

    // Load chat history
    const fetchHistory = async () => {
        try {
            setLoading(true)
            setError(null)
            const res = await apiRequest(`/handwritten/${documentId}/chat/history`)
            setMessages(res?.messages || [])
        } catch (err) {
            console.error('Fetch chat history error:', err)
            setError(err.message || 'Failed to load chat history.')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (documentId) {
            fetchHistory()
        }
    }, [documentId, transcriptionUpdated])

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, sending])

    // Send question to RAG
    const handleSendMessage = async (textToSend) => {
        const query = (textToSend || inputQuestion).trim()
        if (!query || sending) return

        setInputQuestion('')
        const tempUserMsg = {
            id: 'temp_' + Date.now(),
            role: 'user',
            content: query,
            created_at: new Date().toISOString()
        }
        setMessages(prev => [...prev, tempUserMsg])

        try {
            setSending(true)
            setError(null)
            const res = await apiRequest(`/handwritten/${documentId}/chat/message`, {
                method: 'POST',
                body: JSON.stringify({ question: query })
            })

            const assistantMsg = {
                id: 'asst_' + Date.now(),
                role: 'assistant',
                content: res?.answer || '',
                sources: res?.sources || [],
                created_at: new Date().toISOString()
            }
            setMessages(prev => [...prev, assistantMsg])
        } catch (err) {
            console.error('Chat error:', err)
            setError(err.message || 'Failed to get answer.')
        } finally {
            setSending(false)
        }
    }

    // Clear history
    const handleClearChat = async () => {
        if (!window.confirm('Clear all conversation messages for this document?')) return
        try {
            setClearing(true)
            await apiRequest(`/handwritten/${documentId}/chat/history`, {
                method: 'DELETE'
            })
            setMessages([])
        } catch (err) {
            console.error('Clear chat error:', err)
        } finally {
            setClearing(false)
        }
    }

    const starterQuestions = [
        "Summarize the central ideas discussed in these notes",
        "What are the main formulas or definitions?",
        "Are there any specific examples or key takeaways?",
        "Explain the most complex point in simple terms"
    ]

    return (
        <div className="intel-chat-container">
            {/* Chat Header Toolbar */}
            <div className="intel-chat-header">
                <div className="chat-header-info">
                    <span className="chat-ai-pill">
                        <Sparkles size={12} />
                        <span>Grounded Tutor (Llama 3.2 + MiniLM)</span>
                    </span>
                    <span className="chat-doc-info">
                        Answers strictly cite your handwritten pages
                    </span>
                </div>
                {messages.length > 0 && (
                    <button
                        type="button"
                        className="btn-clear-chat"
                        onClick={handleClearChat}
                        disabled={clearing}
                        title="Clear conversation history"
                    >
                        <Trash2 size={13} />
                        <span>Clear Chat</span>
                    </button>
                )}
            </div>

            {/* Error Banner */}
            {error && (
                <div className="intel-error-banner">
                    <div className="intel-error-content">
                        <AlertTriangle size={16} />
                        <span>{error}</span>
                    </div>
                    {messages.length > 0 && messages[messages.length - 1].role === 'user' && (
                        <button
                            type="button"
                            className="btn-intel-retry"
                            onClick={() => handleSend(messages[messages.length - 1].content)}
                            disabled={sending}
                        >
                            <RefreshCw size={12} className={sending ? 'spin-icon' : ''} />
                            <span>Retry</span>
                        </button>
                    )}
                </div>
            )}

            {/* Messages Thread */}
            <div className="intel-chat-messages-area">
                {messages.length === 0 && !loading && (
                    <div className="chat-starter-container">
                        <div className="chat-starter-orb">
                            <Bot size={36} style={{ color: 'var(--cyan-ink)' }} />
                        </div>
                        <h3>Ask Questions About Your Notes</h3>
                        <p>
                            Cognidocs AI searches and cites your handwritten transcription directly.
                            Try asking one of the suggested prompts below:
                        </p>
                        <div className="starter-prompts-grid">
                            {starterQuestions.map((q, idx) => (
                                <button
                                    key={idx}
                                    type="button"
                                    className="starter-prompt-card"
                                    onClick={() => handleSendMessage(q)}
                                >
                                    <Sparkles size={12} className="prompt-sparkle" />
                                    <span>{q}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((msg, idx) => {
                    const isUser = msg.role === 'user'
                    return (
                        <div key={msg.id || idx} className={`chat-message-bubble ${isUser ? 'user-bubble' : 'asst-bubble'}`}>
                            <div className="bubble-avatar">
                                {isUser ? <UserIcon size={14} /> : <Bot size={14} />}
                            </div>
                            <div className="bubble-content-wrap">
                                <div className="bubble-text">{msg.content}</div>

                                {/* Citations / Sources */}
                                {!isUser && msg.sources && msg.sources.length > 0 && (
                                    <div className="bubble-sources-panel">
                                        <div className="sources-header">
                                            <BookOpen size={11} />
                                            <span>Grounding Sources ({msg.sources.length})</span>
                                        </div>
                                        <div className="sources-list">
                                            {msg.sources.map((s, sIdx) => (
                                                <div key={sIdx} className="source-pill-card">
                                                    <span className="source-page-badge">Page {s.page_number}</span>
                                                    <span className="source-excerpt-snippet">"{s.excerpt}"</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )
                })}

                {/* Sending Indicator */}
                {sending && (
                    <div className="chat-message-bubble asst-bubble">
                        <div className="bubble-avatar">
                            <Bot size={14} />
                        </div>
                        <div className="bubble-content-wrap">
                            <div className="chat-typing-indicator">
                                <span className="typing-dot" />
                                <span className="typing-dot" />
                                <span className="typing-dot" />
                                <span className="typing-label">Searching notes & reasoning...</span>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Bar */}
            <form
                className="intel-chat-input-bar"
                onSubmit={(e) => {
                    e.preventDefault()
                    handleSendMessage()
                }}
            >
                <input
                    type="text"
                    className="chat-text-input"
                    placeholder="Ask anything about these handwritten notes..."
                    value={inputQuestion}
                    onChange={(e) => setInputQuestion(e.target.value)}
                    disabled={sending}
                />
                <button
                    type="submit"
                    className="btn-send-chat"
                    disabled={!inputQuestion.trim() || sending}
                >
                    <Send size={15} />
                </button>
            </form>
        </div>
    )
}

