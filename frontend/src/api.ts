// Typed mirrors of the proxy's JSON payloads (app/views/usage.py, app/views/admin.py).

export interface Limits {
  requests_per_minute: number | null
  tokens_per_day: number | null
  lifetime_spend_dollars: number | null
}

export interface ModelUsage {
  requests: number
  prompt_tokens: number
  completion_tokens: number
  cost_dollars: number
}

export interface UsageSummary {
  requests_last_minute: number
  tokens_last_day: number
  total_requests: number
  lifetime_tokens: number
  lifetime_spend_dollars: number
  by_model: Record<string, ModelUsage>
}

// GET /admin/users item; also the POST /admin/users and PUT .../limits response.
export interface AdminUser {
  id: number
  name: string
  is_admin: boolean
  api_key: string
  limits: Limits
  usage: UsageSummary
}

// GET /usage
export interface OwnUsage {
  user: { id: number; name: string }
  limits: Limits
  usage: UsageSummary
}

export class ApiError extends Error {
  constructor(public status: number) {
    super(`HTTP ${status}`)
  }
}

export async function api<T>(
  key: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
    },
  })
  if (!response.ok) throw new ApiError(response.status)
  return response.json()
}

export const formatTokens = (n: number) =>
  Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(n)

export const formatDollars = (n: number) =>
  `$${n.toFixed(n < 0.1 && n > 0 ? 4 : 2)}`
