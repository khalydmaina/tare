import { useEffect, useRef } from 'react'

type Dot = { x: number; y: number; r: number; a: number; vx: number; vy: number }

type Props = {
  /** Pixels of area per dot: lower is denser */
  density?: number
  maxR?: number
  className?: string
}

/**
 * Drifting stipple field with a soft lift around the pointer.
 * Draws a still frame for reduced motion and pauses while off screen.
 */
export function StippleField({ density = 900, maxR = 1.8, className }: Props) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let w = 0
    let h = 0
    let raf = 0
    let dots: Dot[] = []
    let pointer: { x: number; y: number } | null = null

    const seed = () => {
      const count = Math.floor((w * h) / density)
      dots = Array.from({ length: count }, () => {
        const gx = Math.random()
        const gy = Math.random()
        const ridge = Math.exp(-(((gy - 0.42) / 0.22) ** 2)) * Math.exp(-(((gx - 0.5) / 0.38) ** 2))
        return {
          x: gx * w,
          y: gy * h,
          r: Math.random() * maxR + 0.35 + ridge * 1.1,
          a: 0.12 + ridge * 0.55 + Math.random() * 0.15,
          vx: (Math.random() - 0.5) * 0.12,
          vy: (Math.random() - 0.5) * 0.07,
        }
      })
    }

    const draw = (move: boolean) => {
      ctx.clearRect(0, 0, w, h)
      for (const d of dots) {
        if (move) {
          d.x += d.vx
          d.y += d.vy
          if (d.x < 0) d.x = w
          if (d.x > w) d.x = 0
          if (d.y < 0) d.y = h
          if (d.y > h) d.y = 0
        }
        const lift = pointer ? Math.max(0, 1 - Math.hypot(d.x - pointer.x, d.y - pointer.y) / 180) : 0
        ctx.beginPath()
        ctx.arc(d.x, d.y, d.r + lift * 0.8, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(240,240,240,${Math.min(1, d.a + lift * 0.35)})`
        ctx.fill()
      }
    }

    const resize = () => {
      w = canvas.clientWidth
      h = canvas.clientHeight
      canvas.width = Math.round(w * dpr)
      canvas.height = Math.round(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      seed()
      draw(false)
    }

    const loop = () => {
      draw(true)
      raf = requestAnimationFrame(loop)
    }

    const onMove = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect()
      pointer = { x: e.clientX - rect.left, y: e.clientY - rect.top }
    }

    resize()
    const resizeObserver = new ResizeObserver(resize)
    resizeObserver.observe(canvas)
    const visibility = new IntersectionObserver(([entry]) => {
      cancelAnimationFrame(raf)
      if (entry.isIntersecting && !reduce) raf = requestAnimationFrame(loop)
    })
    visibility.observe(canvas)
    window.addEventListener('pointermove', onMove, { passive: true })

    return () => {
      cancelAnimationFrame(raf)
      resizeObserver.disconnect()
      visibility.disconnect()
      window.removeEventListener('pointermove', onMove)
    }
  }, [density, maxR])

  return <canvas ref={ref} className={className} aria-hidden="true" />
}
