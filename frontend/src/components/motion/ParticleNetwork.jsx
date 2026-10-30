import { useEffect, useRef } from 'react'

export default function ParticleNetwork({
    className = '',
    particleCount = 50,
    maxDistance = 120,
    interactive = true,
}) {
    const canvasRef = useRef(null)

    useEffect(() => {
        const canvas = canvasRef.current
        if (!canvas) return

        const ctx = canvas.getContext('2d')
        if (!ctx) return

        let animationFrameId
        let isVisible = true

        // Particle configuration
        const colors = [
            { r: 139, g: 92, b: 246 },  // Electric violet
            { r: 56, g: 189, b: 248 },  // Soft cyan
            { r: 99, g: 102, b: 241 },  // Indigo
            { r: 168, g: 85, b: 247 },  // Purple
        ]

        let width = (canvas.width = canvas.parentElement?.clientWidth || window.innerWidth)
        let height = (canvas.height = canvas.parentElement?.clientHeight || window.innerHeight)

        const mouse = {
            x: -1000,
            y: -1000,
            radius: 140,
        }

        const handleResize = () => {
            if (!canvas.parentElement) return
            width = canvas.width = canvas.parentElement.clientWidth
            height = canvas.height = canvas.parentElement.clientHeight
        }

        const handleMouseMove = (e) => {
            if (!interactive) return
            const rect = canvas.getBoundingClientRect()
            mouse.x = e.clientX - rect.left
            mouse.y = e.clientY - rect.top
        }

        const handleMouseLeave = () => {
            mouse.x = -1000
            mouse.y = -1000
        }

        window.addEventListener('resize', handleResize)
        if (interactive && canvas.parentElement) {
            canvas.parentElement.addEventListener('mousemove', handleMouseMove)
            canvas.parentElement.addEventListener('mouseleave', handleMouseLeave)
        }

        // Initialize particles
        const count = Math.min(particleCount, Math.floor((width * height) / 18000))
        const particles = []

        for (let i = 0; i < count; i++) {
            const color = colors[Math.floor(Math.random() * colors.length)]
            particles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 0.7,
                vy: (Math.random() - 0.5) * 0.7,
                radius: Math.random() * 2 + 1.2,
                color,
                alpha: Math.random() * 0.5 + 0.3,
            })
        }

        // Pause animation when offscreen
        const observer = new IntersectionObserver(([entry]) => {
            isVisible = entry.isIntersecting
        })
        observer.observe(canvas)

        const render = () => {
            if (!isVisible) {
                animationFrameId = requestAnimationFrame(render)
                return
            }

            ctx.clearRect(0, 0, width, height)

            // Update & draw particles
            for (let i = 0; i < particles.length; i++) {
                const p = particles[i]

                p.x += p.vx
                p.y += p.vy

                // Bounce off edges smoothly
                if (p.x < 0 || p.x > width) p.vx *= -1
                if (p.y < 0 || p.y > height) p.vy *= -1

                // Mouse interaction: gentle push
                if (interactive && mouse.x > 0 && mouse.y > 0) {
                    const dx = mouse.x - p.x
                    const dy = mouse.y - p.y
                    const dist = Math.sqrt(dx * dx + dy * dy)
                    if (dist < mouse.radius) {
                        const force = (1 - dist / mouse.radius) * 1.5
                        p.x -= (dx / dist) * force
                        p.y -= (dy / dist) * force
                    }
                }

                // Draw particle node with subtle glow
                ctx.beginPath()
                ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2)
                ctx.fillStyle = `rgba(${p.color.r}, ${p.color.g}, ${p.color.b}, ${p.alpha})`
                ctx.shadowBlur = 8
                ctx.shadowColor = `rgba(${p.color.r}, ${p.color.g}, ${p.color.b}, 0.6)`
                ctx.fill()
                ctx.shadowBlur = 0

                // Connect to nearby particles
                for (let j = i + 1; j < particles.length; j++) {
                    const p2 = particles[j]
                    const dx = p.x - p2.x
                    const dy = p.y - p2.y
                    const dist = Math.sqrt(dx * dx + dy * dy)

                    if (dist < maxDistance) {
                        const lineAlpha = (1 - dist / maxDistance) * 0.22
                        ctx.beginPath()
                        ctx.moveTo(p.x, p.y)
                        ctx.lineTo(p2.x, p2.y)
                        ctx.strokeStyle = `rgba(139, 92, 246, ${lineAlpha})`
                        ctx.lineWidth = 0.8
                        ctx.stroke()
                    }
                }

                // Connect particle to mouse if within distance
                if (interactive && mouse.x > 0 && mouse.y > 0) {
                    const dx = mouse.x - p.x
                    const dy = mouse.y - p.y
                    const dist = Math.sqrt(dx * dx + dy * dy)
                    if (dist < maxDistance * 1.2) {
                        const lineAlpha = (1 - dist / (maxDistance * 1.2)) * 0.4
                        ctx.beginPath()
                        ctx.moveTo(p.x, p.y)
                        ctx.lineTo(mouse.x, mouse.y)
                        ctx.strokeStyle = `rgba(56, 189, 248, ${lineAlpha})`
                        ctx.lineWidth = 1
                        ctx.stroke()
                    }
                }
            }

            animationFrameId = requestAnimationFrame(render)
        }

        render()

        return () => {
            cancelAnimationFrame(animationFrameId)
            observer.disconnect()
            window.removeEventListener('resize', handleResize)
            if (interactive && canvas.parentElement) {
                canvas.parentElement.removeEventListener('mousemove', handleMouseMove)
                canvas.parentElement.removeEventListener('mouseleave', handleMouseLeave)
            }
        }
    }, [particleCount, maxDistance, interactive])

    return (
        <canvas
            ref={canvasRef}
            className={`particle-canvas ${className}`}
            style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                pointerEvents: 'none',
                zIndex: 1,
            }}
            aria-hidden="true"
        />
    )
}

