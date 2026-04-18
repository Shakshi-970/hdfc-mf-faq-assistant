'use client'

import { useState, useRef, useCallback, KeyboardEvent, ChangeEvent } from 'react'

const SCHEME_NAMES = [
  'HDFC Large Cap Fund Direct Growth',
  'HDFC Equity Fund Direct Growth',
  'HDFC ELSS Tax Saver Fund Direct Plan Growth',
  'HDFC Mid-Cap Fund Direct Growth',
  'HDFC Focused Fund Direct Growth',
]

interface Suggestion {
  completedValue: string
  append: string
}

function getSuggestion(input: string): Suggestion | null {
  if (!input.trim()) return null
  // Try each suffix of the input (longest first) to find a scheme name prefix match
  for (let i = 0; i < input.length; i++) {
    const suffix = input.slice(i)
    if (suffix.length < 3) break
    const lower = suffix.toLowerCase()
    const match = SCHEME_NAMES.find(
      s => s.toLowerCase().startsWith(lower) && s.toLowerCase() !== lower
    )
    if (match) {
      return {
        completedValue: input.slice(0, i) + match,
        append: match.slice(suffix.length),
      }
    }
  }
  return null
}

interface ChatInputProps {
  onSend: (query: string) => void
  disabled: boolean
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const autoResize = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const lineHeight = 24
    const maxHeight = lineHeight * 5 + 16
    el.style.height = Math.min(el.scrollHeight, maxHeight) + 'px'
  }, [])

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value)
    autoResize()
  }

  const handleSubmit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const suggestion = getSuggestion(value)

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab' && suggestion) {
      e.preventDefault()
      setValue(suggestion.completedValue)
      autoResize()
      return
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const canSend = value.trim().length > 0 && !disabled

  return (
    <div className="bg-white border-t border-border px-4 py-3 shadow-sm">
      <div className="max-w-4xl mx-auto">
        <div className="relative flex items-end gap-2 bg-white rounded-2xl px-4 py-3 border border-border focus-within:border-hdfc-blue/50 focus-within:shadow-sm transition-all duration-150">
          <div className="flex-1 relative">
            {suggestion && (
              <div className="absolute inset-0 flex items-start pointer-events-none pt-0">
                <span className="text-sm leading-6 whitespace-pre-wrap break-words w-full">
                  <span className="text-transparent">{value}</span>
                  <span className="text-gray-300">{suggestion.append}</span>
                </span>
              </div>
            )}
            <textarea
              ref={textareaRef}
              value={value}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              placeholder="Ask about expense ratio, NAV, SIP, exit load…"
              rows={1}
              className="relative w-full bg-transparent text-sm text-gray-800 placeholder-gray-400 outline-none resize-none leading-6 min-h-[24px] max-h-[120px] overflow-y-auto disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Chat input"
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={!canSend}
            className={`flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-150 ${
              canSend
                ? 'bg-hdfc-red hover:bg-hdfc-redDark text-white cursor-pointer shadow-sm'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed'
            }`}
            aria-label="Send message"
          >
            {disabled ? (
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
