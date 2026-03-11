import React, { useEffect, useState } from 'react'
import { RefreshCw, LayoutDashboard, Sparkles, AlertCircle } from 'lucide-react'
import ChartRenderer from './ChartRenderer'
import { getDashboard } from '../api'

function SkeletonPanel() {
  return (
    <div className="glass-card p-4 animate-pulse">
      <div className="h-3 w-32 bg-slate-700 rounded mb-3" />
      <div className="h-2 w-full bg-slate-800 rounded mb-1.5" />
      <div className="h-2 w-4/5 bg-slate-800 rounded mb-4" />
      <div className="h-44 bg-slate-800/60 rounded-lg" />
    </div>
  )
}

function DashboardPanel({ panel }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="glass-card p-4 hover:border-electric-500/20 transition-colors animate-slide-up">
      <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-electric-500 flex-shrink-0" />
        {panel.title}
      </h3>

      {/* Insight text — collapsed by default, expandable */}
      <div className={`text-xs text-slate-400 leading-relaxed mb-1 ${expanded ? '' : 'line-clamp-2'}`}>
        {panel.answer}
      </div>
      {panel.answer?.length > 120 && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="text-xs text-electric-400 hover:text-electric-300 mb-2"
        >
          {expanded ? 'Show less' : 'Read more'}
        </button>
      )}

      <ChartRenderer chartData={panel.chart_data} compact />
    </div>
  )
}

export default function Dashboard({ datasetId }) {
  const [panels, setPanels] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [cached, setCached] = useState(false)
  const [generatedAt, setGeneratedAt] = useState(null)

  const load = async (refresh = false) => {
    setLoading(true)
    setError(null)
    try {
      const result = await getDashboard(datasetId, refresh)
      setPanels(result.panels)
      setCached(result.cached)
      setGeneratedAt(new Date())
    } catch (e) {
      setError(e?.response?.data?.detail || 'Failed to load dashboard.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (datasetId) load()
  }, [datasetId])

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-8">
        <AlertCircle size={32} className="text-red-400" />
        <p className="text-sm text-red-300">{error}</p>
        <button onClick={() => load(true)} className="btn-primary px-4 py-2 rounded-lg text-sm text-white">
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/60 flex-shrink-0">
        <div className="flex items-center gap-2">
          <LayoutDashboard size={16} className="text-electric-400" />
          <h2 className="text-sm font-semibold text-white">Auto Insights Dashboard</h2>
          {cached && (
            <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">cached</span>
          )}
        </div>
        <button
          onClick={() => load(true)}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-slate-800/60 transition-all disabled:opacity-40"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          Regenerate
        </button>
      </div>

      {/* Subtitle */}
      <div className="px-6 py-3 border-b border-slate-800/40 flex-shrink-0">
        <p className="text-xs text-slate-500">
          5 key insights auto-generated from your dataset using RAG + Claude.
          {generatedAt && !loading && (
            <span className="ml-1 text-slate-600">
              · Generated {generatedAt.toLocaleTimeString()}
            </span>
          )}
        </p>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {loading ? (
          <div>
            <div className="flex items-center gap-2 mb-5 text-sm text-slate-400">
              <Sparkles size={14} className="text-electric-400 animate-pulse" />
              Generating insights — running 5 RAG queries…
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {Array.from({ length: 5 }).map((_, i) => <SkeletonPanel key={i} />)}
            </div>
          </div>
        ) : panels.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
            <LayoutDashboard size={32} className="text-slate-600" />
            <p className="text-sm text-slate-500">No dashboard panels yet.</p>
            <button onClick={() => load(true)} className="btn-primary px-4 py-2 rounded-lg text-sm text-white">
              Generate Now
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {panels.map(panel => (
              <DashboardPanel key={panel.id} panel={panel} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
