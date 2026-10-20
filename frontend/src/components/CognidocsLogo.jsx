import { useState, useEffect, useId } from 'react'

/**
 * Cognidocs Theme Metadata
 *
 * Requirements:
 * - Keep the approved Layered Pages concept and existing logo geometry.
 * - Upper page: clear cyan-to-teal gradient based on Ocean Teal (#00F2FE -> #13B8A6).
 * - Lower page: vivid violet gradient based on #8B5CF6, with #C4B5FD used sparingly as highlight.
 * - Same consistent symbol across all seven themes (no muddy orange/brown or shape-merging colors).
 * - Consistent deep navy (#0F172A) tile.
 * - Wordmark "Cogni" uses active theme primary text color var(--text-primary).
 * - "docs" accented in violet (#7C3AED on light themes for high contrast, #A855F7 on dark theme).
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
          x1="6"
          y1="4.5"
          x2="24"
          y2="15.5"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stopColor="#00F2FE" />
          <stop offset="100%" stopColor="#13B8A6" />
        </linearGradient>

        {/* Lower Page: Vivid Violet Gradient with #C4B5FD Fold Highlight */}
        <linearGradient
          id={lowerGradId}
          x1="5.5"
          y1="13.5"
          x2="24.5"
          y2="27.5"
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

      {/* Layer 1: Upper Page Ribbon (Cyan to Ocean Teal) */}
      <path
        d="M23.5 7.5C20.8 5 17 4.2 13.8 4.6C8.8 5.2 5 9.2 4.5 14.2C4.2 16.5 4.8 18.5 5.8 20.2L11.5 15.2C11 14 11 12.5 11.5 11.2C12.5 8.5 15 7.2 17.5 7.6C18.8 7.8 20 8.6 20.8 9.8L23.5 7.5Z"
        fill={`url(#${upperGradId})`}
      />

      {/* Layer 2: Lower Page Ribbon (Vivid Violet based on #8B5CF6) */}
      <path
        d="M5.2 13.5L4.5 15.5C4.2 17.8 4.8 20.2 6.5 22.5C8.8 25.8 12.8 27.5 16.8 27.5C20 27.5 22.8 26.2 24.5 24L21 20.5C19.8 21.8 18.2 22.5 16.5 22.4C13.8 22.2 11.8 20.2 11.5 17.2L5.2 13.5Z"
        fill={`url(#${lowerGradId})`}
      />

      {/* Layer 3 Highlight: Subtle #C4B5FD Fold Edge Accent */}
      <path
        d="M5.2 13.5L11.5 17.2"
        stroke="#C4B5FD"
        strokeWidth="0.9"
        strokeLinecap="round"
        opacity="0.9"
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
