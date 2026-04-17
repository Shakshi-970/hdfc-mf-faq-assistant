'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { Message, HealthStatus } from '@/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

function generateId(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

export function useChat() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const sessionInitialized = useRef(false)

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(5000) })
      if (res.ok) {
        const data = await res.json()
        setHealth(data)
      } else {
        setHealth(null)
      }
    } catch {
      setHealth(null)
    }
  }, [])

  const createSession = useCallback(async (): Promise<string | null> => {
    try {
      const res = await fetch(`${API_URL}/sessions/new`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      if (res.ok) {
        const data = await res.json()
        return data.session_id as string
      }
      return null
    } catch {
      return null
    }
  }, [])

  // Initialize session and health polling on mount
  useEffect(() => {
    if (sessionInitialized.current) return
    sessionInitialized.current = true

    fetchHealth()
    createSession().then((id) => {
      if (id) setSessionId(id)
    })

    const interval = setInterval(fetchHealth, 30000)
    return () => clearInterval(interval)
  }, [fetchHealth, createSession])

  const sendMessage = useCallback(
    async (query: string) => {
      if (!query.trim() || isLoading) return

      const trimmedQuery = query.trim()

      // Append user message
      const userMsg: Message = {
        id: generateId(),
        role: 'user',
        content: trimmedQuery,
        timestamp: new Date(),
      }

      // Append loading assistant message
      const loadingId = generateId()
      const loadingMsg: Message = {
        id: loadingId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isLoading: true,
      }

      setMessages((prev) => [...prev, userMsg, loadingMsg])
      setIsLoading(true)

      // Ensure we have a session
      let activeSessionId = sessionId
      if (!activeSessionId) {
        activeSessionId = await createSession()
        if (activeSessionId) setSessionId(activeSessionId)
      }

      if (!activeSessionId) {
        // Replace loading msg with error
        setMessages((prev) =>
          prev.map((m) =>
            m.id === loadingId
              ? {
                  ...m,
                  content: 'Unable to connect to the backend. Please ensure the server is running at ' + API_URL,
                  isLoading: false,
                  timestamp: new Date(),
                }
              : m
          )
        )
        setIsLoading(false)
        return
      }

      try {
        const res = await fetch(`${API_URL}/chat/${activeSessionId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: trimmedQuery }),
          signal: AbortSignal.timeout(60000),
        })

        if (!res.ok) {
          const errText = await res.text().catch(() => 'Unknown error')
          throw new Error(`Server responded with ${res.status}: ${errText}`)
        }

        const data = await res.json()

        const assistantMsg: Message = {
          id: loadingId,
          role: 'assistant',
          content: data.answer || 'No answer returned.',
          source_url: data.source_url ?? null,
          last_updated: data.last_updated ?? null,
          query_class: data.query_class,
          llm_provider: data.llm_provider,
          timestamp: new Date(),
          isLoading: false,
        }

        setMessages((prev) => prev.map((m) => (m.id === loadingId ? assistantMsg : m)))
      } catch (err: unknown) {
        const errorMessage =
          err instanceof Error
            ? err.message.includes('timeout')
              ? 'Request timed out. The backend may be processing a large query — please try again.'
              : `Error: ${err.message}`
            : 'An unexpected error occurred. Please try again.'

        setMessages((prev) =>
          prev.map((m) =>
            m.id === loadingId
              ? { ...m, content: errorMessage, isLoading: false, timestamp: new Date() }
              : m
          )
        )
      } finally {
        setIsLoading(false)
      }
    },
    [sessionId, isLoading, createSession]
  )

  const clearChat = useCallback(async () => {
    // Delete current session
    if (sessionId) {
      try {
        await fetch(`${API_URL}/sessions/${sessionId}`, { method: 'DELETE' })
      } catch {
        // Ignore deletion errors
      }
    }

    // Create a new session
    const newId = await createSession()
    setSessionId(newId)
    setMessages([])
  }, [sessionId, createSession])

  return {
    sessionId,
    messages,
    isLoading,
    health,
    sendMessage,
    clearChat,
  }
}
