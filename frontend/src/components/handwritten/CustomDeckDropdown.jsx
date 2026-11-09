import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { Layers, ChevronDown, Check } from 'lucide-react'

/**
 * CustomDeckDropdown
 * Premium accessible dark dropdown for flashcard deck selection.
 * Replaces native HTML <select> with a polished dark navy glass selector,
 * structured deck number + title + card count typography, smooth animations,
 * viewport auto-flip positioning, and full keyboard accessibility.
 */
export default function CustomDeckDropdown({
    decks = [],
    activeDeckId,
    onSelectDeck,
    className = '',
    id = 'custom-deck-dropdown'
}) {
    const [isOpen, setIsOpen] = useState(false)
    const [openUpward, setOpenUpward] = useState(false)
    const [highlightedIndex, setHighlightedIndex] = useState(-1)
    const containerRef = useRef(null)
    const listRef = useRef(null)

    // Format deck options with reverse chronological numbering
    const formattedDecks = useMemo(() => {
        return decks.map((d, idx) => ({
            id: d.id,
            deckNumber: decks.length - idx,
            title: d.title || 'Untitled Deck',
            cardCount: d.cards?.length || 0
        }))
    }, [decks])

    // Currently selected deck
    const selectedDeck = useMemo(() => {
        return formattedDecks.find(d => d.id === activeDeckId) || formattedDecks[0] || null
    }, [formattedDecks, activeDeckId])

    // Toggle dropdown with viewport boundary collision detection
    const handleToggle = () => {
        if (!isOpen && containerRef.current) {
            const rect = containerRef.current.getBoundingClientRect()
            const spaceBelow = window.innerHeight - rect.bottom
            // If less than 320px below and more space above, open upward
            if (spaceBelow < 320 && rect.top > spaceBelow) {
                setOpenUpward(true)
            } else {
                setOpenUpward(false)
            }
        }
        setIsOpen(prev => !prev)
    }

    // Close when clicking outside
    useEffect(() => {
        function handleClickOutside(event) {
            if (containerRef.current && !containerRef.current.contains(event.target)) {
                setIsOpen(false)
            }
        }

        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside)
            document.addEventListener('touchstart', handleClickOutside)
        }
        return () => {
            document.removeEventListener('mousedown', handleClickOutside)
            document.removeEventListener('touchstart', handleClickOutside)
        }
    }, [isOpen])

    // Keyboard navigation
    const handleKeyDown = useCallback((e) => {
        if (!isOpen) {
            if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
                e.preventDefault()
                if (containerRef.current) {
                    const rect = containerRef.current.getBoundingClientRect()
                    const spaceBelow = window.innerHeight - rect.bottom
                    if (spaceBelow < 320 && rect.top > spaceBelow) {
                        setOpenUpward(true)
                    } else {
                        setOpenUpward(false)
                    }
                }
                setIsOpen(true)
                const currentIndex = formattedDecks.findIndex(d => d.id === activeDeckId)
                setHighlightedIndex(currentIndex >= 0 ? currentIndex : 0)
            }
            return
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault()
                setHighlightedIndex(prev => (prev < formattedDecks.length - 1 ? prev + 1 : 0))
                break
            case 'ArrowUp':
                e.preventDefault()
                setHighlightedIndex(prev => (prev > 0 ? prev - 1 : formattedDecks.length - 1))
                break
            case 'Enter':
            case ' ':
                e.preventDefault()
                if (highlightedIndex >= 0 && highlightedIndex < formattedDecks.length) {
                    onSelectDeck(formattedDecks[highlightedIndex].id)
                    setIsOpen(false)
                }
                break
            case 'Escape':
                e.preventDefault()
                setIsOpen(false)
                break
            case 'Tab':
                setIsOpen(false)
                break
            default:
                break
        }
    }, [isOpen, highlightedIndex, formattedDecks, activeDeckId, onSelectDeck])

    // Scroll highlighted item into view
    useEffect(() => {
        if (isOpen && highlightedIndex >= 0 && listRef.current) {
            const items = listRef.current.querySelectorAll('.custom-deck-item')
            if (items[highlightedIndex]) {
                items[highlightedIndex].scrollIntoView({ block: 'nearest' })
            }
        }
    }, [isOpen, highlightedIndex])

    const handleSelect = (deckId) => {
        if (onSelectDeck) {
            onSelectDeck(deckId)
        }
        setIsOpen(false)
    }

    if (!selectedDeck) {
        return null
    }

    return (
        <div
            ref={containerRef}
            className={`custom-deck-dropdown ${className} ${isOpen ? 'is-open' : ''} ${openUpward ? 'open-upward' : ''}`}
            onKeyDown={handleKeyDown}
        >
            <button
                type="button"
                id={id}
                className="custom-deck-trigger"
                onClick={handleToggle}
                aria-haspopup="listbox"
                aria-expanded={isOpen}
                title={`Deck #${selectedDeck.deckNumber}: ${selectedDeck.title} (${selectedDeck.cardCount} cards)`}
            >
                <div className="trigger-deck-info">
                    <Layers size={14} className="trigger-deck-icon" />
                    <span className="trigger-deck-num">Deck #{selectedDeck.deckNumber}:</span>
                    <span className="trigger-deck-title">{selectedDeck.title}</span>
                    <span className="trigger-deck-count">({selectedDeck.cardCount} cards)</span>
                </div>
                <ChevronDown size={14} className={`trigger-deck-chevron ${isOpen ? 'rotate' : ''}`} />
            </button>

            {isOpen && (
                <div
                    ref={listRef}
                    className={`custom-deck-menu ${openUpward ? 'menu-upward' : 'menu-downward'}`}
                    role="listbox"
                    aria-activedescendant={highlightedIndex >= 0 ? `deck-opt-${highlightedIndex}` : undefined}
                >
                    <div className="custom-deck-list-inner">
                        {formattedDecks.map((d, index) => {
                            const isSelected = d.id === selectedDeck.id
                            const isHighlighted = index === highlightedIndex

                            return (
                                <button
                                    key={d.id}
                                    id={`deck-opt-${index}`}
                                    type="button"
                                    role="option"
                                    aria-selected={isSelected}
                                    className={`custom-deck-item ${isSelected ? 'selected' : ''} ${isHighlighted ? 'highlighted' : ''}`}
                                    onClick={() => handleSelect(d.id)}
                                    onMouseEnter={() => setHighlightedIndex(index)}
                                    title={`Deck #${d.deckNumber}: ${d.title} (${d.cardCount} cards)`}
                                >
                                    <div className="deck-item-left">
                                        <span className="deck-item-num">Deck #{d.deckNumber}:</span>
                                        <span className="deck-item-title">{d.title}</span>
                                    </div>
                                    <div className="deck-item-right">
                                        <span className="deck-item-count">{d.cardCount} cards</span>
                                        {isSelected && <Check size={14} className="deck-item-check" />}
                                    </div>
                                </button>
                            )
                        })}
                    </div>
                </div>
            )}
        </div>
    )
}

