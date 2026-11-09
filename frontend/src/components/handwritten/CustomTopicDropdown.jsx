import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { Filter, ChevronDown, Check } from 'lucide-react'

/**
 * CustomTopicDropdown
 * Premium accessible dark dropdown for topic filtering and selection.
 * Replaces native HTML <select> with styled dark glass surface, smooth animations,
 * click-outside detection, and keyboard accessibility.
 */
export default function CustomTopicDropdown({
    value = 'all',
    onChange,
    options = [],
    allLabel = 'All Topics',
    className = '',
    icon: CustomIcon = Filter,
    id = 'custom-topic-dropdown'
}) {
    const [isOpen, setIsOpen] = useState(false)
    const [highlightedIndex, setHighlightedIndex] = useState(-1)
    const containerRef = useRef(null)
    const listRef = useRef(null)

    // Complete list including 'all'
    const fullOptions = useMemo(() => [
        { value: 'all', label: allLabel },
        ...options.map(opt => ({ value: opt, label: opt }))
    ], [allLabel, options])

    // Find current display label
    const selectedOption = fullOptions.find(opt => opt.value === value) || fullOptions[0]

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
                setIsOpen(true)
                const currentIndex = fullOptions.findIndex(opt => opt.value === value)
                setHighlightedIndex(currentIndex >= 0 ? currentIndex : 0)
            }
            return
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault()
                setHighlightedIndex(prev => (prev < fullOptions.length - 1 ? prev + 1 : 0))
                break
            case 'ArrowUp':
                e.preventDefault()
                setHighlightedIndex(prev => (prev > 0 ? prev - 1 : fullOptions.length - 1))
                break
            case 'Enter':
            case ' ':
                e.preventDefault()
                if (highlightedIndex >= 0 && highlightedIndex < fullOptions.length) {
                    onChange(fullOptions[highlightedIndex].value)
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
    }, [isOpen, highlightedIndex, fullOptions, value, onChange])

    // Scroll highlighted item into view
    useEffect(() => {
        if (isOpen && highlightedIndex >= 0 && listRef.current) {
            const items = listRef.current.querySelectorAll('.custom-topic-item')
            if (items[highlightedIndex]) {
                items[highlightedIndex].scrollIntoView({ block: 'nearest' })
            }
        }
    }, [isOpen, highlightedIndex])

    const handleSelect = (val) => {
        if (onChange) {
            onChange(val)
        }
        setIsOpen(false)
    }

    return (
        <div
            ref={containerRef}
            className={`custom-topic-dropdown ${className} ${isOpen ? 'is-open' : ''}`}
            onKeyDown={handleKeyDown}
        >
            <button
                type="button"
                id={id}
                className="custom-topic-trigger"
                onClick={() => setIsOpen(!isOpen)}
                aria-haspopup="listbox"
                aria-expanded={isOpen}
                title={selectedOption.label}
            >
                <div className="trigger-left">
                    <CustomIcon size={12} className="trigger-icon" />
                    <span className="trigger-label">{selectedOption.label}</span>
                </div>
                <ChevronDown size={13} className={`trigger-chevron ${isOpen ? 'rotate' : ''}`} />
            </button>

            {isOpen && (
                <div
                    ref={listRef}
                    className="custom-topic-menu"
                    role="listbox"
                    aria-activedescendant={highlightedIndex >= 0 ? `opt-${highlightedIndex}` : undefined}
                >
                    <div className="custom-topic-list-inner">
                        {fullOptions.map((opt, index) => {
                            const isSelected = opt.value === value
                            const isHighlighted = index === highlightedIndex

                            return (
                                <button
                                    key={opt.value}
                                    id={`opt-${index}`}
                                    type="button"
                                    role="option"
                                    aria-selected={isSelected}
                                    className={`custom-topic-item ${isSelected ? 'selected' : ''} ${isHighlighted ? 'highlighted' : ''}`}
                                    onClick={() => handleSelect(opt.value)}
                                    onMouseEnter={() => setHighlightedIndex(index)}
                                    title={opt.label}
                                >
                                    <span className="item-label">{opt.label}</span>
                                    {isSelected && <Check size={13} className="item-check" />}
                                </button>
                            )
                        })}
                    </div>
                </div>
            )}
        </div>
    )
}
