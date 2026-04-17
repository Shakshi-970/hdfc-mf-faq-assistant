'use client'

import { useEffect, useRef } from 'react'
import { Message } from '@/types'
import ChatMessage from './ChatMessage'

interface ChatWindowProps {
  messages: Message[]
  onExampleClick: (query: string) => void
}

const EXAMPLE_QUESTIONS = [
  'What is the expense ratio of HDFC Large Cap Fund?',
  'Minimum SIP amount for HDFC Mid-Cap Fund?',
  'What is the exit load for HDFC Equity Fund?',
  'What is the lock-in period for HDFC ELSS Tax Saver Fund?',
  'Who is the fund manager of HDFC Focused Fund?',
  'What is the benchmark for HDFC Large Cap Fund?',
  'What is the NAV of HDFC ELSS Tax Saver Fund?',
  'What are the tax benefits of HDFC ELSS fund?',
]

function EmptyState({ onExampleClick }: { onExampleClick: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6 py-12">
      <div className="w-16 h-16 bg-hdfc-blue/10 rounded-2xl flex items-center justify-center mb-5 border border-hdfc-blue/20">
        <svg
          className="w-8 h-8 text-hdfc-blue"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
          />
        </svg>
      </div>

      <h2 className="text-xl font-semibold text-hdfc-blueDeep mb-2 text-center">
        Ask anything about HDFC Mutual Funds
      </h2>
      <p className="text-sm text-gray-500 mb-8 text-center">
        Facts from Groww.in · Updated daily
      </p>

      <div className="grid grid-cols-2 gap-2 w-full max-w-2xl">
        {EXAMPLE_QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => onExampleClick(q)}
            className="text-left text-xs text-gray-600 hover:text-hdfc-blue bg-white hover:bg-hdfc-blue/5 border border-border hover:border-hdfc-blue/40 px-3.5 py-2.5 rounded-xl transition-all duration-150 leading-relaxed shadow-sm"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function ChatWindow({ messages, onExampleClick }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  if (messages.length === 0) {
    return <EmptyState onExampleClick={onExampleClick} />
  }

  return (
    <div className="flex flex-col gap-3 px-4 py-4">
      {messages.map((message) => (
        <ChatMessage key={message.id} message={message} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
