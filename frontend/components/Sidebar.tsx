'use client'

import Image from 'next/image'
import { HealthStatus } from '@/types'

interface SidebarProps {
  health: HealthStatus | null
  onExampleClick: (query: string) => void
  onClearChat: () => void
}

const FUNDS = [
  { label: 'HDFC Large Cap Fund (Direct Growth)',            query: 'Tell me about HDFC Large Cap Fund Direct Growth' },
  { label: 'HDFC Equity Fund (Direct Growth)',               query: 'Tell me about HDFC Equity Fund Direct Growth' },
  { label: 'HDFC ELSS Tax Saver Fund (Direct Plan Growth)',  query: 'Tell me about HDFC ELSS Tax Saver Fund Direct Plan Growth' },
  { label: 'HDFC Mid-Cap Fund (Direct Growth)',              query: 'Tell me about HDFC Mid-Cap Fund Direct Growth' },
  { label: 'HDFC Focused Fund (Direct Growth)',              query: 'Tell me about HDFC Focused Fund Direct Growth' },
]

const QUICK_QUESTIONS = [
  'What is the expense ratio of HDFC ELSS Tax Saver Fund?',
  'What is the minimum SIP amount for HDFC Large Cap Fund?',
  'Who is the fund manager of HDFC Mid-Cap Fund?',
  'What is the exit load for HDFC Equity Fund?',
]

export default function Sidebar({ health, onExampleClick, onClearChat }: SidebarProps) {
  const isConnected = health !== null && health.status === 'ok'

  return (
    <aside className="w-[280px] flex-shrink-0 h-screen flex flex-col bg-surface border-r border-border overflow-y-auto">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-border bg-white">
        <Image
          src="/HDFC-Bank-logo.jpg"
          alt="HDFC Bank"
          width={160}
          height={52}
          priority
          className="object-contain"
        />
      </div>


      {/* In-scope schemes */}
      <div className="px-5 py-4 border-b border-border">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          In-scope schemes
        </p>
        <div className="flex flex-col gap-1.5">
          {FUNDS.map((fund) => (
            <button
              key={fund.label}
              onClick={() => onExampleClick(fund.query)}
              className="text-left text-xs text-gray-600 hover:text-hdfc-blue px-2.5 py-1.5 rounded-lg hover:bg-hdfc-blue/8 transition-colors duration-150 leading-relaxed"
              title={fund.label}
            >
              {fund.label}
            </button>
          ))}
        </div>
      </div>

      {/* Quick questions */}
      <div className="px-5 py-4 flex-1 border-b border-border">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Quick questions
        </p>
        <div className="flex flex-col gap-1.5">
          {QUICK_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => onExampleClick(q)}
              className="text-left text-xs text-gray-500 hover:text-hdfc-blue px-2.5 py-2 rounded-lg hover:bg-hdfc-blue/8 transition-colors duration-150 leading-relaxed"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Bottom: disclaimer + clear button */}
      <div className="px-5 py-4 flex flex-col gap-3">
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5">
          <div className="flex items-start gap-2">
            <svg
              className="w-3.5 h-3.5 text-amber-500 flex-shrink-0 mt-0.5"
              fill="currentColor"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
            <p className="text-xs text-amber-700 leading-relaxed">
              Facts only · No investment advice
            </p>
          </div>
        </div>

        <button
          onClick={onClearChat}
          className="w-full text-xs text-gray-500 hover:text-hdfc-red bg-white hover:bg-red-50 px-3 py-2 rounded-lg border border-border hover:border-hdfc-red/30 transition-colors duration-150 flex items-center justify-center gap-2"
        >
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
          Clear conversation
        </button>
      </div>
    </aside>
  )
}
