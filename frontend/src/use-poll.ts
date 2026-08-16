import { useEffect, useState } from 'react'
import { api } from '@/api'

// Poll a GET endpoint every 2s so usage visibly ticks during load runs.
// refresh() re-fetches immediately (used after mutations).
export function usePoll<T>(apiKey: string, path: string) {
  const [data, setData] = useState<T | null>(null)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let alive = true
    let seq = 0 // slow responses can arrive out of order; only the latest may write
    const tick = () => {
      const mine = ++seq
      api<T>(apiKey, path)
        .then((result) => alive && mine === seq && setData(result))
        .catch(() => {}) // transient poll failure: keep last data
    }
    tick()
    const id = setInterval(tick, 2000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [apiKey, path, version])

  return { data, refresh: () => setVersion((v) => v + 1) }
}
