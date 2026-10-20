import { useState, useEffect, useId } from 'react'

/**
 * Cognidocs Theme Metadata & Palettes
 *
 * Requirements:
 * - Approved Layered Pages concept forming a clean, recognizable C.
 * - Upper page: clear cyan-to-teal gradient based on Ocean Teal (#00F2FE -> #13B8A6).
 * - Lower page: vivid violet gradient based on #8B5CF6, with #C4B5FD used sparingly as highlight.
 * - Distinct silhouettes and endpoints: upper page has a distinct top-right folio head,
 *   lower page has a distinct bottom-right folio foot, and an overlapping spine fold.
 * - Same consistent symbol across all seven themes.
 * - Consistent deep navy (#0F172A) tile.
 * - Wordmark "Cogni" uses active theme primary text color var(--text-primary).
 * - "docs" accented in accessible violet (#7C3AED on light themes for high contrast, #A855F7 on dark theme).
 * - Tagline uses active theme secondary text color var(--text-secondary).
 */
const DARK_THEMES = new Set(['dark'])

function resolveActiveTheme(explicitTheme) {
  if (explicitTheme) {
    return explicitTheme
  }
  if (typeof document !== 'undefined' && document.documentElement.dataset.theme) {
    return document.documentElement.dataset.theme
  }
  if (typeof window !== 'undefined') {
    const saved = localStorage.getItem('app_theme')
    if (saved) {
      return saved
    }
  }
  return 'ocean'
}

/**
 * CognidocsLogo Component
 */
function CognidocsLogo({
  size = '100%',
  variant = 'mark',
  withBackground = false,
  theme = null,
  className = '',
  title = 'Cognidocs Logo',
  style,
  ...props
}) {
  const baseId = useId()
  const upperGradId = `${baseId}-upper`
  const lowerGradId = `${baseId}-lower`

  const [domTheme, setDomTheme] = useState(() => resolveActiveTheme(theme))

  useEffect(() => {
    if (theme) {
      return
    }

    // Observe changes to document.documentElement.dataset.theme
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (
          mutation.type === 'attributes' &&
          mutation.attributeName === 'data-theme'
        ) {
          setDomTheme(resolveActiveTheme())
        }
      }
    })

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })

    const handleStorage = (event) => {
      if (event.key === 'app_theme') {
        setDomTheme(resolveActiveTheme())
      }
    }

    window.addEventListener('storage', handleStorage)

    return () => {
      observer.disconnect()
      window.removeEventListener('storage', handleStorage)
    }
  }, [theme])

  const activeTheme = theme || domTheme
  const isDark = DARK_THEMES.has(activeTheme)

  // Accessible violet accent for "docs": #A855F7 on dark (8.5:1), #7C3AED on light (>5.5:1)
  const docsAccentColor = isDark ? '#A855F7' : '#7C3AED'

  const svgMark = (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`cognidocs-logo-mark ${className}`.trim()}
      role="img"
      aria-label={title}
      style={{ display: 'block', borderRadius: 'inherit', ...style }}
      {...props}
    >
      <title>{title}</title>

      <defs>
        {/* Upper Page: Clear Cyan to Ocean Teal Gradient */}
        <linearGradient
          id={upperGradId}
          x1="4"
          y1="4"
          x2="26.5"
          y2="15"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stopColor="#00F2FE" />
          <stop offset="100%" stopColor="#13B8A6" />
        </linearGradient>

        {/* Lower Page: Vivid Violet Gradient with #C4B5FD Fold Highlight */}
        <linearGradient
          id={lowerGradId}
          x1="4"
          y1="13"
          x2="26.5"
          y2="28"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stopColor="#C4B5FD" />
          <stop offset="22%" stopColor="#8B5CF6" />
          <stop offset="100%" stopColor="#6D28D9" />
        </linearGradient>
      </defs>

      {/* Optional Standalone Base Tile: Consistent Deep Navy (#0F172A) */}
      {withBackground && (
        <rect
          width="32"
          height="32"
          rx="8"
          fill="#0F172A"
          stroke="rgba(19, 184, 166, 0.22)"
          strokeWidth="0.8"
        />
      )}

      {/* Layer 1: Upper Document Page (Cyan to Ocean Teal) - Distinct top-right folio head */}
      <path
        d="M26.5 4H15C9 4 4.5 8.5 3.8 14.5C3.5 16.8 4 19 5.2 20.8L12.8 14.5C12.2 13.5 12 12.2 12.5 11C13.5 8.5 16 7.5 18.5 7.8H26.5V4Z"
        fill={`url(#${upperGradId})`}
      />

      {/* Layer 2: Lower Document Page (Vivid Violet) - Distinct bottom-right folio foot & overlapping spine */}
      <path
        d="M3.8 12.5L12.8 17.5C12 19 12.2 20.5 13.2 21.8C14.5 23.2 16.5 24 18.8 24H26.5V28H15C9 28 4.5 23.5 3.8 17.5C3.5 15.5 3.5 14 3.8 12.5Z"
        fill={`url(#${lowerGradId})`}
      />

      {/* Layer 3 Highlight: Delicate #C4B5FD Fold Edge Accent */}
      <path
        d="M3.8 12.5L12.8 17.5"
        stroke="#C4B5FD"
        strokeWidth="1.1"
        strokeLinecap="round"
        opacity="0.95"
      />
    </svg>
  )

  if (variant === 'full') {
    return (
      <div
        className={`cognidocs-brand-lockup ${className}`.trim()}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '12px',
          ...style,
        }}
        {...props}
      >
        <div
          style={{
            width: typeof size === 'number' ? size : 32,
            height: typeof size === 'number' ? size : 32,
            flexShrink: 0,
          }}
        >
          {svgMark}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span
            style={{
              fontWeight: 800,
              fontSize: '17px',
              color: 'var(--text-primary, #12363d)',
              letterSpacing: '-0.2px',
              lineHeight: 1.2,
              fontFamily: 'inherit',
            }}
          >
            Cogni
            <span
              style={{
                color: docsAccentColor,
              }}
            >
              docs
            </span>
          </span>
          <span
            style={{
              fontSize: '11px',
              color: 'var(--text-secondary, #4f7077)',
              fontWeight: 500,
              letterSpacing: '0.4px',
              fontFamily: 'inherit',
            }}
          >
            Knowledge, unlocked.
          </span>
        </div>
      </div>
    )
  }

  return svgMark
}

export default CognidocsLogo
