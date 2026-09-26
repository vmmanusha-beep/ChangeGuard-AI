// Typed API client — all calls go through Vite's proxy to localhost:8000

export interface Finding {
  file: string
  line_hint: string
  category: string
  description: string
  suggestion: string
  severity: 'high' | 'medium' | 'low'
}

export interface AnalyzeResponse {
  id: number
  title: string
  risk_level: 'high' | 'medium' | 'low'
  risk_score: number
  summary: string
  affected_files: string[]
  findings: Finding[]
  safer_alternatives: string[]
  recommended_tests: string[]
  engine: string
  created_at: string
}

export interface ReportListItem {
  id: number
  title: string
  risk_level: 'high' | 'medium' | 'low'
  risk_score: number
  summary: string
  affected_files: string[]
  findings_count: number
  engine: string
  created_at: string
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  analyze(diff: string, title: string): Promise<AnalyzeResponse> {
    return request<AnalyzeResponse>('https://changeguard-ai-backend-jcxk.onrender.com/api/analyze', {
      method: 'POST',
      body: JSON.stringify({ diff, title }),
    })
  },

  listReports(): Promise<ReportListItem[]> {
    return request<ReportListItem[]>('https://changeguard-ai-backend-jcxk.onrender.com/api/reports')
  },

  getReport(id: number): Promise<AnalyzeResponse> {
    return request<AnalyzeResponse>(`https://changeguard-ai-backend-jcxk.onrender.com/api/reports/${id}`)
  },
}
