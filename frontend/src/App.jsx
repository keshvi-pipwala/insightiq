import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Paperclip, X, AlertCircle, CheckCircle, LayoutDashboard, MessageSquare } from 'lucide-react'
import Sidebar from './components/Sidebar'
import Message from './components/Message'
import SuggestedQuestions from './components/SuggestedQuestions'
import Dashboard from './components/Dashboard'
import { uploadCSV, queryStream, getSchema, getHistory, listDatasets } from './api'

export default function App() {
  const [tab, setTab] = useState('chat')           // 'chat' | 'dashboard'
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [dataset, setDataset] = useState(null)
  const [schema, setSchema] = useState(null)
  const [history, setHistory] = useState([])
  const [toast, setToast] = useState(null)

  const fileInputRef = useRef(null)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    listDatasets()
      .then(datasets => {
        if (datasets.length > 0) {
          const latest = datasets[0]
          setDataset(latest)
          return Promise.all([getSchema(latest.id), getHistory(latest.id)])
        }
      })
      .then(results => {
        if (results) {
          setSchema(results[0])
          setHistory(results[1])
        }
      })
      .catch(() => {})
  }, [])

  const showToast = useCallback((msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }, [])

  const handleUpload = async (file) => {
    if (!file) return
    setUploading(true)
    try {
      const result = await uploadCSV(file)
      const newDataset = { id: result.dataset_id, filename: result.filename, row_count: result.row_count }
      setDataset(newDataset)
      const [schemaData, historyData] = await Promise.all([
        getSchema(result.dataset_id),
        getHistory(result.dataset_id)
      ])
      setSchema(schemaData)
      setHistory(historyData)
      showToast(`"${result.filename}" uploaded — ${result.row_count} rows, ${result.chunks_created} chunks indexed`)
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Upload failed.', 'error')
    } finally {
      setUploading(false)
    }
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
    e.target.value = ''
  }

  const sendMessage = async (questionOverride) => {
    const question = (questionOverride || input).trim()
    if (!question || loading) return
    if (!dataset) {
      showToast('Upload a CSV dataset first.', 'error')
      return
    }

    setInput('')
    setLoading(true)

    // Add user message + empty streaming AI message
    const userId = Date.now()
    const aiId = Date.now() + 1
    setMessages(prev => [
      ...prev,
      { id: userId, role: 'user', content: question },
      { id: aiId, role: 'ai', content: '', streaming: true, chart_data: null, context_used: null },
    ])

    try {
      await queryStream(question, dataset.id, {
        onToken: (text) => {
          setMessages(prev => prev.map(m =>
            m.id === aiId ? { ...m, content: m.content + text } : m
          ))
        },
        onChart: (chartData) => {
          setMessages(prev => prev.map(m =>
            m.id === aiId ? { ...m, chart_data: chartData } : m
          ))
        },
        onDone: (contextUsed) => {
          setMessages(prev => prev.map(m =>
            m.id === aiId ? { ...m, streaming: false, context_used: contextUsed } : m
          ))
          getHistory(dataset.id).then(setHistory).catch(() => {})
        },
        onError: (message) => {
          setMessages(prev => prev
            .filter(m => m.id !== aiId)
            .concat({ id: aiId, role: 'error', content: message })
          )
        },
      })
    } catch (err) {
      setMessages(prev => prev
        .filter(m => m.id !== aiId)
        .concat({ id: aiId, role: 'error', content: err.message || 'Stream failed.' })
      )
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const handleHistoryClick = (item) => {
    setTab('chat')
    setMessages(prev => [
      ...prev,
      { id: Date.now(), role: 'user', content: item.question },
      { id: Date.now() + 1, role: 'ai', content: item.answer, chart_data: item.chart_data, streaming: false },
    ])
  }

  return (
    <div className="flex h-screen bg-navy-950 grid-bg overflow-hidden">
      <Sidebar
        dataset={dataset}
        schema={schema}
        history={history}
        onHistoryClick={handleHistoryClick}
        onUploadClick={() => fileInputRef.current?.click()}
        uploading={uploading}
        activeTab={tab}
        onTabChange={setTab}
      />

      {/* Main content */}
      <div className="flex flex-col flex-1 min-w-0 h-full">
        {/* Tab bar */}
        <header className="flex items-center justify-between px-6 py-0 border-b border-slate-800/60 flex-shrink-0">
          <div className="flex items-center">
            <TabButton
              active={tab === 'chat'}
              onClick={() => setTab('chat')}
              icon={<MessageSquare size={13} />}
              label="Chat"
            />
            <TabButton
              active={tab === 'dashboard'}
              onClick={() => setTab('dashboard')}
              icon={<LayoutDashboard size={13} />}
              label="Dashboard"
              disabled={!dataset}
            />
          </div>
          <div className="flex items-center gap-2 py-3">
            {tab === 'chat' && messages.length > 0 && (
              <button
                onClick={() => setMessages([])}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-all"
              >
                <X size={12} />
                Clear
              </button>
            )}
            <div className={`w-2 h-2 rounded-full ${dataset ? 'bg-green-400' : 'bg-slate-600'}`} />
            <span className="text-xs text-slate-500">{dataset ? dataset.filename : 'No dataset'}</span>
          </div>
        </header>

        {/* Dashboard tab */}
        {tab === 'dashboard' && dataset && (
          <Dashboard datasetId={dataset.id} />
        )}

        {/* Chat tab */}
        {tab === 'chat' && (
          <>
            <div className="flex-1 overflow-y-auto px-6 py-6">
              {messages.length === 0 ? (
                <SuggestedQuestions onSelect={sendMessage} />
              ) : (
                <>
                  {messages.map(msg => <Message key={msg.id} msg={msg} />)}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            <div className="px-6 pb-5 pt-3 flex-shrink-0 border-t border-slate-800/40">
              <div className="flex items-end gap-2 glass-card px-3 py-2.5 glow-border">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="text-slate-500 hover:text-electric-400 transition-colors p-1 flex-shrink-0 mb-0.5"
                  title="Upload CSV"
                >
                  <Paperclip size={16} />
                </button>
                <textarea
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={dataset ? 'Ask a question about your data…' : 'Upload a CSV first, then ask questions…'}
                  disabled={loading || !dataset}
                  rows={1}
                  style={{ resize: 'none', minHeight: 36, maxHeight: 120 }}
                  className="flex-1 bg-transparent text-sm text-slate-200 placeholder:text-slate-600 outline-none disabled:opacity-40 py-1"
                  onInput={e => {
                    e.target.style.height = 'auto'
                    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
                  }}
                />
                <button
                  onClick={() => sendMessage()}
                  disabled={!input.trim() || loading || !dataset}
                  className="btn-primary w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 disabled:opacity-30 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-none mb-0.5"
                >
                  <Send size={14} className="text-white" />
                </button>
              </div>
              <p className="text-xs text-slate-600 mt-2 text-center">
                Answers stream in real-time · Grounded via RAG · Press Enter to send
              </p>
            </div>
          </>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={handleFileChange}
      />

      {toast && (
        <div className={`fixed bottom-6 right-6 flex items-start gap-3 px-4 py-3 rounded-xl shadow-2xl animate-slide-up max-w-sm z-50 ${
          toast.type === 'error'
            ? 'bg-red-900/90 border border-red-500/30 text-red-200'
            : 'bg-navy-800/95 border border-electric-500/25 text-slate-200'
        }`}>
          {toast.type === 'error'
            ? <AlertCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
            : <CheckCircle size={16} className="text-green-400 flex-shrink-0 mt-0.5" />
          }
          <p className="text-sm leading-snug">{toast.msg}</p>
        </div>
      )}
    </div>
  )
}

function TabButton({ active, onClick, icon, label, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        flex items-center gap-2 px-4 py-3.5 text-xs font-medium border-b-2 transition-all
        ${active
          ? 'border-electric-500 text-white'
          : 'border-transparent text-slate-500 hover:text-slate-300 hover:border-slate-600'}
        ${disabled ? 'opacity-30 cursor-not-allowed' : ''}
      `}
    >
      {icon}
      {label}
    </button>
  )
}
