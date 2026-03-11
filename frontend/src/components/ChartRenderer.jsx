import React from 'react'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const PALETTE = {
  blue:   ['#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe', '#dbeafe'],
  green:  ['#22c55e', '#4ade80', '#86efac', '#bbf7d0', '#dcfce7'],
  red:    ['#ef4444', '#f87171', '#fca5a5', '#fecaca', '#fee2e2'],
  purple: ['#a855f7', '#c084fc', '#d8b4fe', '#e9d5ff', '#f3e8ff'],
  orange: ['#f97316', '#fb923c', '#fdba74', '#fed7aa', '#ffedd5'],
}

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload?.length) {
    return (
      <div className="glass-card px-3 py-2 text-xs shadow-xl">
        <p className="text-slate-300 font-medium mb-1">{label}</p>
        {payload.map((p, i) => (
          <p key={i} style={{ color: p.color }}>
            {p.name || 'Value'}:{' '}
            <span className="font-semibold">
              {typeof p.value === 'number' ? p.value.toLocaleString() : p.value}
            </span>
          </p>
        ))}
      </div>
    )
  }
  return null
}

const CustomPieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
  if (percent < 0.05) return null
  const RADIAN = Math.PI / 180
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5
  const x = cx + radius * Math.cos(-midAngle * RADIAN)
  const y = cy + radius * Math.sin(-midAngle * RADIAN)
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={500}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  )
}

/**
 * @param {object} chartData  — { chart_type, chart_title, chart_labels, chart_values, chart_color }
 * @param {boolean} compact   — smaller height for dashboard panels
 */
export default function ChartRenderer({ chartData, compact = false }) {
  if (!chartData || chartData.chart_type === 'none' || !chartData.chart_labels?.length) {
    return null
  }

  const { chart_type, chart_title, chart_labels, chart_values, chart_color = 'blue' } = chartData
  const colors = PALETTE[chart_color] || PALETTE.blue
  const height = compact ? 180 : 220

  const data = chart_labels.map((label, i) => ({
    name: String(label).length > 12 ? String(label).slice(0, 11) + '…' : label,
    fullName: label,
    value: Number(chart_values[i]) || 0,
  }))

  const axisStyle = { fill: '#64748b', fontSize: 10, fontFamily: 'Inter' }
  const gridStyle = { stroke: 'rgba(59,130,246,0.07)' }

  const wrapper = (children) => (
    <div className={compact ? 'mt-2' : 'mt-4 animate-slide-up'}>
      {!compact && (
        <div className="glass-card p-4">
          {chart_title && (
            <h4 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-electric-500 inline-block" />
              {chart_title}
            </h4>
          )}
          {children}
        </div>
      )}
      {compact && children}
    </div>
  )

  return wrapper(
    <>
      {chart_type === 'bar' && (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} margin={{ top: 4, right: 8, left: -10, bottom: compact ? 30 : 40 }}>
            <CartesianGrid strokeDasharray="3 3" {...gridStyle} />
            <XAxis dataKey="name" tick={axisStyle} angle={-28} textAnchor="end" interval={0} />
            <YAxis tick={axisStyle} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="value" radius={[3, 3, 0, 0]}>
              {data.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}

      {chart_type === 'line' && (
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={data} margin={{ top: 4, right: 8, left: -10, bottom: compact ? 30 : 40 }}>
            <CartesianGrid strokeDasharray="3 3" {...gridStyle} />
            <XAxis dataKey="name" tick={axisStyle} angle={-28} textAnchor="end" interval={0} />
            <YAxis tick={axisStyle} />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="value"
              stroke={colors[0]}
              strokeWidth={2}
              dot={{ fill: colors[0], r: 3 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      {chart_type === 'pie' && (
        <ResponsiveContainer width="100%" height={height}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              outerRadius={compact ? 70 : 90}
              dataKey="value"
              labelLine={false}
              label={<CustomPieLabel />}
            >
              {data.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend
              formatter={(val) => <span style={{ color: '#94a3b8', fontSize: 10 }}>{val}</span>}
              iconSize={7}
            />
          </PieChart>
        </ResponsiveContainer>
      )}
    </>
  )
}
