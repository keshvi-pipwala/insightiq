import React, { useState } from 'react'
import {
  Database, Upload, Clock, ChevronDown, ChevronRight,
  Table, Sparkles, ExternalLink
} from 'lucide-react'

export default function Sidebar({
  dataset, schema, history, onHistoryClick, onUploadClick, uploading
}) {
  const [schemaOpen, setSchemaOpen] = useState(true)
  const [historyOpen, setHistoryOpen] = useState(true)

  return (
    <aside className="w-64 flex flex-col h-full border-r border-slate-800/60 bg-navy-900/80 backdrop-blur-sm overflow-hidden flex-shrink-0">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-slate-800/60">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-electric-500/20 border border-electric-500/30 flex items-center justify-center">
            <Sparkles size={16} className="text-electric-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">InsightIQ</h1>
            <p className="text-xs text-slate-500">AI Analytics Assistant</p>
          </div>
        </div>
      </div>

      {/* Upload button */}
      <div className="px-3 pt-4 pb-2">
        <button
          onClick={onUploadClick}
          disabled={uploading}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg btn-primary text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {uploading ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Processing…
            </>
          ) : (
            <>
              <Upload size={14} />
              Upload CSV Dataset
            </>
          )}
        </button>
      </div>

      {/* Dataset info */}
      {dataset && (
        <div className="mx-3 mt-2 px-3 py-2.5 rounded-lg bg-electric-500/5 border border-electric-500/15">
          <div className="flex items-center gap-2 mb-1">
            <Database size={12} className="text-electric-400" />
            <span className="text-xs font-medium text-electric-400">Active Dataset</span>
          </div>
          <p className="text-xs text-white font-medium truncate">{dataset.filename}</p>
          <p className="text-xs text-slate-400 mt-0.5">{dataset.row_count?.toLocaleString()} rows</p>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
        {/* Schema */}
        {schema?.columns?.length > 0 && (
          <div>
            <button
              onClick={() => setSchemaOpen(o => !o)}
              className="sidebar-item w-full flex items-center justify-between"
            >
              <span className="flex items-center gap-2">
                <Table size={13} />
                Schema
              </span>
              {schemaOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            </button>
            {schemaOpen && (
              <div className="ml-2 mt-1 space-y-0.5 animate-fade-in">
                {schema.columns.map((col) => (
                  <div key={col} className="flex items-center gap-2 px-2 py-1 rounded text-xs text-slate-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-electric-500/40 flex-shrink-0" />
                    <span className="font-mono truncate">{col}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* History */}
        {history?.length > 0 && (
          <div className="mt-2">
            <button
              onClick={() => setHistoryOpen(o => !o)}
              className="sidebar-item w-full flex items-center justify-between"
            >
              <span className="flex items-center gap-2">
                <Clock size={13} />
                History
                <span className="ml-1 text-xs bg-slate-700 rounded-full px-1.5 py-0.5">{history.length}</span>
              </span>
              {historyOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            </button>
            {historyOpen && (
              <div className="ml-2 mt-1 space-y-0.5 animate-fade-in">
                {history.slice(0, 15).map((item) => (
                  <button
                    key={item.id}
                    onClick={() => onHistoryClick(item)}
                    className="sidebar-item w-full text-left px-2 py-1.5 text-xs leading-snug"
                  >
                    <span className="line-clamp-2">{item.question}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-slate-800/60 space-y-2">
        <a
          href="https://github.com"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          <ExternalLink size={11} />
          View on GitHub
        </a>
        <p className="text-xs text-slate-600">Powered by Claude + RAG</p>
      </div>
    </aside>
  )
}
