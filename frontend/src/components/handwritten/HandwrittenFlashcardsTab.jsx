import { useState, useEffect, useCallback, useMemo } from 'react'
import {
    Layers,
    Sparkles,
    RotateCw,
    Shuffle,
    ArrowLeft,
    ArrowRight,
    AlertTriangle,
    RefreshCw,
    CheckCircle2,
    Clock,
    Maximize2,
    Minimize2,
    Quote,
    Award
} from 'lucide-react'
import { apiRequest } from '../../services/api'
import CustomTopicDropdown from './CustomTopicDropdown'

export default function HandwrittenFlashcardsTab({ documentId, transcriptionUpdated }) {
    const [decks, setDecks] = useState([])
    const [activeDeckId, setActiveDeckId] = useState(null)
    const [currentCardIdx, setCurrentCardIdx] = useState(0)
    const [isFlipped, setIsFlipped] = useState(false)
    const [generating, setGenerating] = useState(false)
    const [cardCount, setCardCount] = useState(8)
    const [selectedTopic, setSelectedTopic] = useState('all')
    const [showConfig, setShowConfig] = useState(false)
    const [error, setError] = useState(null)

    // Advanced learning interaction states
    const [isShuffled, setIsShuffled] = useState(false)
    const [shuffledIndices, setShuffledIndices] = useState([])
    const [studyFilter, setStudyFilter] = useState('all') // 'all' | 'needs_review' | 'mastered'
    const [filterTopic, setFilterTopic] = useState('all')
    const [isFocusMode, setIsFocusMode] = useState(false)
    const [isSessionCompleted, setIsSessionCompleted] = useState(false)

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
    const originalCards = activeDeck?.cards || []

    // Available topics in the current deck
    const availableTopics = useMemo(() => {
        const tops = new Set()
        originalCards.forEach(c => {
            if (c.topic) tops.add(c.topic)
        })
        return Array.from(tops).sort()
    }, [originalCards])

    // Filter cards based on study mode and topic
    const activeCards = useMemo(() => {
        let filtered = [...originalCards]

        if (filterTopic !== 'all') {
            filtered = filtered.filter(c => c.topic === filterTopic)
        }

        if (studyFilter === 'needs_review') {
            filtered = filtered.filter(c => c.needs_review || c.rating === 'again' || c.rating === 'hard' || (!c.known && !c.rating))
        } else if (studyFilter === 'mastered') {
            filtered = filtered.filter(c => c.known || c.rating === 'good' || c.rating === 'easy')
        }

        if (isShuffled && shuffledIndices.length === filtered.length) {
            return shuffledIndices.map(idx => filtered[idx]).filter(Boolean)
        }

        return filtered
    }, [originalCards, studyFilter, filterTopic, isShuffled, shuffledIndices])

    const totalActive = activeCards.length
    const currentCard = activeCards[currentCardIdx] || null

    // Reset card index when filters or deck switch
    useEffect(() => {
        setCurrentCardIdx(0)
        setIsFlipped(false)
        setIsSessionCompleted(false)
    }, [activeDeckId, studyFilter, filterTopic])

    // Reset flip when switching card index
    useEffect(() => {
        setIsFlipped(false)
    }, [currentCardIdx])

    // Generate new deck
    const handleGenerateDeck = async () => {
        try {
            setGenerating(true)
            setError(null)
            setShowConfig(false)
            const topicPayload = selectedTopic !== 'all' ? selectedTopic : null

            const res = await apiRequest(`/handwritten/${documentId}/flashcards/generate`, {
                method: 'POST',
                body: JSON.stringify({
                    card_count: cardCount,
                    topic: topicPayload
                })
            })
            const newDeck = res?.deck
            if (newDeck) {
                setDecks(prev => [newDeck, ...prev])
                setActiveDeckId(newDeck.id)
                setCurrentCardIdx(0)
                setIsShuffled(false)
                setStudyFilter('all')
                setFilterTopic('all')
                setIsSessionCompleted(false)
            }
        } catch (err) {
            console.error('Flashcard generate error:', err)
            setError(err.message || 'Failed to generate flashcard deck.')
        } finally {
            setGenerating(false)
        }
    }

    // Toggle Shuffle Mode (without destroying stored order)
    const handleToggleShuffle = () => {
        if (!isShuffled) {
            const indices = Array.from({ length: activeCards.length }, (_, i) => i)
            for (let i = indices.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [indices[i], indices[j]] = [indices[j], indices[i]]
            }
            setShuffledIndices(indices)
            setIsShuffled(true)
            setCurrentCardIdx(0)
        } else {
            setIsShuffled(false)
            setShuffledIndices([])
            setCurrentCardIdx(0)
        }
    }

    // 4-Level Self Assessment: 'again', 'hard', 'good', 'easy'
    const handleRateCard = async (rating) => {
        if (!activeDeck || !currentCard) return

        try {
            // Optimistic update
            setDecks(prev => prev.map(d => {
                if (d.id !== activeDeck.id) return d
                const updatedCards = d.cards.map(c => {
                    if (c.id === currentCard.id) {
                        const isMastered = rating === 'good' || rating === 'easy'
                        return {
                            ...c,
                            rating,
                            known: isMastered,
                            needs_review: !isMastered,
                            review_count: (c.review_count || 0) + 1,
                            last_reviewed_at: new Date().toISOString()
                        }
                    }
                    return c
                })
                const knownCount = updatedCards.filter(c => c.known || c.rating === 'good' || c.rating === 'easy').length
                const reviewCount = updatedCards.filter(c => c.needs_review || c.rating === 'again' || c.rating === 'hard').length
                return { ...d, cards: updatedCards, known_count: knownCount, needs_review_count: reviewCount }
            }))

            await apiRequest(`/handwritten/${documentId}/flashcards/${activeDeck.id}/cards/${currentCard.id}`, {
                method: 'PATCH',
                body: JSON.stringify({ rating })
            })

            // Advance to next card or complete session
            if (currentCardIdx < totalActive - 1) {
                setTimeout(() => {
                    setCurrentCardIdx(prev => prev + 1)
                }, 200)
            } else {
                setIsSessionCompleted(true)
            }
        } catch (err) {
            console.error('Rate card error:', err)
        }
    }

    // Reset deck status
    const handleResetDeck = async () => {
        if (!activeDeck) return
        try {
            setDecks(prev => prev.map(d => {
                if (d.id !== activeDeck.id) return d
                const resetCards = d.cards.map(c => ({
                    ...c,
                    known: false,
                    needs_review: false,
                    rating: null,
                    review_count: 0
                }))
                return { ...d, cards: resetCards, known_count: 0, needs_review_count: 0 }
            }))
            await apiRequest(`/handwritten/${documentId}/flashcards/${activeDeck.id}/reset`, {
                method: 'POST'
            })
            setCurrentCardIdx(0)
            setIsSessionCompleted(false)
        } catch (err) {
            console.error('Reset deck error:', err)
        }
    }

    // Keyboard navigation
    const handleKeyDown = useCallback((e) => {
        if (showConfig || generating) return

        if (e.key === ' ' || e.code === 'Space') {
            e.preventDefault()
            setIsFlipped(prev => !prev)
        } else if (e.key === 'ArrowRight') {
            if (currentCardIdx < totalActive - 1) {
                setCurrentCardIdx(prev => prev + 1)
            } else if (currentCardIdx === totalActive - 1) {
                setIsSessionCompleted(true)
            }
        } else if (e.key === 'ArrowLeft') {
            setCurrentCardIdx(prev => Math.max(0, prev - 1))
        } else if (isFlipped) {
            // Ratings keyboard shortcuts
            if (e.key === '1') handleRateCard('again')
            else if (e.key === '2') handleRateCard('hard')
            else if (e.key === '3') handleRateCard('good')
            else if (e.key === '4') handleRateCard('easy')
        } else if (e.key === 'Escape' && isFocusMode) {
            setIsFocusMode(false)
        }
    }, [totalActive, currentCardIdx, isFlipped, isFocusMode, showConfig, generating])

    useEffect(() => {
        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [handleKeyDown])

    const knownCount = activeDeck?.known_count || 0
    const reviewCount = activeDeck?.needs_review_count || 0
    const totalCount = originalCards.length

    // Format card type label
    const formatCardType = (typeStr) => {
        const map = {
            'question_answer': 'QUESTION & ANSWER',
            'term_definition': 'TERM & DEFINITION',
            'concept_explanation': 'CONCEPT & EXPLANATION',
            'formula_application': 'FORMULA & APPLICATION',
            'problem_solution': 'PROBLEM & SOLUTION',
            'compare_contrast': 'COMPARE & CONTRAST',
            'example_concept': 'EXAMPLE & CONCEPT',
            'important_facts': 'IMPORTANT FACTS'
        }
        return map[typeStr] || (typeStr ? typeStr.replace('_', ' ').toUpperCase() : 'ACTIVE RECALL')
    }

    return (
        <div className={`intel-tab-container ${isFocusMode ? 'flashcard-focus-mode' : ''}`}>
            {/* Top Toolbar */}
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
                                className={`btn-studio-action ${isShuffled ? 'active-highlight' : ''}`}
                                onClick={handleToggleShuffle}
                                title={isShuffled ? 'Restore original order' : 'Shuffle cards for study'}
                            >
                                <Shuffle size={13} />
                                <span>{isShuffled ? 'Shuffled' : 'Shuffle'}</span>
                            </button>

                            <button
                                type="button"
                                className="btn-studio-action"
                                onClick={() => setIsFocusMode(!isFocusMode)}
                                title={isFocusMode ? 'Exit focus mode' : 'Distraction-free focus mode'}
                            >
                                {isFocusMode ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
                                <span>{isFocusMode ? 'Exit Focus' : 'Focus Mode'}</span>
                            </button>

                            <button
                                type="button"
                                className="btn-studio-action"
                                onClick={handleResetDeck}
                                title="Reset card ratings"
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

            {/* Smart Revision & Topic Filter Bar */}
            {activeDeck && originalCards.length > 0 && (
                <div className="flashcard-filter-bar">
                    <div className="study-filter-segmented">
                        <button
                            type="button"
                            className={`segmented-filter-btn ${studyFilter === 'all' ? 'active' : ''}`}
                            onClick={() => setStudyFilter('all')}
                        >
                            <Layers size={13} className="btn-icon" />
                            <span className="btn-label">All Cards</span>
                            <span className="filter-count-badge all">{originalCards.length}</span>
                        </button>
                        <button
                            type="button"
                            className={`segmented-filter-btn review ${studyFilter === 'needs_review' ? 'active' : ''}`}
                            onClick={() => setStudyFilter('needs_review')}
                        >
                            <Sparkles size={13} className="btn-icon" />
                            <span className="btn-label">Smart Revision</span>
                            <span className="filter-count-badge review">{reviewCount}</span>
                        </button>
                        <button
                            type="button"
                            className={`segmented-filter-btn mastered ${studyFilter === 'mastered' ? 'active' : ''}`}
                            onClick={() => setStudyFilter('mastered')}
                        >
                            <CheckCircle2 size={13} className="btn-icon" />
                            <span className="btn-label">Mastered</span>
                            <span className="filter-count-badge mastered">{knownCount}</span>
                        </button>
                    </div>

                    {availableTopics.length > 1 && (
                        <div className="topic-filter-dropdown-wrap">
                            <CustomTopicDropdown
                                value={filterTopic}
                                onChange={setFilterTopic}
                                options={availableTopics}
                                allLabel="All Topics"
                                id="flashcard-topic-filter"
                            />
                        </div>
                    )}
                </div>
            )}

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
                                {[5, 8, 12, 16, 20].map(num => (
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

                        {availableTopics.length > 0 && (
                            <div className="config-field">
                                <label>Topic Focus</label>
                                <CustomTopicDropdown
                                    value={selectedTopic}
                                    onChange={setSelectedTopic}
                                    options={availableTopics}
                                    allLabel="All Note Topics (Diverse Mix)"
                                    id="flashcard-config-topic"
                                />
                            </div>
                        )}
                    </div>
                    <div className="config-actions">
                        <button
                            type="button"
                            className="btn-intel-primary"
                            onClick={handleGenerateDeck}
                            disabled={generating}
                        >
                            <Sparkles size={14} />
                            <span>Generate Deck ({cardCount} Cards across 8 Types)</span>
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
                            <p>Handwriting has been revised. Create an updated deck to align with current notes.</p>
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
                    <div className="intel-error-content">
                        <AlertTriangle size={16} />
                        <span>{error}</span>
                    </div>
                    <button
                        type="button"
                        className="btn-intel-retry"
                        onClick={() => handleGenerateDeck()}
                        disabled={generating}
                    >
                        <RefreshCw size={12} className={generating ? 'spin-icon' : ''} />
                        <span>Retry</span>
                    </button>
                </div>
            )}

            {/* Generating Loader */}
            {generating && (
                <div className="intel-generating-card">
                    <div className="intel-spinner-orb">
                        <Layers size={28} className="spin-icon" style={{ color: '#c084fc' }} />
                    </div>
                    <h4>Generating Active Recall Flashcards...</h4>
                    <p>Creating question-answers, definitions, formulas, problem-solutions, and comparison cards across your notes with Llama 3.2.</p>
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
                        Master handwritten notes using 8 active recall card types (terms, formulas, comparisons, problem solutions).
                        Rate your understanding and prioritize weak concepts with Smart Revision.
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

            {/* SESSION COMPLETION SCREEN */}
            {!generating && isSessionCompleted && (
                <div className="session-complete-card">
                    <div className="complete-award-icon">
                        <Award size={40} style={{ color: '#38bdf8' }} />
                    </div>
                    <h3>Study Session Completed!</h3>
                    <p className="complete-desc">You have reviewed all {totalActive} cards in this set.</p>

                    <div className="session-stats-grid">
                        <div className="session-stat-box mastered">
                            <span className="stat-value">{knownCount}</span>
                            <span className="stat-label">Mastered</span>
                        </div>
                        <div className="session-stat-box review">
                            <span className="stat-value">{reviewCount}</span>
                            <span className="stat-label">Needs Revision</span>
                        </div>
                        <div className="session-stat-box total">
                            <span className="stat-value">{totalActive}</span>
                            <span className="stat-label">Total Reviewed</span>
                        </div>
                    </div>

                    <div className="session-complete-actions">
                        {reviewCount > 0 && (
                            <button
                                type="button"
                                className="btn-intel-primary"
                                onClick={() => {
                                    setStudyFilter('needs_review')
                                    setCurrentCardIdx(0)
                                    setIsSessionCompleted(false)
                                }}
                            >
                                <Clock size={14} />
                                <span>Practice Difficult Cards ({reviewCount})</span>
                            </button>
                        )}
                        <button
                            type="button"
                            className="btn-studio-action"
                            onClick={() => {
                                setCurrentCardIdx(0)
                                setIsSessionCompleted(false)
                            }}
                        >
                            <RotateCw size={14} />
                            <span>Restart Deck</span>
                        </button>
                    </div>
                </div>
            )}

            {/* INTERACTIVE FLASHCARD 3D STAGE */}
            {!generating && activeDeck && currentCard && !isSessionCompleted && (
                <div className="flashcard-stage-container">
                    {/* Header: Card Counter, Type Pill, Topic Badge */}
                    <div className="flashcard-stats-row">
                        <div className="stat-pill-item">
                            <span className="stat-label">Card:</span>
                            <span className="stat-num">{currentCardIdx + 1} / {totalActive}</span>
                        </div>
                        <span className="card-type-badge">{formatCardType(currentCard.card_type)}</span>
                        {currentCard.topic && <span className="card-topic-pill">{currentCard.topic}</span>}
                        <span className="page-citation-pill">Page {currentCard.page_number}</span>
                    </div>

                    {/* Progress Track */}
                    <div className="flashcard-progress-track">
                        <div
                            className="flashcard-progress-indicator"
                            style={{ width: `${((currentCardIdx + 1) / totalActive) * 100}%` }}
                        />
                    </div>

                    {/* 3D Flip Card Scene */}
                    <div
                        className={`flashcard-scene ${isFlipped ? 'flipped' : ''}`}
                        onClick={() => setIsFlipped(!isFlipped)}
                        title="Click to flip (or press Space)"
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
                                        {currentCard.rating && (
                                            <span className={`rating-status-badge ${currentCard.rating}`}>
                                                Rating: {currentCard.rating.toUpperCase()}
                                            </span>
                                        )}
                                    </div>
                                    <div className="flip-prompt-indicator">
                                        <RotateCw size={13} />
                                        <span>Flip for Answer</span>
                                    </div>
                                </div>
                            </div>

                            {/* BACK SIDE */}
                            <div className="flashcard-face flashcard-back">
                                <div className="card-face-header">
                                    <span className="card-side-tag back-tag">ANSWER & EXPLANATION</span>
                                    <span className="page-citation-pill">Source: Page {currentCard.page_number}</span>
                                </div>
                                <div className="card-body-content">
                                    <p className="card-answer-text">{currentCard.back}</p>
                                    {currentCard.excerpt && (
                                        <div className="card-excerpt-quote">
                                            <Quote size={11} className="quote-icon" />
                                            <span>"{currentCard.excerpt}"</span>
                                        </div>
                                    )}
                                </div>
                                <div className="card-face-footer">
                                    <div className="card-status-badges">
                                        {currentCard.rating && (
                                            <span className={`rating-status-badge ${currentCard.rating}`}>
                                                Rating: {currentCard.rating.toUpperCase()}
                                            </span>
                                        )}
                                    </div>
                                    <div className="flip-prompt-indicator">
                                        <RotateCw size={13} />
                                        <span>Flip to Prompt</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* SELF ASSESSMENT RATINGS: AGAIN, HARD, GOOD, EASY */}
                    {isFlipped ? (
                        <div className="self-assessment-panel">
                            <span className="assessment-label">Rate your recall (Keys 1-4):</span>
                            <div className="assessment-buttons-row">
                                <button
                                    type="button"
                                    className="btn-rating btn-rate-again"
                                    onClick={() => handleRateCard('again')}
                                    title="Shortcut: Key 1"
                                >
                                    <span className="rate-num">1</span>
                                    <span className="rate-title">Again</span>
                                    <span className="rate-sub">Forgotten</span>
                                </button>
                                <button
                                    type="button"
                                    className="btn-rating btn-rate-hard"
                                    onClick={() => handleRateCard('hard')}
                                    title="Shortcut: Key 2"
                                >
                                    <span className="rate-num">2</span>
                                    <span className="rate-title">Hard</span>
                                    <span className="rate-sub">Struggled</span>
                                </button>
                                <button
                                    type="button"
                                    className="btn-rating btn-rate-good"
                                    onClick={() => handleRateCard('good')}
                                    title="Shortcut: Key 3"
                                >
                                    <span className="rate-num">3</span>
                                    <span className="rate-title">Good</span>
                                    <span className="rate-sub">Remembered</span>
                                </button>
                                <button
                                    type="button"
                                    className="btn-rating btn-rate-easy"
                                    onClick={() => handleRateCard('easy')}
                                    title="Shortcut: Key 4"
                                >
                                    <span className="rate-num">4</span>
                                    <span className="rate-title">Easy</span>
                                    <span className="rate-sub">Confident</span>
                                </button>
                            </div>
                        </div>
                    ) : (
                        /* Standard navigation when not flipped */
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

                            <button
                                type="button"
                                className="btn-flip-prompt"
                                onClick={() => setIsFlipped(true)}
                            >
                                <RotateCw size={14} />
                                <span>Reveal Answer (Space)</span>
                            </button>

                            <button
                                type="button"
                                className="btn-card-nav"
                                onClick={() => {
                                    if (currentCardIdx < totalActive - 1) {
                                        setCurrentCardIdx(prev => prev + 1)
                                    } else {
                                        setIsSessionCompleted(true)
                                    }
                                }}
                            >
                                <span>{currentCardIdx === totalActive - 1 ? 'Finish' : 'Next'}</span>
                                <ArrowRight size={16} />
                            </button>
                        </div>
                    )}

                    <div className="flashcard-keyboard-help">
                        <span>Shortcuts: <strong>Space</strong> flip • <strong>← / →</strong> navigate • <strong>1 / 2 / 3 / 4</strong> rate recall</span>
                    </div>
                </div>
            )}

            {/* Filtered empty state */}
            {!generating && activeDeck && totalActive === 0 && !isSessionCompleted && (
                <div className="intel-empty-card">
                    <p>No cards match the active filter ({studyFilter.replace('_', ' ')}).</p>
                    <button
                        type="button"
                        className="btn-studio-action"
                        onClick={() => {
                            setStudyFilter('all')
                            setFilterTopic('all')
                        }}
                    >
                        Show All Cards
                    </button>
                </div>
            )}
        </div>
    )
}
