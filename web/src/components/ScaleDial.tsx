import { motion, useReducedMotion } from 'framer-motion'

type Props = {
  stated: number
  calibrated: number
  size?: number
  label?: string
}

/** Dual reading: gross (stated) vs net (calibrated) - the product metaphor. */
export function ScaleDial({ stated, calibrated, size = 280, label }: Props) {
  const reduce = useReducedMotion()
  const r = size * 0.36
  const cx = size / 2
  const cy = size / 2 + 8
  const toXY = (pct: number, radius = r) => {
    const a = Math.PI * (1 - pct / 100)
    return { x: cx + radius * Math.cos(a), y: cy - radius * Math.sin(a) }
  }
  const gross = toXY(stated)
  const net = toXY(calibrated)
  const gap = stated - calibrated

  return (
    <div className="relative inline-flex flex-col items-center">
      <svg width={size} height={size * 0.72} viewBox={`0 0 ${size} ${size * 0.72}`} className="overflow-visible">
        <defs>
          <linearGradient id="arcTrack" x1="0" x2="1">
            <stop offset="0%" stopColor="#222" />
            <stop offset="100%" stopColor="#333" />
          </linearGradient>
        </defs>
        {/* Arc track */}
        <path
          d={`M ${toXY(0).x} ${toXY(0).y} A ${r} ${r} 0 0 1 ${toXY(100).x} ${toXY(100).y}`}
          fill="none"
          stroke="url(#arcTrack)"
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* Overconfidence band (calibrated → stated) */}
        <path
          d={`M ${net.x} ${net.y} A ${r} ${r} 0 0 1 ${gross.x} ${gross.y}`}
          fill="none"
          stroke="#EF4444"
          strokeWidth="10"
          strokeLinecap="round"
          opacity="0.55"
        />
        {/* Calibrated arc */}
        <path
          d={`M ${toXY(0).x} ${toXY(0).y} A ${r} ${r} 0 0 1 ${net.x} ${net.y}`}
          fill="none"
          stroke="#22C55E"
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* Needles */}
        <motion.line
          x1={cx}
          y1={cy}
          x2={gross.x}
          y2={gross.y}
          stroke="#FFFFFF"
          strokeWidth="2.5"
          strokeLinecap="round"
          initial={reduce ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
        />
        <motion.line
          x1={cx}
          y1={cy}
          x2={net.x}
          y2={net.y}
          stroke="#22C55E"
          strokeWidth="2.5"
          strokeLinecap="round"
          initial={reduce ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        />
        <circle cx={cx} cy={cy} r="6" fill="#111" stroke="#fff" strokeWidth="2" />
        {/* Labels */}
        <text x={toXY(0, r + 18).x} y={toXY(0, r + 18).y} fill="#A3A3A3" fontSize="11" fontFamily="IBM Plex Mono">
          0
        </text>
        <text
          x={toXY(100, r + 18).x - 14}
          y={toXY(100, r + 18).y}
          fill="#A3A3A3"
          fontSize="11"
          fontFamily="IBM Plex Mono"
        >
          100
        </text>
      </svg>

      <div className="mt-[-0.5rem] grid grid-cols-3 gap-4 text-center">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-mute">Gross</div>
          <div className="tabular text-2xl text-white">{stated}%</div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-wide text-mute">Gap</div>
          <div className="tabular text-2xl text-danger">-{gap}</div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-wide text-mute">Net</div>
          <div className="tabular text-2xl text-guarded">{calibrated}%</div>
        </div>
      </div>
      {label ? <p className="mt-3 max-w-[22rem] text-center text-sm text-mute">{label}</p> : null}
    </div>
  )
}
