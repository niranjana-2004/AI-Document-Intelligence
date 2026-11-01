import { useState, useEffect, useCallback } from 'react'
import {
    Layers,
    Sparkles,
    Check,
    RotateCw,
    Shuffle,
    ArrowLeft,
    ArrowRight,
    AlertTriangle,
    RefreshCw,
    CheckCircle2,
    Clock,
    X,
    Eye
} from 'lucide-react'
import { apiRequest } from '../../services/api'

export default function HandwrittenFlashcardsTab({ documentId, transcriptionUpdated }) {
    const [decks, setDecks] = useState([])
    const [activeDeckId, setActiveDeckId] = useState(null)
    const [currentCardIdx, setCurrentCardIdx] = useState(0)
    const [isFlipped, setIsFlipped] = useState(false)
    const [generating, setGenerating] = useState(false)
    const [cardCount, setCardCount] = useState(8)
    const [showConfig, setShowConfig] = useState(false)
    const [error, setError] = useState(null)

    // Load decks
    const fetchDecks = async () => {
        try {
            setError(null)
            const res = await apiRequest(`/handwritten/${documentId}/flashcards`)
            const list = res?.decks || []
            setDecks(list)
            if (list.length > 0 && !activeDeckId) {
                setActiveDeckId(list[0].id)
            }
        } catch (err) {
            console.error('Fetch flashcards error:', err)
            setError(err.message || 'Failed to load flashcards.')
        }
    }

    useEffect(() => {
        if (documentId) {
            fetchDecks()
        }
    }, [documentId, transcriptionUpdated])

    const activeDeck = decks.find(d => d.id === activeDeckId) || null
    const cards = activeDeck?.cards || []
    const currentCard = cards[currentCardIdx] || null

    // Reset flip when switching cards
    useEffect(() => {
        setIsFlipped(false)
    }, [currentCardIdx, activeDeckId])

    // Generate new deck
    const handleGenerateDeck = async () => {
        try {
            setGenerating(true)
            setError(null)
            setShowConfig(false)
            const res = await apiRequest(`/handwritten/${documentId}/flashcards/generate`, {
                method: 'POST',
                body: JSON.stringify({ card_count: cardCount })
            })
            const newDeck = res?.deck
            if (newDeck) {
                setDecks(prev => [newDeck, ...prev])
                setActiveDeckId(newDeck.id)
                setCurrentCardIdx(0)
            }
        } catch (err) {
            console.error('Flashcard generate error:', err)
            setError(err.message || 'Failed to generate flashcard deck.')
        } finally {
            setGenerating(false)
        }
    }

    // Toggle card learning status
    const handleUpdateCardStatus = async (status) => {
        if (!activeDeck || !currentCard) return
        try {
            // Optimistic update
            setDecks(prev => prev.map(d => {
                if (d.id !== activeDeck.id) return d
                const updatedCards = d.cards.map(c => {
                    if (c.id === currentCard.id) {
                        return {
                            ...c,
                            known: status === 'known',
                            needs_review: status === 'needs_review'
                        }
                    }
                    return c
                })
                const knownCount = updatedCards.filter(c => c.known).length
                const reviewCount = updatedCards.filter(c => c.needs_review).length
                return { ...d, cards: updatedCards, known_count: knownCount, needs_review_count: reviewCount }
            }))

            await apiRequest(`/handwritten/${documentId}/flashcards/${activeDeck.id}/cards/${currentCard.id}`, {
                method: 'PATCH',
                body: JSON.stringify({ status })
            })

            // Auto-advance to next card if not at end
            if (currentCardIdx < cards.length - 1) {
                setTimeout(() => {
                    setCurrentCardIdx(prev => prev + 1)
                }, 250)
            }
        } catch (err) {
            console.error('Update card error:', err)
        }
    }

    // Reset deck statuses
    const handleResetDeck = async () => {
        if (!activeDeck) return
        try {
            setDecks(prev => prev.map(d => {
                if (d.id !== activeDeck.id) return d
                const resetCards = d.cards.map(c => ({ ...c, known: false, needs_review: false }))
                return { ...d, cards: resetCards, known_count: 0, needs_review_count: 0 }
            }))
            await apiRequest(`/handwritten/${documentId}/flashcards/${activeDeck.id}/reset`, {
                method: 'POST'
            })
            setCurrentCardIdx(0)
        } catch (err) {
            console.error('Reset deck error:', err)
        }
    }

    // Shuffle cards in current deck
    const handleShuffle = () => {
        if (!activeDeck) return
        const shuffled = [...cards].sort(() => Math.random() - 0.5)
        setDecks(prev => prev.map(d => d.id === activeDeck.id ? { ...d, cards: shuffled } : d))
        setCurrentCardIdx(0)
        setIsFlipped(false)
    }

    // Keyboard navigation
    const handleKeyDown = useCallback((e) => {
        if (showConfig || generating) return
        if (e.key === ' ' || e.code === 'Space') {
            e.preventDefault()
            setIsFlipped(prev => !prev)
        } else if (e.key === 'ArrowRight') {
            setCurrentCardIdx(prev => Math.min(cards.length - 1, prev + 1))
        } else if (e.key === 'ArrowLeft') {
            setCurrentCardIdx(prev => Math.max(0, prev - 1))
        }
    }, [cards.length, showConfig, generating])

    useEffect(() => {
        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [handleKeyDown])

    const knownCount = activeDeck?.known_count || 0
    const reviewCount = activeDeck?.needs_review_count || 0
    const totalCount = cards.length

    return (
        <div className="intel-tab-container">
            {/* Toolbar */}
            <div className="intel-toolbar">
                <div className="flashcard-deck-select-group">
                    {decks.length > 0 && (
                        <select
                            className="quiz-dropdown-select"
                            value={activeDeckId || ''}
                            onChange={(e) => setActiveDeckId(Number(e.target.value))}
                        >
                            {decks.map((d, idx) => (
                                <option key={d.id} value={d.id}>
                                    Deck #{decks.length - idx}: {d.title} ({d.cards?.length || 0} cards)
                                </option>
                            ))}
                        </select>
                    )}
                </div>

                <div className="intel-actions-group">
                    {activeDeck && (
                        <>
                            <button
                                type="button"
                                className="btn-studio-action"
                                onClick={handleShuffle}
                                title="Shuffle cards"
                            >
                                <Shuffle size={13} />
                                <span>Shuffle</span>
                            </button>
                            <button
                                type="button"
                                className="btn-studio-action"
                                onClick={handleResetDeck}
                                title="Reset learning progress"
                            >
                                <RotateCw size={13} />
                                <span>Reset</span>
                            </button>
                        </>
                    )}
                    <button
                        type="button"
                        className="btn-studio-action btn-studio-primary"
                        onClick={() => setShowConfig(true)}
                        disabled={generating}
                    >
                        <Sparkles size={13} className={generating ? 'spin-icon' : ''} />
                        <span>{generating ? 'Synthesizing...' : 'New Deck'}</span>
                    </button>
                </div>
            </div>

            {/* Config Card */}
            {showConfig && (
                <div className="quiz-config-card">
                    <div className="config-header">
                        <h4>Create Flashcard Deck</h4>
                        <button type="button" className="config-close-btn" onClick={() => setShowConfig(false)}>×</button>
                    </div>
                    <div className="config-grid">
                        <div className="config-field">
                            <label>Number of Flashcards</label>
                            <div className="config-pills">
                                {[5, 8, 12, 16].map(num => (
                                    <button
                                        key={num}
                                        type="button"
                                        className={`config-pill ${cardCount === num ? 'active' : ''}`}
                                        onClick={() => setCardCount(num)}
                                    >
                                        {num} Cards
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                    <div className="config-actions">
                        <button
                            type="button"
                            className="btn-intel-primary"
                            onClick={handleGenerateDeck}
                            disabled={generating}
                        >
                            <Sparkles size={14} />
                            <span>Generate Deck ({cardCount} Cards)</span>
                        </button>
                    </div>
                </div>
            )}

            {/* Outdated Notice */}
            {activeDeck && activeDeck.is_outdated && (
                <div className="intel-outdated-banner">
                    <div className="outdated-content">
                        <AlertTriangle size={18} className="outdated-icon" />
                        <div>
                            <strong>Transcription Modified</strong>
                            <p>Handwriting has changed. Create an updated deck to align with current notes.</p>
                        </div>
                    </div>
                    <button
                        type="button"
                        className="btn-outdated-regen"
                        onClick={handleGenerateDeck}
                        disabled={generating}
                    >
                        <RefreshCw size={12} className={generating ? 'spin-icon' : ''} />
                        <span>Regenerate Deck</span>
                    </button>
                </div>
            )}

            {/* Error */}
            {error && (
                <div className="intel-error-banner">
                    <AlertTriangle size={16} />
                    <span>{error}</span>
                </div>
            )}

            {/* Generating Loader */}
            {generating && (
                <div className="intel-generating-card">
                    <div className="intel-spinner-orb">
                        <Layers size={28} className="spin-icon" style={{ color: '#c084fc' }} />
                    </div>
                    <h4>Generating Active Recall Flashcards...</h4>
                    <p>Distilling formulas, key concepts, and high-yield questions from transcribed pages with Llama 3.2.</p>
                    <div className="intel-progress-bar-wrap">
                        <div className="intel-progress-bar-fill" />
                    </div>
                </div>
            )}

            {/* Empty State */}
            {!generating && decks.length === 0 && (
                <div className="intel-empty-card">
                    <div className="empty-icon-wrap" style={{ background: 'rgba(168, 85, 247, 0.15)', borderColor: 'rgba(168, 85, 247, 0.3)' }}>
                        <Layers size={40} style={{ color: '#a855f7' }} />
                    </div>
                    <h3>Active Recall 3D Flashcards</h3>
                    <p>
                        Master handwritten lecture notes using spaced repetition and 3D flip flashcards.
                        Track cards as "Mastered" or "Needs Review".
                    </p>
                    <button
                        type="button"
                        className="btn-intel-primary"
                        onClick={() => setShowConfig(true)}
                        style={{ background: 'linear-gradient(135deg, #8b5cf6, #3b82f6)' }}
                    >
                        <Sparkles size={16} />
                        <span>Generate First Deck</span>
                    </button>
                </div>
            )}

            {/* Interactive Flashcard 3D Stage */}
            {!generating && activeDeck && currentCard && (
                <div className="flashcard-stage-container">
                    {/* Stats Progress Bar */}
                    <div className="flashcard-stats-row">
                        <div className="stat-pill-item">
                            <span className="stat-label">Card:</span>
                            <span className="stat-num">{currentCardIdx + 1} / {totalCount}</span>
                        </div>
                        <div className="stat-pill-item mastered">
                            <CheckCircle2 size={13} />
                            <span>{knownCount} Mastered</span>
                        </div>
                        <div className="stat-pill-item review">
                            <Clock size={13} />
                            <span>{reviewCount} Needs Review</span>
                        </div>
                        <span className="page-citation-pill">Page {currentCard.page_number}</span>
                    </div>

                    {/* Progress Track */}
                    <div className="flashcard-progress-track">
                        <div
                            className="flashcard-progress-indicator"
                            style={{ width: `${((currentCardIdx + 1) / totalCount) * 100}%` }}
                        />
                    </div>

                    {/* 3D Flip Card Container */}
                    <div
                        className={`flashcard-scene ${isFlipped ? 'flipped' : ''}`}
                        onClick={() => setIsFlipped(!isFlipped)}
                    >
                        <div className="flashcard-flipper">
                            {/* FRONT SIDE */}
                            <div className="flashcard-face flashcard-front">
                                <div className="card-face-header">
                                    <span className="card-side-tag">PROMPT / QUESTION</span>
                                    <span className="card-flip-hint">Click or Space to Flip</span>
                                </div>
                                <div className="card-body-content">
                                    <h3 className="card-prompt-text">{currentCard.front}</h3>
                                </div>
                                <div className="card-face-footer">
                                    <div className="card-status-badges">
                                        {currentCard.known && <span className="status-badge known">✓ Mastered</span>}
                                        {currentCard.needs_review && <span className="status-badge review">⚠️ Needs Review</span>}
                                    </div>
                                    <div className="flip-prompt-indicator">
                                        <RotateCw size={13} />
                                        <span>Flip to Answer</span>
                                    </div>
                                </div>
                            </div>

                            {/* BACK SIDE */}
                            <div className="flashcard-face flashcard-back">
                                <div className="card-face-header">
                                    <span className="card-side-tag back-tag">ANSWER / DEFINITION</span>
                                    <span className="page-citation-pill">Source: Page {currentCard.page_number}</span>
                                </div>
                                <div className="card-body-content">
                                    <p className="card-answer-text">{currentCard.back}</p>
                                </div>
                                <div className="card-face-footer">
                                    <div className="card-status-badges">
                                        {currentCard.known && <span className="status-badge known">✓ Mastered</span>}
                                        {currentCard.needs_review && <span className="status-badge review">⚠️ Needs Review</span>}
                                    </div>
                                    <div className="flip-prompt-indicator">
                                        <RotateCw size={13} />
                                        <span>Flip to Prompt</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Learning Status Controls & Card Stepper */}
                    <div className="flashcard-controls-toolbar">
                        <button
                            type="button"
                            className="btn-card-nav"
                            onClick={() => setCurrentCardIdx(prev => Math.max(0, prev - 1))}
                            disabled={currentCardIdx === 0}
                        >
                            <ArrowLeft size={16} />
                            <span>Previous</span>
                        </button>

                        <div className="learning-action-buttons">
                            <button
                                type="button"
                                className={`btn-learning-action btn-review ${currentCard.needs_review ? 'active' : ''}`}
                                onClick={() => handleUpdateCardStatus('needs_review')}
                                title="Mark this card for further review"
                            >
                                <Clock size={14} />
                                <span>Needs Review</span>
                            </button>

                            <button
                                type="button"
                                className={`btn-learning-action btn-known ${currentCard.known ? 'active' : ''}`}
                                onClick={() => handleUpdateCardStatus('known')}
                                title="Mark this card as mastered"
                            >
                                <Check size={14} />
                                <span>Mastered</span>
                            </button>
                        </div>

                        <button
                            type="button"
                            className="btn-card-nav"
                            onClick={() => setCurrentCardIdx(prev => Math.min(cards.length - 1, prev + 1))}
                            disabled={currentCardIdx === cards.length - 1}
                        >
                            <span>Next</span>
                            <ArrowRight size={16} />
                        </button>
                    </div>

                    <div className="flashcard-keyboard-help">
                        <span>Keyboard shortcuts: <strong>Space</strong> to flip, <strong>← / →</strong> for previous/next</span>
                    </div>
                </div>
            )}
        </div>
    )
}

