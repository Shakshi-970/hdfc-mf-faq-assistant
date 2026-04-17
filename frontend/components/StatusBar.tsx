'use client'

import { HealthStatus } from '@/types'

interface StatusBarProps {
  health: HealthStatus | null
}

export default function StatusBar({ health }: StatusBarProps) {
  return (
    <div className="h-10 flex items-center justify-between px-4 bg-hdfc-blueDeep border-b border-hdfc-blue/30 flex-shrink-0">
      <span className="text-xs font-semibold text-white tracking-wide">
        HDFC Mutual Fund FAQ Assistant
      </span>

      {health !== null && (
        <div className="flex items-center gap-1.5">
          <svg
            className="w-3.5 h-3.5 text-zinc-300"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
          <span className="text-xs text-zinc-300">
            {health.active_sessions}{' '}
            {health.active_sessions === 1 ? 'active session' : 'active sessions'}
          </span>
        </div>
      )}
    </div>
  )
}
