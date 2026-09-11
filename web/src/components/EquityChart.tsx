import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { EquityPoint } from '../data/demo'

export function EquityChart({ data, height = 280 }: { data: EquityPoint[]; height?: number }) {
  return (
    <div className="h-full w-full" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="gGuard" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22C55E" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#22C55E" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#222" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="t"
            tickFormatter={(v) =>
              new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            }
            stroke="#333"
            tick={{ fill: '#A3A3A3', fontSize: 11, fontFamily: 'IBM Plex Mono' }}
            minTickGap={40}
          />
          <YAxis
            domain={['auto', 'auto']}
            stroke="#333"
            tick={{ fill: '#A3A3A3', fontSize: 11, fontFamily: 'IBM Plex Mono' }}
            width={56}
          />
          <Tooltip
            contentStyle={{
              background: '#111',
              border: '1px solid #333',
              borderRadius: 4,
              fontFamily: 'IBM Plex Mono',
              fontSize: 12,
            }}
            labelFormatter={(v) => new Date(String(v)).toUTCString()}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: '#A3A3A3' }} />
          <Area
            type="monotone"
            dataKey="guarded"
            name="Guarded"
            stroke="#22C55E"
            fill="url(#gGuard)"
            strokeWidth={2}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="shadow"
            name="Shadow (unguarded)"
            stroke="#EF4444"
            strokeWidth={2}
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
