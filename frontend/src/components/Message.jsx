import React from 'react'
import { User, Sparkles, AlertCircle } from 'lucide-react'
import ChartRenderer from './ChartRenderer'

// Blinking cursor shown at end of streaming text
function StreamingCursor() {
  return (
    <span
      className="inline-block w-0.5 h-3.5 bg-electric-400 ml-0.5 align-middle"
      style={{ animation: 'cursorBlink 0.8s step-end infinite' }}
    />
  )
}

export default function Message({ msg }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end mb-4 animate-slide-up">
        <div className="flex items-start gap-2.5 max-w-[75%]">
          <div className="message-user rounded-2xl rounded-tr-sm px-4 py-3 text-sm text-slate-100 leading-relaxed">
            {msg.content}
          </div>
          <div className="w-7 h-7 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center flex-shrink-0 mt-0.5">
            <User size={13} className="text-slate-300" />
          </div>
        </div>
      </div>
    )
  }

  if (msg.role === 'error') {
    return (
      <div className="flex items-start gap-2.5 mb-4 animate-slide-up">
        <div className="w-7 h-7 rounded-full bg-red-500/20 border border-red-500/30 flex items-center justify-center flex-shrink-0 mt-0.5">
          <AlertCircle size={13} className="text-red-400" />
        </div>
        <div className="rounded-2xl rounded-tl-sm px-4 py-3 bg-red-500/10 border border-red-500/20 text-sm text-red-300 max-w-[85%]">
          {msg.content}
        </div>
      </div>
    )
  }

  // AI message (streaming or complete)
  const isStreaming = msg.streaming && msg.content !== undefined
  const isEmpty = !msg.content

  return (
    <div className="flex items-start gap-2.5 mb-6 animate-slide-up">
      {/* Avatar — pulses while streaming */}
      <div className={`w-7 h-7 rounded-full bg-electric-500/20 border border-electric-500/30 flex items-center justify-center flex-shrink-0 mt-0.5 ${isStreaming ? 'animate-pulse-slow' : ''}`}>
        <Sparkles size={13} className="text-electric-400" />
      </div>

      <div className="max-w-[85%] flex-1">
        <div className="message-ai rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-slate-200 leading-relaxed">
          {isEmpty && isStreaming ? (
            // Haven't received any tokens yet — show dots
            <div className="flex gap-1 items-center px-1 py-1">
              {[0, 1, 2].map(i => (
                <div
                  key={i}
                  className="typing-dot w-2 h-2 rounded-full bg-electric-500"
                  style={{ animationDelay: `${i * 0.2}s` }}
                />
              ))}
            </div>
          ) : (
            <div className="whitespace-pre-wrap">
              {msg.content}
              {isStreaming && <StreamingCursor />}
            </div>
          )}

          {/* Footer — only shown when done */}
          {!isStreaming && msg.context_used != null && (
            <div className="mt-2 pt-2 border-t border-slate-700/50">
              <span className="text-xs text-slate-500">
                Grounded on {msg.context_used} data context{msg.context_used !== 1 ? 's' : ''}
              </span>
            </div>
          )}
        </div>

        {/* Chart renders once chart_data arrives (during or after stream) */}
        {msg.chart_data && <ChartRenderer chartData={msg.chart_data} />}
      </div>

      <style>{`
        @keyframes cursorBlink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  )
}
