/**
 * CognidocsLogo Component
 *
 * Clean, flat SVG emblem combining a folded document with the letter C.
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
  withBackground = true,
  className = '',
  title = 'Cognidocs Logo',
  style,
  ...props
}) {
  const svgMark = (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`cognidocs-logo-mark ${className}`.trim()}
      role="img"
      aria-label={title}
      style={{ display: 'block', borderRadius: 'inherit', ...style }}
      {...props}
    >
      <title>{title}</title>

      {/* Navy Squircle Foundation */}
      {withBackground && (
        <rect
          width="40"
          height="40"
          rx="10"
          fill="#0F172A"
        />
      )}

      {/* Folded Document Body forming the Letter "C" */}
      <path
        d="M13 9C11.3431 9 10 10.3431 10 12V28C10 29.6569 11.3431 31 13 31H27C28.6569 31 30 29.6569 30 28V25H22C19.7909 25 18 23.2091 18 21V19C18 16.7909 19.7909 15 22 15H30V15L24 9H13Z"
        fill="#8B5CF6"
      />

      {/* Top-Right Paper Fold Flap */}
      <path
        d="M24 9V15H30L24 9Z"
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
            width: typeof size === 'number' ? size : 40,
            height: typeof size === 'number' ? size : 40,
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
