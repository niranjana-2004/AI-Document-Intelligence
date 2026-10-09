import { useState } from 'react'
import { apiRequest } from '../services/api'
import '../App.css'

function AskAI() {
    const [question, setQuestion] = useState('')
    const [answer, setAnswer] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    const suggestedQuestions = [
        'What are my skills?',
        'What projects have I done?',
        'What certifications do I have?',
        'What is my educational background?',
    ]

    const handleAskAI = async () => {
        if (!question.trim()) {
            return
        }

        try {
            setLoading(true)
            setAnswer('')
            setError('')

            const data = await apiRequest(
                '/documents/ask',
                {
                    method: 'POST',
                    body: JSON.stringify({
                        query: question,
                        document_id: null,
                        top_k: 12,
                    }),
                }
            )

            const aiAnswer =
                data.answer ||
                data.response ||
                data.result ||
                'No answer returned.'

            setAnswer(aiAnswer)

        } catch (error) {
            console.error(
                'Ask AI error:',
                error
            )

            setError(
                error.message ||
                'Failed to get an answer.'
            )

        } finally {
            setLoading(false)
        }
    }

    const handleSuggestedQuestion = (suggestion) => {
        setQuestion(suggestion)
        setAnswer('')
        setError('')
    }

    const handleClear = () => {
        setQuestion('')
        setAnswer('')
        setError('')
    }

    return (
        <main className="ask-ai-page">

            {/* =================================
                PAGE HEADER
            ================================= */}

            <section className="ask-ai-header">

                <div>

                    <p className="eyebrow">
                        AI DOCUMENT ASSISTANT
                    </p>

                    <h2>
                        Ask AI
                    </h2>

                    <p>
                        Ask questions and get answers based
                        on the information in your documents.
                    </p>

                </div>

            </section>


            {/* =================================
                SUGGESTED QUESTIONS
            ================================= */}

            <section className="suggestions-section">

                <div className="section-header">

                    <div>

                        <h3>
                            Try asking
                        </h3>

                        <p>
                            Start with one of these questions
                        </p>

                    </div>

                </div>

                <div className="suggestion-list">

                    {suggestedQuestions.map(
                        (suggestion) => (

                            <button
                                key={suggestion}
                                className="suggestion-button"
                                onClick={() =>
                                    handleSuggestedQuestion(
                                        suggestion
                                    )
                                }
                            >
                                {suggestion}
                            </button>

                        )
                    )}

                </div>

            </section>


            {/* =================================
                QUESTION SECTION
            ================================= */}

            <section className="ask-ai-card">

                <div className="ask-ai-card-header">

                    <div>

                        <h3>
                            Your question
                        </h3>

                        <p>
                            Ask anything about your uploaded
                            documents.
                        </p>

                    </div>

                    {(question || answer) && (

                        <button
                            className="clear-button"
                            onClick={handleClear}
                        >
                            Clear
                        </button>

                    )}

                </div>


                <textarea
                    className="ask-ai-input"
                    placeholder="Example: What projects have I worked on?"
                    value={question}
                    onChange={(event) =>
                        setQuestion(event.target.value)
                    }
                    onKeyDown={(event) => {

                        if (
                            event.key === 'Enter' &&
                            !event.shiftKey
                        ) {
                            event.preventDefault()
                            handleAskAI()
                        }

                    }}
                />


                <div className="ask-ai-input-footer">

                    <span>
                        Press Enter to ask · Shift + Enter
                        for a new line
                    </span>

                    <button
                        className="ask-ai-button"
                        onClick={handleAskAI}
                        disabled={
                            loading ||
                            !question.trim()
                        }
                    >
                        {loading
                            ? 'Thinking...'
                            : 'Ask AI →'}
                    </button>

                </div>

            </section>


            {/* =================================
                ERROR
            ================================= */}

            {error && (

                <div className="ask-ai-error">
                    {error}
                </div>

            )}


            {/* =================================
                AI ANSWER
            ================================= */}

            {loading && (

                <section className="answer-card">

                    <div className="answer-header">

                        <div className="answer-icon">
                            AI
                        </div>

                        <div>

                            <h3>
                                AI Answer
                            </h3>

                            <p>
                                Searching your documents...
                            </p>

                        </div>

                    </div>

                    <div className="answer-loading">

                        <span></span>
                        <span></span>
                        <span></span>

                    </div>

                </section>

            )}


            {!loading && answer && (

                <section className="answer-card">

                    <div className="answer-header">

                        <div className="answer-icon">
                            AI
                        </div>

                        <div>

                            <h3>
                                AI Answer
                            </h3>

                            <p>
                                Generated from your document
                                knowledge base
                            </p>

                        </div>

                    </div>


                    <div className="answer-content">
                        {answer}
                    </div>

                </section>

            )}


            {/* =================================
                EMPTY STATE
            ================================= */}

            {!loading &&
                !answer &&
                !error && (

                    <section className="ask-ai-empty">

                        <div className="ask-ai-empty-icon">
                            ✦
                        </div>

                        <h3>
                            Your documents are ready
                        </h3>

                        <p>
                            Ask a question above and AI will
                            search your document knowledge base
                            to find the most relevant information.
                        </p>

                    </section>

                )}

        </main>
    )
}

export default AskAI