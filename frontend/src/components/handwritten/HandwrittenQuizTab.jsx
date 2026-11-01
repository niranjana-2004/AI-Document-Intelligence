import { useState, useEffect } from 'react'
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
    Quote
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
    const [error, setError] = useState(null)

    // Generator configs
    const [difficulty, setDifficulty] = useState('medium')
    const [questionCount, setQuestionCount] = useState(5)
    const [questionTypes, setQuestionTypes] = useState('all')

    // Fetch existing quizzes
    const fetchQuizzes = async () => {
        try {
            setError(null)
            const res = await apiRequest(`/handwritten/${documentId}/quizzes`)
            const list = res?.quizzes || []
            setQuizzes(list)
            if (list.length > 0 && !activeQuizId) {
                setActiveQuizId(list[0].id)
                if (list[0].user_answers && list[0].user_score !== null) {
                    // Quiz was already submitted previously
                    handleEvaluateExisting(list[0])
                }
            }
        } catch (err) {
            console.error('Fetch quizzes error:', err)
            setError(err.message || 'Failed to load quizzes.')
        }
    }

    useEffect(() => {
        if (documentId) {
            fetchQuizzes()
        }
    }, [documentId, transcriptionUpdated])

    const activeQuiz = quizzes.find(q => q.id === activeQuizId) || null
    const questions = activeQuiz?.questions || []
    const currentQuestion = questions[currentQuestionIdx] || null

    // When switching active quiz, restore or reset answers
    useEffect(() => {
        if (activeQuiz) {
            setCurrentQuestionIdx(0)
            if (activeQuiz.user_answers && activeQuiz.user_score !== null) {
                setUserAnswers(activeQuiz.user_answers || {})
                handleEvaluateExisting(activeQuiz)
            } else {
                setUserAnswers({})
                setSubmittedFeedback(null)
            }
        }
    }, [activeQuizId])

    const handleEvaluateExisting = (quiz) => {
        const answers = quiz.user_answers || {}
        const total = quiz.questions?.length || 0
        const correct = quiz.user_score || 0
        const percentage = total > 0 ? Math.round((correct / total) * 100) : 0

        const feedback = (quiz.questions || []).map(q => {
            const uAns = answers[q.id] || ''
            const cAns = q.correct_answer || ''
            const isCorrect = uAns.trim().toLowerCase() === cAns.trim().toLowerCase()
            return {
                id: q.id,
                question: q.question,
                user_answer: uAns,
                correct_answer: cAns,
                is_correct: isCorrect,
                explanation: q.explanation,
                excerpt: q.excerpt,
                page_number: q.page_number
            }
        })

        setSubmittedFeedback({
            quiz_id: quiz.id,
            total_questions: total,
            correct_count: correct,
            score_percentage: percentage,
            feedback
        })
    }

    // Generate new quiz
    const handleGenerateQuiz = async () => {
        try {
            setGenerating(true)
            setError(null)
            setShowConfig(false)
            const res = await apiRequest(`/handwritten/${documentId}/quizzes/generate`, {
                method: 'POST',
                body: JSON.stringify({
                    difficulty,
                    question_count: questionCount,
                    question_types: questionTypes
                })
            })
            const newQuiz = res?.quiz
            if (newQuiz) {
                setQuizzes(prev => [newQuiz, ...prev])
                setActiveQuizId(newQuiz.id)
                setCurrentQuestionIdx(0)
                setUserAnswers({})
                setSubmittedFeedback(null)
            }
        } catch (err) {
            console.error('Quiz generate error:', err)
            setError(err.message || 'Failed to generate quiz.')
        } finally {
            setGenerating(false)
        }
    }

    // Handle answer selection
    const handleSelectOption = (questionId, option) => {
        if (submittedFeedback) return // locked after submission
        setUserAnswers(prev => ({
            ...prev,
            [questionId]: option
        }))
    }

    // Submit quiz
    const handleSubmitQuiz = async () => {
        if (!activeQuiz) return
        try {
            setIsSubmitting(true)
            setError(null)
            const res = await apiRequest(`/handwritten/${documentId}/quizzes/${activeQuiz.id}/submit`, {
                method: 'POST',
                body: JSON.stringify({ answers: userAnswers })
            })
            setSubmittedFeedback(res)
            // Update quiz in local state
            setQuizzes(prev => prev.map(q => q.id === activeQuiz.id ? { ...q, user_score: res.correct_count, user_answers: userAnswers } : q))
        } catch (err) {
            console.error('Submit quiz error:', err)
            setError(err.message || 'Failed to submit quiz.')
        } finally {
            setIsSubmitting(false)
        }
    }

    // Retake quiz
    const handleRetake = () => {
        setUserAnswers({})
        setSubmittedFeedback(null)
        setCurrentQuestionIdx(0)
    }

    return (
        <div className="intel-tab-container">
            {/* Toolbar */}
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
                                    Quiz #{quizzes.length - idx}: {q.title} ({q.difficulty})
                                </option>
                            ))}
                        </select>
                    )}
                </div>

                <div className="intel-actions-group">
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
                        <h4>Configure AI Quiz</h4>
                        <button type="button" className="config-close-btn" onClick={() => setShowConfig(false)}>×</button>
                    </div>
                    <div className="config-grid">
                        <div className="config-field">
                            <label>Difficulty</label>
                            <div className="config-pills">
                                {['easy', 'medium', 'hard'].map(lvl => (
                                    <button
                                        key={lvl}
                                        type="button"
                                        className={`config-pill ${difficulty === lvl ? 'active' : ''}`}
                                        onClick={() => setDifficulty(lvl)}
                                    >
                                        {lvl.toUpperCase()}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="config-field">
                            <label>Questions</label>
                            <div className="config-pills">
                                {[3, 5, 10].map(cnt => (
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
                                    { id: 'all', label: 'Mixed' },
                                    { id: 'multiple_choice', label: 'MCQ' },
                                    { id: 'true_false', label: 'True / False' }
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
                    </div>

                    <div className="config-actions">
                        <button
                            type="button"
                            className="btn-intel-primary"
                            onClick={handleGenerateQuiz}
                            disabled={generating}
                        >
                            <Sparkles size={14} />
                            <span>Generate {difficulty} Quiz ({questionCount} Qs)</span>
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
                            <p>Handwritten transcription has been revised. Generate a fresh quiz to test current notes.</p>
                        </div>
                    </div>
                    <button
                        type="button"
                        className="btn-outdated-regen"
                        onClick={handleGenerateQuiz}
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
                    <AlertTriangle size={16} />
                    <span>{error}</span>
                </div>
            )}

            {/* Generating Loader */}
            {generating && (
                <div className="intel-generating-card">
                    <div className="intel-spinner-orb">
                        <HelpCircle size={28} className="spin-icon" style={{ color: '#38bdf8' }} />
                    </div>
                    <h4>Crafting Interactive Quiz...</h4>
                    <p>Formulating grounded questions, verifying answer citations against transcribed pages, and building explanations with Llama 3.2.</p>
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
                    <h3>Test Your Mastery with AI Quizzes</h3>
                    <p>
                        Generate tailored quizzes (Easy, Medium, Hard) strictly grounded in your lecture notes.
                        Receive instant evaluations, source page citations, and clear explanations.
                    </p>
                    <button
                        type="button"
                        className="btn-intel-primary"
                        onClick={() => setShowConfig(true)}
                    >
                        <Sparkles size={16} />
                        <span>Create First Quiz</span>
                    </button>
                </div>
            )}

            {/* Active Quiz Runner */}
            {!generating && activeQuiz && currentQuestion && !submittedFeedback && (
                <div className="quiz-runner-card">
                    {/* Progress Bar & Header */}
                    <div className="quiz-runner-header">
                        <div className="quiz-progress-text">
                            <span className="q-number">Question {currentQuestionIdx + 1} of {questions.length}</span>
                            <span className="q-diff-badge">{activeQuiz.difficulty.toUpperCase()}</span>
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

                        {/* Options */}
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
                    </div>

                    {/* Navigation Controls */}
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
                            <span>{Object.keys(userAnswers).length} of {questions.length} Answered</span>
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
                                onClick={handleSubmitQuiz}
                                disabled={isSubmitting || Object.keys(userAnswers).length === 0}
                            >
                                <span>{isSubmitting ? 'Evaluating...' : 'Submit Answers'}</span>
                                <CheckCircle2 size={14} />
                            </button>
                        )}
                    </div>
                </div>
            )}

            {/* Results & Score Screen */}
            {!generating && submittedFeedback && (
                <div className="quiz-results-container">
                    {/* Score Hero Card */}
                    <div className="score-hero-card">
                        <div className="score-award-icon">
                            <Award size={36} style={{ color: submittedFeedback.score_percentage >= 70 ? '#34d399' : '#fbbf24' }} />
                        </div>
                        <h3 className="score-percentage-title">{submittedFeedback.score_percentage}%</h3>
                        <p className="score-subtitle">
                            You got {submittedFeedback.correct_count} out of {submittedFeedback.total_questions} questions correct!
                        </p>
                        <div className="results-actions">
                            <button
                                type="button"
                                className="btn-studio-action"
                                onClick={handleRetake}
                            >
                                <RotateCcw size={13} />
                                <span>Retake Quiz</span>
                            </button>
                            <button
                                type="button"
                                className="btn-studio-action btn-studio-primary"
                                onClick={() => setShowConfig(true)}
                            >
                                <Sparkles size={13} />
                                <span>Try Another Quiz</span>
                            </button>
                        </div>
                    </div>

                    {/* Feedback Breakdown List */}
                    <div className="results-breakdown-list">
                        <h4 className="breakdown-heading">Detailed Question Review</h4>
                        {(submittedFeedback.feedback || []).map((fb, idx) => (
                            <div
                                key={idx}
                                className={`review-card ${fb.is_correct ? 'correct-card' : 'incorrect-card'}`}
                            >
                                <div className="review-card-header">
                                    <div className="review-status-pill">
                                        {fb.is_correct ? (
                                            <>
                                                <CheckCircle2 size={14} style={{ color: '#34d399' }} />
                                                <span>Correct</span>
                                            </>
                                        ) : (
                                            <>
                                                <XCircle size={14} style={{ color: '#f87171' }} />
                                                <span>Incorrect</span>
                                            </>
                                        )}
                                    </div>
                                    <span className="page-citation-pill">Page {fb.page_number}</span>
                                </div>

                                <p className="review-question">{fb.question}</p>

                                <div className="review-answers-box">
                                    <div className="answer-line">
                                        <strong>Your Answer:</strong>
                                        <span className={fb.is_correct ? 'ans-correct' : 'ans-incorrect'}>
                                            {fb.user_answer || '(No answer provided)'}
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

