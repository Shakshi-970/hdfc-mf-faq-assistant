'use client'

import { Message } from '@/types'

interface ChatMessageProps {
  message: Message
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
}

function QueryClassBadge({ queryClass }: { queryClass: string }) {
  const badgeMap: Record<string, { label: string; className: string }> = {
    advisory: { label: 'Advisory', className: 'bg-amber-100 text-amber-700 border border-amber-300' },
    out_of_scope: { label: 'Out of scope', className: 'bg-gray-100 text-gray-600 border border-gray-300' },
    pii_risk: { label: 'PII risk', className: 'bg-red-100 text-hdfc-red border border-red-200' },
  }

  const badge = badgeMap[queryClass]
  if (!badge) return null

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${badge.className}`}>
      {badge.label}
    </span>
  )
}

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-2 py-1 animate-pulse">
      <div className="h-3 bg-gray-200 rounded-full w-4/5" />
      <div className="h-3 bg-gray-200 rounded-full w-3/5" />
      <div className="h-3 bg-gray-200 rounded-full w-2/3" />
    </div>
  )
}

function LinkedContent({ text }: { text: string }) {
  const urlRegex = /(https?:\/\/[^\s]+)/g
  const parts = text.split(urlRegex)
  return (
    <>
      {parts.map((part, i) =>
        urlRegex.test(part) ? (
          <a
            key={i}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            className="text-hdfc-blue underline underline-offset-2 hover:text-hdfc-blueDark break-all"
          >
            {part}
          </a>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  )
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="flex flex-col items-end gap-1 max-w-[75%]">
          <div className="bg-hdfc-blueDeep text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm leading-relaxed shadow-sm">
            {message.content}
          </div>
          <span className="text-xs text-gray-400 pr-1">
            {formatTime(new Date(message.timestamp))}
          </span>
        </div>
      </div>
    )
  }

  // Assistant message
  return (
    <div className="flex justify-start">
      <div className="flex flex-col items-start gap-1.5 max-w-[80%]">
        <div className="bg-white border border-border text-gray-800 rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed shadow-sm">
          {message.isLoading ? (
            <LoadingSkeleton />
          ) : (
            <p className="whitespace-pre-wrap"><LinkedContent text={message.content} /></p>
          )}
        </div>

        {/* Metadata row */}
        {!message.isLoading && (
          <div className="flex flex-col gap-1.5 pl-1">
            {/* Query class badge */}
            {message.query_class && (
              <QueryClassBadge queryClass={message.query_class} />
            )}

            {/* Source URL pill */}
            {message.source_url && (
              <a
                href={message.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white border border-border text-xs text-gray-500 hover:text-hdfc-blue hover:border-hdfc-blue/40 transition-colors duration-150"
              >
                <svg
                  className="w-3 h-3 flex-shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                  />
                </svg>
                <span>
                  Source
                  {message.last_updated && (
                    <span className="text-gray-400"> · {message.last_updated}</span>
                  )}
                </span>
              </a>
            )}

            <span className="text-xs text-gray-400">
              {formatTime(new Date(message.timestamp))}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
