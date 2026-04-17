'use client'

import { useState, useCallback } from 'react'
import { useChat } from '@/hooks/useChat'
import Sidebar from '@/components/Sidebar'
import StatusBar from '@/components/StatusBar'
import ChatWindow from '@/components/ChatWindow'
import ChatInput from '@/components/ChatInput'

export default function HomePage() {
  const { messages, isLoading, health, sendMessage, clearChat } = useChat()
  const [pendingQuery, setPendingQuery] = useState<string | null>(null)

  const handleExampleClick = useCallback(
    (query: string) => {
      if (isLoading) return
      sendMessage(query)
    },
    [isLoading, sendMessage]
  )

  const handleSend = useCallback(
    (query: string) => {
      sendMessage(query)
      if (pendingQuery !== null) setPendingQuery(null)
    },
    [sendMessage, pendingQuery]
  )

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      {/* Left sidebar */}
      <Sidebar
        health={health}
        onExampleClick={handleExampleClick}
        onClearChat={clearChat}
      />

      {/* Main content area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top status bar */}
        <StatusBar health={health} />

        {/* Scrollable chat messages */}
        <div className="flex-1 overflow-y-auto">
          <ChatWindow messages={messages} onExampleClick={handleExampleClick} />
        </div>

        {/* Fixed input bar */}
        <ChatInput onSend={handleSend} disabled={isLoading} />
      </div>
    </div>
  )
}
