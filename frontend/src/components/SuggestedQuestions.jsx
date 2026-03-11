import React from 'react'
import { TrendingDown, Users, DollarSign, BarChart2, Star, Globe } from 'lucide-react'

const SUGGESTIONS = [
  { icon: TrendingDown, text: "What is driving churn this quarter?", color: "text-red-400" },
  { icon: Users, text: "Which user segment has the highest lifetime value?", color: "text-blue-400" },
  { icon: DollarSign, text: "Show me average spend by subscription plan", color: "text-green-400" },
  { icon: BarChart2, text: "What's the revenue breakdown by product category?", color: "text-purple-400" },
  { icon: Star, text: "How does NPS score vary across customer segments?", color: "text-yellow-400" },
  { icon: Globe, text: "Which countries have the highest churn rates?", color: "text-orange-400" },
]

export default function SuggestedQuestions({ onSelect }) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-8 py-10 max-w-2xl mx-auto">
      <div className="mb-8 text-center">
        <div className="w-14 h-14 rounded-2xl bg-electric-500/15 border border-electric-500/25 flex items-center justify-center mx-auto mb-4">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-electric-400">
            <path d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-white mb-2">Ask anything about your data</h2>
        <p className="text-sm text-slate-500 leading-relaxed">
          Upload a CSV dataset and start asking natural language questions. InsightIQ uses RAG to ground answers in your actual data.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full">
        {SUGGESTIONS.map(({ icon: Icon, text, color }) => (
          <button
            key={text}
            onClick={() => onSelect(text)}
            className="flex items-start gap-3 px-4 py-3 rounded-xl glass-card hover:border-electric-500/25 hover:bg-electric-500/5 transition-all text-left group"
          >
            <Icon size={15} className={`${color} flex-shrink-0 mt-0.5`} />
            <span className="text-sm text-slate-400 group-hover:text-slate-200 transition-colors leading-snug">{text}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
