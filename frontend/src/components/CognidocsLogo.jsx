import { useId } from 'react'

/**
 * CognidocsLogo Component
 *
 * Approved Brand Direction:
 * - Concept: Layered Pages forming a stylized letter C
 * - Style: Premium, clean, minimal, modern AI product
 * - Navy: #0F172A
 * - Violet: #8B5CF6
 * - Light Violet: #C4B5FD
 * - Wordmark: "Cognidocs"
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
          x1="6"
          y1="5.5"
          x2="16"
          y2="24"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stopColor="#0F172A" />
          <stop offset="60%" stopColor="#4C1D95" />
          <stop offset="100%" stopColor="#7C3AED" />
        </linearGradient>
        <linearGradient
          id={`${gradientId}-lower`}
          x1="8"
          y1="16"
          x2="24.5"
          y2="26.5"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stopColor="#6D28D9" />
          <stop offset="100%" stopColor="#8B5CF6" />
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

      {/* Layer 1: Upper Document Page & Spine Foundation (Navy-to-Violet gradient) */}
      <path
        d="M18.5 5.5H12C8.41 5.5 5.5 8.41 5.5 12V20C5.5 23.59 8.41 26.5 12 26.5H15C11.5 24.5 9.5 21 9.5 17.5V13C9.5 11.9 10.4 11 11.5 11H18.5V5.5Z"
        fill={`url(#${gradientId})`}
      />

      {/* Layer 2: Lower Document Page (Violet Layer overlapping spine with fold angle) */}
      <path
        d="M24.5 21V26.5H12C8.41 26.5 5.5 23.59 5.5 20V15.5L11.5 11.5V19C11.5 20.1 12.4 21 13.5 21H24.5Z"
        fill={`url(#${gradientId}-lower)`}
      />

      {/* Layer 3: Top-Right Folded Page Flap (Light Violet Accent) */}
      <path
        d="M18.5 5.5L24.5 11.5H18.5V5.5Z"
        fill="#C4B5FD"
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
