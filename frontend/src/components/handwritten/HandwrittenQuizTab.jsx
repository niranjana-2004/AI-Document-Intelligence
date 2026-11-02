import { useState, useEffect, useRef } from 'react'
import {
    HelpCircle,
    Sparkles,
    CheckCircle2,
    XCircle,
    ArrowRight,
    ArrowLeft,
    RotateCcw,
    Award,
    AlertTriangle,
    RefreshCw,
    Sliders,
    BookOpen,
    Quote,
    Clock,
    Check,
    X,
    Filter,
    Layers,
    Lightbulb
} from 'lucide-react'
import { apiRequest } from '../../services/api'

export default function HandwrittenQuizTab({ documentId, transcriptionUpdated }) {
    const [quizzes, setQuizzes] = useState([])
    const [activeQuizId, setActiveQuizId] = useState(null)
    const [currentQuestionIdx, setCurrentQuestionIdx] = useState(0)
    const [userAnswers, setUserAnswers] = useState({})
    const [submittedFeedback, setSubmittedFeedback] = useState(null)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [generating, setGenerating] = useState(false)
    const [showConfig, setShowConfig] = useState(false)
    const [showSubmitConfirm, setShowSubmitConfirm] = useState(false)
    const [error, setError] = useState(null)

    // Generator configs
    const [difficulty, setDifficulty] = useState('medium') // 'easy' | 'medium' | 'hard' | 'mixed'
    const [questionCount, setQuestionCount] = useState(5)
    const [questionTypes, setQuestionTypes] = useState('all') // 'all' | 'multiple_choice' | 'true_false' | 'short_answer'
    const [availableTopics, setAvailableTopics] = useState([])
    const [selectedTopic, setSelectedTopic] = useState('all')

    // Live timer
    const [elapsedSeconds, setElapsedSeconds] = useState(0)
    const [isTimerRunning, setIsTimerRunning] = useState(false)
    const timerRef = useRef(null)

    // Fetch topics
    const fetchTopics = async () => {
        try {
            const res = await apiRequest(`/handwritten/${documentId}/topics`)
            setAvailableTopics(res?.topics || [])
        } catch (err) {
            console.error('Fetch topics error:', err)
        }
    }

    // Fetch existing quizzes
    const fetchQuizzes = async () => {
        try {
            setError(null)
            const res = await apiRequest(`/handwritten/${documentId}/quizzes`)
            const list = res?.quizzes || []
            setQuizzes(list)
            if (list.length > 0 && !activeQuizId) {
                setActiveQuizId(list[0].id)
                if (list[0].is_submitted) {
                    handleLoadSubmittedQuiz(list[0])
                }
            }
        } catch (err) {
            console.error('Fetch quizzes error:', err)
            setError(err.message || 'Failed to load quizzes.')
        }
    }

    useEffect(() => {
        if (documentId) {
            fetchTopics()
            fetchQuizzes()
        }
    }, [documentId, transcriptionUpdated])

    const activeQuiz = quizzes.find(q => q.id === activeQuizId) || null
    const questions = activeQuiz?.questions || []
    const currentQuestion = questions[currentQuestionIdx] || null

    // Load submitted quiz details
    const handleLoadSubmittedQuiz = (quiz) => {
        const answers = quiz.user_answers || {}
        const total = quiz.questions?.length || 0
        const correct = quiz.user_score || 0
        const percentage = total > 0 ? Math.round((correct / total) * 100) : 0

        const feedback = (quiz.questions || []).map(q => {
            const uAns = (answers[q.id] || '').trim()
            const cAns = (q.correct_answer || '').trim()
            const isUnanswered = !uAns
            const isCorrect = !isUnanswered && (
                uAns.toLowerCase() === cAns.toLowerCase() ||
                (cAns.toLowerCase().startsWith(uAns.toLowerCase()) && uAns.length === 1) ||
                (cAns.toLowerCase().includes(uAns.toLowerCase()) && uAns.length > 3)
            )

            return {
                id: q.id,
                type: q.type,
                category: q.category,
                topic: q.topic,
                difficulty: q.difficulty,
                question: q.question,
                options: q.options || [],
                user_answer: uAns,
                correct_answer: cAns,
                is_correct: isCorrect,
                is_unanswered: isUnanswered,
                explanation: q.explanation,
                excerpt: q.excerpt,
                page_number: q.page_number
            }
        })

        const incorrectCount = feedback.filter(f => !f.is_correct && !f.is_unanswered).length
        const unansweredCount = feedback.filter(f => f.is_unanswered).length

        setSubmittedFeedback({
            quiz_id: quiz.id,
            total_questions: total,
            correct_count: correct,
            incorrect_count: incorrectCount,
            unanswered_count: unansweredCount,
            score_percentage: percentage,
            time_taken_seconds: quiz.time_taken_seconds || 0,
            performance_summary: percentage >= 75 ? "Well done! Good comprehension demonstrated." : "Review recommended for missed concepts.",
            feedback,
            weak_topics: quiz.weak_topics || [],
            recommendations: quiz.recommendations || []
        })
    }

    // Switch active quiz
    useEffect(() => {
        if (activeQuiz) {
            setCurrentQuestionIdx(0)
            if (activeQuiz.is_submitted) {
                setUserAnswers(activeQuiz.user_answers || {})
                handleLoadSubmittedQuiz(activeQuiz)
                setIsTimerRunning(false)
            } else {
                setUserAnswers({})
                setSubmittedFeedback(null)
                setElapsedSeconds(0)
                setIsTimerRunning(true)
            }
        }
    }, [activeQuizId])

    // Timer effect
    useEffect(() => {
        if (isTimerRunning && !submittedFeedback) {
            timerRef.current = setInterval(() => {
                setElapsedSeconds(prev => prev + 1)
            }, 1000)
        } else {
            clearInterval(timerRef.current)
        }
        return () => clearInterval(timerRef.current)
    }, [isTimerRunning, submittedFeedback])

    const formatTimer = (secs) => {
        const m = Math.floor(secs / 60)
        const s = secs % 60
        return `${m}:${s < 10 ? '0' : ''}${s}`
    }

    // Generate new quiz
    const handleGenerateQuiz = async (overrideTopics = null) => {
        try {
            setGenerating(true)
            setError(null)
            setShowConfig(false)

            const topicsPayload = overrideTopics || (selectedTopic !== 'all' ? [selectedTopic] : null)

            const res = await apiRequest(`/handwritten/${documentId}/quizzes/generate`, {
                method: 'POST',
                body: JSON.stringify({
                    difficulty,
                    question_count: questionCount,
                    question_types: questionTypes,
                    topics: topicsPayload
                })
            })

            const newQuiz = res?.quiz
            if (newQuiz) {
                setQuizzes(prev => [newQuiz, ...prev])
                setActiveQuizId(newQuiz.id)
                setCurrentQuestionIdx(0)
                setUserAnswers({})
                setSubmittedFeedback(null)
                setElapsedSeconds(0)
                setIsTimerRunning(true)
            }
        } catch (err) {
            console.error('Quiz generate error:', err)
            setError(err.message || 'Failed to generate quiz.')
        } finally {
            setGenerating(false)
        }
    }

    // Handle answer modification
    const handleSelectOption = (questionId, option) => {
        if (submittedFeedback) return
        setUserAnswers(prev => ({
            ...prev,
            [questionId]: option
        }))
    }

    const handleShortAnswerChange = (questionId, text) => {
        if (submittedFeedback) return
        setUserAnswers(prev => ({
            ...prev,
            [questionId]: text
        }))
    }

    // Pre-submission check
    const handlePreSubmit = () => {
        if (!activeQuiz) return
        const answeredCount = Object.keys(userAnswers).filter(k => (userAnswers[k] || '').trim()).length
        const total = questions.length

        if (answeredCount < total) {
            setShowSubmitConfirm(true)
        } else {
            handleFinalSubmit()
        }
    }

    // Final Submit Quiz
    const handleFinalSubmit = async () => {
        if (!activeQuiz) return
        setShowSubmitConfirm(false)
        setIsTimerRunning(false)

        try {
            setIsSubmitting(true)
            setError(null)

            const res = await apiRequest(`/handwritten/${documentId}/quizzes/${activeQuiz.id}/submit`, {
                method: 'POST',
                body: JSON.stringify({
                    answers: userAnswers,
                    time_taken_seconds: elapsedSeconds
                })
            })

            setSubmittedFeedback(res)

            // Update quiz in state
            setQuizzes(prev => prev.map(q => q.id === activeQuiz.id ? {
                ...q,
                is_submitted: true,
                user_score: res.correct_count,
                user_answers: userAnswers,
                time_taken_seconds: elapsedSeconds,
                weak_topics: res.weak_topics,
                recommendations: res.recommendations
            } : q))
        } catch (err) {
            console.error('Submit quiz error:', err)
            setError(err.message || 'Failed to submit quiz.')
            setIsTimerRunning(true)
        } finally {
            setIsSubmitting(false)
        }
    }

    // Retake quiz
    const handleRetake = () => {
        setUserAnswers({})
        setSubmittedFeedback(null)
        setCurrentQuestionIdx(0)
        setElapsedSeconds(0)
        setIsTimerRunning(true)
    }

    // Targeted Weak-Area Practice
    const handlePracticeWeakAreas = () => {
        if (!submittedFeedback?.weak_topics) return
        const weakNames = submittedFeedback.weak_topics.map(w => w.topic)
        handleGenerateQuiz(weakNames)
    }

    const answeredCount = Object.keys(userAnswers).filter(k => (userAnswers[k] || '').trim()).length

    return (
        <div className="intel-tab-container">
            {/* Top Toolbar */}
            <div className="intel-toolbar">
                <div className="quiz-selector-group">
                    {quizzes.length > 0 && (
                        <select
                            className="quiz-dropdown-select"
                            value={activeQuizId || ''}
                            onChange={(e) => setActiveQuizId(Number(e.target.value))}
                        >
                            {quizzes.map((q, idx) => (
                                <option key={q.id} value={q.id}>
                                    Quiz #{quizzes.length - idx}: {q.title} ({q.difficulty.toUpperCase()}) {q.is_submitted ? `• Score: ${q.user_score}/${q.question_count}` : '• In Progress'}
                                </option>
                            ))}
                        </select>
                    )}
                </div>

                <div className="intel-actions-group">
                    {!submittedFeedback && isTimerRunning && (
                        <div className="quiz-timer-pill" title="Elapsed examination time">
                            <Clock size={13} className="timer-icon" />
                            <span>{formatTimer(elapsedSeconds)}</span>
                        </div>
                    )}

                    <button
                        type="button"
                        className="btn-studio-action"
                        onClick={() => setShowConfig(!showConfig)}
                    >
                        <Sliders size={13} />
                        <span>Config</span>
                    </button>

                    <button
                        type="button"
                        className="btn-studio-action btn-studio-primary"
                        onClick={() => setShowConfig(true)}
                        disabled={generating}
                    >
                        <Sparkles size={13} className={generating ? 'spin-icon' : ''} />
                        <span>{generating ? 'Synthesizing...' : 'New Quiz'}</span>
                    </button>
                </div>
            </div>

            {/* Config Drawer / Modal */}
            {showConfig && (
                <div className="quiz-config-card">
                    <div className="config-header">
                        <h4>Configure Examination Quiz</h4>
                        <button type="button" className="config-close-btn" onClick={() => setShowConfig(false)}>×</button>
                    </div>
                    <div className="config-grid">
                        <div className="config-field">
                            <label>Difficulty</label>
                            <div className="config-pills">
                                {[
                                    { id: 'mixed', label: 'Mixed' },
                                    { id: 'easy', label: 'Easy' },
                                    { id: 'medium', label: 'Medium' },
                                    { id: 'hard', label: 'Hard' }
                                ].map(lvl => (
                                    <button
                                        key={lvl.id}
                                        type="button"
                                        className={`config-pill ${difficulty === lvl.id ? 'active' : ''}`}
                                        onClick={() => setDifficulty(lvl.id)}
                                    >
                                        {lvl.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="config-field">
                            <label>Questions</label>
                            <div className="config-pills">
                                {[3, 5, 10, 15].map(cnt => (
                                    <button
                                        key={cnt}
                                        type="button"
                                        className={`config-pill ${questionCount === cnt ? 'active' : ''}`}
                                        onClick={() => setQuestionCount(cnt)}
                                    >
                                        {cnt} Questions
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="config-field">
                            <label>Question Type</label>
                            <div className="config-pills">
                                {[
                                    { id: 'all', label: 'Mixed Format' },
                                    { id: 'multiple_choice', label: 'MCQs' },
                                    { id: 'true_false', label: 'True / False' },
                                    { id: 'short_answer', label: 'Short Answer' }
                                ].map(t => (
                                    <button
                                        key={t.id}
                                        type="button"
                                        className={`config-pill ${questionTypes === t.id ? 'active' : ''}`}
                                        onClick={() => setQuestionTypes(t.id)}
                                    >
                                        {t.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {availableTopics.length > 0 && (
                            <div className="config-field">
                                <label>Topic Focus</label>
                                <select
                                    className="config-topic-select"
                                    value={selectedTopic}
                                    onChange={(e) => setSelectedTopic(e.target.value)}
                                >
                                    <option value="all">All Note Topics (Comprehensive)</option>
                                    {availableTopics.map((top, idx) => (
                                        <option key={idx} value={top}>{top}</option>
                                    ))}
                                </select>
                            </div>
                        )}
                    </div>

                    <div className="config-actions">
                        <button
                            type="button"
                            className="btn-intel-primary"
                            onClick={() => handleGenerateQuiz()}
                            disabled={generating}
                        >
                            <Sparkles size={14} />
                            <span>Generate Examination ({questionCount} Qs • {difficulty.toUpperCase()})</span>
                        </button>
                    </div>
                </div>
            )}

            {/* Outdated Notice */}
            {activeQuiz && activeQuiz.is_outdated && (
                <div className="intel-outdated-banner">
                    <div className="outdated-content">
                        <AlertTriangle size={18} className="outdated-icon" />
                        <div>
                            <strong>Transcription Updated</strong>
                            <p>Handwritten notes transcription has changed since this quiz was generated. Create an updated examination to test your latest edits.</p>
                        </div>
                    </div>
                    <button
                        type="button"
                        className="btn-outdated-regen"
                        onClick={() => handleGenerateQuiz()}
                        disabled={generating}
                    >
                        <RefreshCw size={12} className={generating ? 'spin-icon' : ''} />
                        <span>Regenerate Quiz</span>
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
                        onClick={() => handleGenerate()}
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
                        <HelpCircle size={28} className="spin-icon" style={{ color: '#38bdf8' }} />
                    </div>
                    <h4>Synthesizing Academic Examination...</h4>
                    <p>Formulating distinct questions spanning conceptual understanding, definitions, applications, and problem-solving with Llama 3.2.</p>
                    <div className="intel-progress-bar-wrap">
                        <div className="intel-progress-bar-fill" />
                    </div>
                </div>
            )}

            {/* Empty State */}
            {!generating && quizzes.length === 0 && (
                <div className="intel-empty-card">
                    <div className="empty-icon-wrap" style={{ background: 'rgba(56, 189, 248, 0.15)', borderColor: 'rgba(56, 189, 248, 0.3)' }}>
                        <HelpCircle size={40} style={{ color: '#38bdf8' }} />
                    </div>
                    <h3>Interactive Examination & Assessment</h3>
                    <p>
                        Generate rigorous quizzes across 7 pedagogical categories (conceptual, application, scenario-based, analytical, comparison) directly from your handwritten notes.
                    </p>
                    <button
                        type="button"
                        className="btn-intel-primary"
                        onClick={() => setShowConfig(true)}
                    >
                        <Sparkles size={16} />
                        <span>Create Examination</span>
                    </button>
                </div>
            )}

            {/* ACTIVE QUIZ ATTEMPT SCREEN */}
            {!generating && activeQuiz && currentQuestion && !submittedFeedback && (
                <div className="quiz-runner-card">
                    {/* Header: Progress, Category, Topic, Page Badge */}
                    <div className="quiz-runner-header">
                        <div className="quiz-progress-text">
                            <div className="q-badge-group">
                                <span className="q-number">Question {currentQuestionIdx + 1} of {questions.length}</span>
                                <span className="q-category-pill">{currentQuestion.category ? currentQuestion.category.toUpperCase() : 'CONCEPTUAL'}</span>
                                {currentQuestion.topic && (
                                    <span className="q-topic-pill">{currentQuestion.topic}</span>
                                )}
                                <span className="q-diff-badge">{currentQuestion.difficulty ? currentQuestion.difficulty.toUpperCase() : activeQuiz.difficulty.toUpperCase()}</span>
                            </div>
                            <span className="page-citation-pill">Page {currentQuestion.page_number}</span>
                        </div>
                        <div className="quiz-progress-track">
                            <div
                                className="quiz-progress-indicator"
                                style={{ width: `${((currentQuestionIdx + 1) / questions.length) * 100}%` }}
                            />
                        </div>
                    </div>

                    {/* Question Content */}
                    <div className="question-content-box">
                        <h3 className="question-text">{currentQuestion.question}</h3>

                        {/* Question Format Rendering: Multiple Choice */}
                        {currentQuestion.type === 'multiple_choice' && (
                            <div className="options-list">
                                {(currentQuestion.options || []).map((opt, oIdx) => {
                                    const isSelected = userAnswers[currentQuestion.id] === opt
                                    return (
                                        <button
                                            key={oIdx}
                                            type="button"
                                            className={`option-btn ${isSelected ? 'selected' : ''}`}
                                            onClick={() => handleSelectOption(currentQuestion.id, opt)}
                                        >
                                            <span className="option-marker">
                                                {String.fromCharCode(65 + oIdx)}
                                            </span>
                                            <span className="option-text">{opt}</span>
                                        </button>
                                    )
                                })}
                            </div>
                        )}

                        {/* Question Format Rendering: True / False */}
                        {currentQuestion.type === 'true_false' && (
                            <div className="tf-options-group">
                                {['True', 'False'].map((tf) => {
                                    const isSelected = userAnswers[currentQuestion.id]?.toLowerCase() === tf.toLowerCase()
                                    return (
                                        <button
                                            key={tf}
                                            type="button"
                                            className={`tf-option-btn ${isSelected ? 'selected' : ''}`}
                                            onClick={() => handleSelectOption(currentQuestion.id, tf)}
                                        >
                                            <span className="tf-indicator" />
                                            <span className="tf-text">{tf}</span>
                                        </button>
                                    )
                                })}
                            </div>
                        )}

                        {/* Question Format Rendering: Short Answer */}
                        {currentQuestion.type === 'short_answer' && (
                            <div className="short-answer-box">
                                <label className="short-answer-label">Enter your response based on the notes:</label>
                                <textarea
                                    className="short-answer-input"
                                    placeholder="Type your explanation or answer here..."
                                    value={userAnswers[currentQuestion.id] || ''}
                                    onChange={(e) => handleShortAnswerChange(currentQuestion.id, e.target.value)}
                                    rows={3}
                                />
                            </div>
                        )}
                    </div>

                    {/* Step 3: Question Navigation Panel / Grid */}
                    <div className="quiz-nav-grid-panel">
                        <div className="nav-grid-header">
                            <span>Question Navigator</span>
                            <span className="nav-grid-stat">{answeredCount} of {questions.length} Answered</span>
                        </div>
                        <div className="nav-pills-row">
                            {questions.map((q, idx) => {
                                const isAns = Boolean((userAnswers[q.id] || '').trim())
                                const isCurr = idx === currentQuestionIdx
                                return (
                                    <button
                                        key={idx}
                                        type="button"
                                        className={`nav-pill-btn ${isCurr ? 'current' : ''} ${isAns ? 'answered' : 'unanswered'}`}
                                        onClick={() => setCurrentQuestionIdx(idx)}
                                        title={`Jump to Question ${idx + 1}`}
                                    >
                                        {idx + 1}
                                    </button>
                                )
                            })}
                        </div>
                    </div>

                    {/* Footer Actions: Navigation & Submit */}
                    <div className="quiz-footer-actions">
                        <button
                            type="button"
                            className="btn-quiz-nav"
                            onClick={() => setCurrentQuestionIdx(prev => Math.max(0, prev - 1))}
                            disabled={currentQuestionIdx === 0}
                        >
                            <ArrowLeft size={14} />
                            <span>Previous</span>
                        </button>

                        <div className="answered-status">
                            <button
                                type="button"
                                className="btn-skip-question"
                                onClick={() => setCurrentQuestionIdx(prev => Math.min(questions.length - 1, prev + 1))}
                                disabled={currentQuestionIdx === questions.length - 1}
                            >
                                Skip Question
                            </button>
                        </div>

                        {currentQuestionIdx < questions.length - 1 ? (
                            <button
                                type="button"
                                className="btn-quiz-nav btn-quiz-next"
                                onClick={() => setCurrentQuestionIdx(prev => prev + 1)}
                            >
                                <span>Next</span>
                                <ArrowRight size={14} />
                            </button>
                        ) : (
                            <button
                                type="button"
                                className="btn-quiz-nav btn-quiz-submit"
                                onClick={handlePreSubmit}
                                disabled={isSubmitting}
                            >
                                <span>{isSubmitting ? 'Evaluating...' : 'Submit Examination'}</span>
                                <CheckCircle2 size={14} />
                            </button>
                        )}
                    </div>
                </div>
            )}

            {/* Unanswered Questions Confirmation Dialog */}
            {showSubmitConfirm && (
                <div className="submit-confirm-overlay" role="dialog" aria-modal="true">
                    <div className="submit-confirm-card">
                        <div className="confirm-icon-wrap">
                            <AlertTriangle size={24} style={{ color: '#fbbf24' }} />
                        </div>
                        <h4>Unanswered Questions Remaining</h4>
                        <p>
                            You have answered <strong>{answeredCount}</strong> of <strong>{questions.length}</strong> questions.
                            ({questions.length - answeredCount} unanswered questions will be marked as skipped).
                        </p>
                        <div className="confirm-actions-row">
                            <button
                                type="button"
                                className="btn-confirm-secondary"
                                onClick={() => setShowSubmitConfirm(false)}
                            >
                                Review Answers
                            </button>
                            <button
                                type="button"
                                className="btn-confirm-primary"
                                onClick={handleFinalSubmit}
                            >
                                Submit Anyway
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* RESULTS SCREEN (STEP 5 & STEP 6) */}
            {!generating && submittedFeedback && (
                <div className="quiz-results-container">
                    {/* Score Hero Card */}
                    <div className="score-hero-card">
                        <div className="score-award-icon">
                            <Award size={36} style={{ color: submittedFeedback.score_percentage >= 75 ? '#34d399' : '#fbbf24' }} />
                        </div>
                        <h3 className="score-percentage-title">{submittedFeedback.score_percentage}%</h3>
                        <p className="score-subtitle">{submittedFeedback.performance_summary}</p>

                        {/* Detailed Metrics Badges */}
                        <div className="score-metrics-pills-row">
                            <span className="metric-pill correct">
                                <CheckCircle2 size={13} />
                                <span>{submittedFeedback.correct_count} Correct</span>
                            </span>
                            <span className="metric-pill incorrect">
                                <XCircle size={13} />
                                <span>{submittedFeedback.incorrect_count} Incorrect</span>
                            </span>
                            {submittedFeedback.unanswered_count > 0 && (
                                <span className="metric-pill unanswered">
                                    <Clock size={13} />
                                    <span>{submittedFeedback.unanswered_count} Unanswered</span>
                                </span>
                            )}
                            {submittedFeedback.time_taken_seconds > 0 && (
                                <span className="metric-pill time">
                                    <Clock size={13} />
                                    <span>Time: {formatTimer(submittedFeedback.time_taken_seconds)}</span>
                                </span>
                            )}
                        </div>

                        <div className="results-actions">
                            <button
                                type="button"
                                className="btn-studio-action"
                                onClick={handleRetake}
                            >
                                <RotateCcw size={13} />
                                <span>Retake Examination</span>
                            </button>
                            <button
                                type="button"
                                className="btn-studio-action btn-studio-primary"
                                onClick={() => setShowConfig(true)}
                            >
                                <Sparkles size={13} />
                                <span>New Examination</span>
                            </button>
                        </div>
                    </div>

                    {/* STEP 6: LEARNING RECOMMENDATIONS (WEAK AREAS) */}
                    {submittedFeedback.recommendations && submittedFeedback.recommendations.length > 0 && (
                        <div className="weak-areas-card">
                            <div className="weak-areas-header">
                                <div className="weak-icon-badge">
                                    <Lightbulb size={18} />
                                </div>
                                <div>
                                    <h4 className="weak-title">Targeted Revision Recommendations</h4>
                                    <p className="weak-subtitle">Concepts to strengthen based on your examination performance:</p>
                                </div>
                            </div>

                            <div className="weak-topics-grid">
                                {submittedFeedback.recommendations.map((rec, rIdx) => (
                                    <div key={rIdx} className="weak-topic-item">
                                        <div className="weak-topic-top">
                                            <span className="weak-topic-name">{rec.topic}</span>
                                            {rec.pages && rec.pages.length > 0 && (
                                                <span className="page-citation-pill">
                                                    Page {rec.pages.join(', ')}
                                                </span>
                                            )}
                                        </div>
                                        <p className="weak-action-text">{rec.action}</p>
                                        <div className="weak-flashcard-hint">
                                            <Layers size={11} />
                                            <span>{rec.flashcard_suggestion}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className="weak-action-footer">
                                <button
                                    type="button"
                                    className="btn-practice-weak"
                                    onClick={handlePracticeWeakAreas}
                                    title="Generate a targeted quiz focusing exclusively on your weak topics"
                                >
                                    <Sparkles size={13} />
                                    <span>Practice Weak Areas Quiz</span>
                                </button>
                            </div>
                        </div>
                    )}

                    {/* STEP 5: DETAILED QUESTION REVIEW */}
                    <div className="results-breakdown-list">
                        <h4 className="breakdown-heading">Detailed Examination Question Review</h4>
                        {(submittedFeedback.feedback || []).map((fb, idx) => (
                            <div
                                key={idx}
                                className={`review-card ${fb.is_correct ? 'correct-card' : (fb.is_unanswered ? 'unanswered-card' : 'incorrect-card')}`}
                            >
                                <div className="review-card-header">
                                    <div className="review-status-pill">
                                        {fb.is_correct ? (
                                            <>
                                                <CheckCircle2 size={14} style={{ color: '#34d399' }} />
                                                <span>Correct</span>
                                            </>
                                        ) : fb.is_unanswered ? (
                                            <>
                                                <Clock size={14} style={{ color: '#94a3b8' }} />
                                                <span>Unanswered / Skipped</span>
                                            </>
                                        ) : (
                                            <>
                                                <XCircle size={14} style={{ color: '#f87171' }} />
                                                <span>Incorrect</span>
                                            </>
                                        )}
                                    </div>
                                    <div className="review-meta-group">
                                        <span className="q-category-pill">{fb.category || 'CONCEPTUAL'}</span>
                                        {fb.topic && <span className="q-topic-pill">{fb.topic}</span>}
                                        <span className="page-citation-pill">Page {fb.page_number}</span>
                                    </div>
                                </div>

                                <p className="review-question">{fb.question}</p>

                                <div className="review-answers-box">
                                    <div className="answer-line">
                                        <strong>Your Answer:</strong>
                                        <span className={fb.is_correct ? 'ans-correct' : (fb.is_unanswered ? 'ans-unanswered' : 'ans-incorrect')}>
                                            {fb.user_answer || '(Unanswered)'}
                                        </span>
                                    </div>
                                    {!fb.is_correct && (
                                        <div className="answer-line">
                                            <strong>Correct Answer:</strong>
                                            <span className="ans-correct">{fb.correct_answer}</span>
                                        </div>
                                    )}
                                </div>

                                {fb.explanation && (
                                    <p className="review-explanation">
                                        <strong>Explanation:</strong> {fb.explanation}
                                    </p>
                                )}

                                {fb.excerpt && (
                                    <div className="review-quote-box">
                                        <Quote size={11} className="quote-icon" />
                                        <span>"{fb.excerpt}"</span>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}
