import { useId } from 'react'

/**
 * CognidocsLogo Component
 *
 * Clean, flat SVG emblem visibly combining:
 * - A recognizable document silhouette
 * - A folded top-right corner in light violet (#C4B5FD)
 * - A bold C-shaped form using navy (#0F172A) and violet (#8B5CF6)
 * - Three simple document lines
 *
 * Brand Identity Tokens:
 * - Navy: #0F172A
 * - Violet: #8B5CF6
 * - Light Violet: #C4B5FD
 * - Tagline: "Knowledge, unlocked."
 */
function CognidocsLogo({
  size = '100%',
  variant = 'mark',
  withBackground = false,
  className = '',
  title = 'Cognidocs Logo',
  style,
  ...props
}) {
  const gradientId = useId()

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
        <linearGradient
          id={gradientId}
          x1="9"
          y1="10"
          x2="18"
          y2="22"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#0F172A" />
          <stop offset="1" stopColor="#8B5CF6" />
        </linearGradient>
      </defs>

      {/* Optional Standalone Base Tile (disabled by default to preserve container gradients) */}
      {withBackground && (
        <rect
          width="32"
          height="32"
          rx="8"
          fill="#0F172A"
        />
      )}

      {/* 1. Recognizable Document Silhouette (with subtle border for light backgrounds) */}
      <path
        d="M7 3C5.89543 3 5 3.89543 5 5V27C5 28.1046 5.89543 29 7 29H25C26.1046 29 27 28.1046 27 27V11L19 3H7Z"
        fill="#FFFFFF"
        stroke="#CBD5E1"
        strokeWidth="0.75"
        strokeLinejoin="round"
      />

      {/* 2. Folded Top-Right Corner in Light Violet */}
      <path
        d="M19 3V11H27L19 3Z"
        fill="#C4B5FD"
      />
      <path
        d="M19 11L27 11"
        stroke="#A78BFA"
        strokeWidth="0.5"
        strokeOpacity="0.6"
      />

      {/* 3. Bold C-Shaped Form in Navy & Violet */}
      <path
        d="M18 10H13C10.7909 10 9 11.7909 9 14V18C9 20.2091 10.7909 22 13 22H18"
        stroke={`url(#${gradientId})`}
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* 4. Three Simple Document Lines */}
      <rect
        x="15"
        y="14"
        width="7"
        height="1.6"
        rx="0.8"
        fill="#8B5CF6"
      />
      <rect
        x="15"
        y="17"
        width="5.5"
        height="1.6"
        rx="0.8"
        fill="#8B5CF6"
        fillOpacity="0.75"
      />
      <rect
        x="15"
        y="20"
        width="4"
        height="1.6"
        rx="0.8"
        fill="#8B5CF6"
        fillOpacity="0.5"
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
              color: 'var(--text-primary, #0F172A)',
              letterSpacing: '-0.2px',
              lineHeight: 1.2,
            }}
          >
            Cognidocs
          </span>
          <span
            style={{
              fontSize: '11px',
              color: 'var(--text-muted, #94A3B8)',
              fontWeight: 500,
              letterSpacing: '0.4px',
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
