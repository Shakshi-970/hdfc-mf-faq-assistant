export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  source_url?: string | null
  last_updated?: string | null
  query_class?: string
  llm_provider?: string
  timestamp: Date
  isLoading?: boolean
}

export interface HealthStatus {
  status: string
  version: string
  active_sessions: number
  llm_provider: string
  cache?: unknown
}
