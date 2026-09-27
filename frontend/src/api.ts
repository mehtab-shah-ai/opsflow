export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
export const base = API_BASE
export const apiUrl = (path: string) => API_BASE + path

export function getActiveToken(): string {
  let token = localStorage.getItem('opsflow.auth_token') || localStorage.getItem('opsflow.workspace')
  if (!token) {
    token = crypto.randomUUID().replaceAll('-', '') + crypto.randomUUID().replaceAll('-', '')
    localStorage.setItem('opsflow.workspace', token)
  }
  return token
}

export function setAuthToken(token: string | null) {
  if (token) {
    localStorage.setItem('opsflow.auth_token', token)
  } else {
    localStorage.removeItem('opsflow.auth_token')
  }
}

export function isUserAuthenticated(): boolean {
  return !!localStorage.getItem('opsflow.auth_token')
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getActiveToken()
  const headers: Record<string, string> = {
    'X-Workspace-Token': token,
    'Authorization': `Bearer ${token}`
  }
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 65000)
  try {
    const response = await fetch(base + path, {
      ...options,
      headers: {
        ...headers,
        ...(options.body && !(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers
      },
      signal: controller.signal
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(typeof err.detail === 'string' ? err.detail : `The request could not finish (${response.status}). Review your input and retry.`)
    }
    return await response.json() as T
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('The backend is taking longer than expected. Your workspace is still available; retry shortly.')
    }
    throw error
  } finally {
    clearTimeout(timer)
  }
}

export async function download(path: string, filename: string) {
  const token = getActiveToken()
  const response = await fetch(base + path, {
    headers: {
      'X-Workspace-Token': token,
      'Authorization': `Bearer ${token}`
    }
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.detail || 'Download failed. Please retry.')
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) })

