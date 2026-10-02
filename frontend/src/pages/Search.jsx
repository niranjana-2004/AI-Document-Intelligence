import { useState } from 'react'
import '../App.css'

const API_URL = 'http://127.0.0.1:8000'

function Search() {
    const [query, setQuery] = useState('')
    const [results, setResults] = useState([])

    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    const [hasSearched, setHasSearched] = useState(false)

    const handleSearch = async () => {
        if (!query.trim()) {
            return
        }

        try {
            setLoading(true)
            setError('')
            setResults([])
            setHasSearched(true)

            const response = await fetch(
                `${API_URL}/documents/search?query=${encodeURIComponent(
                    query
                )}&top_k=5`
            )

            if (!response.ok) {
                const errorData =
                    await response
                        .json()
                        .catch(() => null)

                throw new Error(
                    errorData?.detail ||
                    'Search failed.'
                )
            }

            const data = await response.json()

            setResults(data.results || [])

        } catch (error) {
            console.error(
                'Search error:',
                error
            )

            setError(
                error.message ||
                'Unable to complete the search.'
            )

        } finally {
            setLoading(false)
        }
    }


    const handleKeyDown = (event) => {
        if (
            event.key === 'Enter' &&
            !event.shiftKey
        ) {
            event.preventDefault()
            handleSearch()
        }
    }


    const handleClear = () => {
        setQuery('')
        setResults([])
        setError('')
        setHasSearched(false)
    }


    return (
        <main className="search-page">

            {/* =================================
          PAGE HEADER
      ================================= */}

            <section className="search-page-header">

                <div>

                    <p className="eyebrow">
                        DOCUMENT DISCOVERY
                    </p>

                    <h2>
                        Search
                    </h2>

                    <p>
                        Find relevant information across
                        your document knowledge base.
                    </p>

                </div>

            </section>


            {/* =================================
          SEARCH BOX
      ================================= */}

            <section className="search-box-card">

                <div className="search-box-header">

                    <div>

                        <h3>
                            Semantic Search
                        </h3>

                        <p>
                            Search by meaning, not just exact
                            keywords.
                        </p>

                    </div>

                    {(query || hasSearched) && (

                        <button
                            className="clear-search-button"
                            onClick={handleClear}
                        >
                            Clear
                        </button>

                    )}

                </div>


                <div className="search-input-row">

                    <input
                        className="full-search-input"
                        type="text"
                        placeholder="What would you like to find?"
                        value={query}
                        onChange={(event) =>
                            setQuery(event.target.value)
                        }
                        onKeyDown={handleKeyDown}
                    />

                    <button
                        className="search-submit-button"
                        onClick={handleSearch}
                        disabled={
                            loading ||
                            !query.trim()
                        }
                    >
                        {loading
                            ? 'Searching...'
                            : 'Search'}
                    </button>

                </div>


                <p className="search-hint">
                    Press Enter to search
                </p>

            </section>


            {/* =================================
          ERROR
      ================================= */}

            {error && (

                <div className="search-error">
                    {error}
                </div>

            )}


            {/* =================================
          LOADING
      ================================= */}

            {loading && (

                <section className="search-loading-card">

                    <div className="search-loading-icon">
                        ⌕
                    </div>

                    <h3>
                        Searching your documents...
                    </h3>

                    <p>
                        Finding the most relevant information
                        from your document knowledge base.
                    </p>

                    <div className="search-loading-dots">

                        <span></span>
                        <span></span>
                        <span></span>

                    </div>

                </section>

            )}


            {/* =================================
          RESULTS
      ================================= */}

            {!loading &&
                hasSearched &&
                !error &&
                results.length > 0 && (

                    <section className="search-results-section">

                        <div className="search-results-header">

                            <div>

                                <h3>
                                    Search Results
                                </h3>

                                <p>
                                    Found {results.length}{' '}
                                    relevant{' '}
                                    {results.length === 1
                                        ? 'result'
                                        : 'results'}
                                </p>

                            </div>

                        </div>


                        <div className="search-results-list">

                            {results.map(
                                (result, index) => (

                                    <article
                                        className="search-result-card"
                                        key={
                                            result.id ||
                                            result.chunk_id ||
                                            index
                                        }
                                    >

                                        <div className="search-result-top">

                                            <div className="search-result-number">
                                                {String(index + 1).padStart(
                                                    2,
                                                    '0'
                                                )}
                                            </div>

                                            <div className="search-result-meta">

                                                {result.filename && (
                                                    <span>
                                                        {result.filename}
                                                    </span>
                                                )}

                                                {result.document_type && (
                                                    <span>
                                                        {result.document_type}
                                                    </span>
                                                )}

                                            </div>

                                        </div>


                                        <div className="search-result-content">

                                            <p>
                                                {result.content ||
                                                    result.text ||
                                                    'No content available.'}
                                            </p>

                                        </div>


                                        {(result.score !== undefined ||
                                            result.similarity !==
                                            undefined) && (

                                                <div className="search-result-footer">

                                                    <span>
                                                        Relevance
                                                    </span>

                                                    <strong>
                                                        {Math.round(
                                                            (result.score ??
                                                                result.similarity) *
                                                            100
                                                        )}
                                                        %
                                                    </strong>

                                                </div>

                                            )}

                                    </article>

                                )
                            )}

                        </div>

                    </section>

                )}


            {/* =================================
          NO RESULTS
      ================================= */}

            {!loading &&
                hasSearched &&
                !error &&
                results.length === 0 && (

                    <section className="search-empty">

                        <div className="search-empty-icon">
                            ⌕
                        </div>

                        <h3>
                            No relevant information found
                        </h3>

                        <p>
                            Try using different words or
                            asking your question in another
                            way.
                        </p>

                    </section>

                )}


            {/* =================================
          INITIAL STATE
      ================================= */}

            {!hasSearched && (

                <section className="search-initial">

                    <div className="search-initial-icon">
                        ⌕
                    </div>

                    <h3>
                        Search your documents
                    </h3>

                    <p>
                        Enter a topic, concept, or question
                        above. The search engine will find
                        relevant information based on meaning
                        and context.
                    </p>

                </section>

            )}

        </main>
    )
}

export default Search