import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { AdminView } from '@/components/admin-view'
import { UserView } from '@/components/user-view'
import { api, ApiError } from '@/api'

type Session = { key: string; view: 'admin' | 'user' }

// One page; the pasted API key decides the view (DESIGN.md 3.8):
// admin key → fleet view, user key → self view. Key lives in React state only.
export default function App() {
  const [keyInput, setKeyInput] = useState('')
  const [session, setSession] = useState<Session | null>(null)
  const [error, setError] = useState<string | null>(null)

  const signIn = async () => {
    const key = keyInput.trim()
    setError(null)
    try {
      await api(key, '/admin/users')
      setSession({ key, view: 'admin' })
    } catch (probeError) {
      if (probeError instanceof ApiError && probeError.status === 403) {
        try {
          await api(key, '/usage')
          setSession({ key, view: 'user' })
          return
        } catch {
          /* fall through to the error message */
        }
      }
      setError('Invalid API key')
    }
  }

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-8">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">llm-proxy dashboard</h1>
        {session && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setSession(null)
              setKeyInput('')
            }}
          >
            Sign out
          </Button>
        )}
      </header>

      {!session ? (
        <div className="space-y-2">
          <div className="flex max-w-md gap-2">
            <Input
              type="password"
              placeholder="sk-proxy-…"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && signIn()}
            />
            <Button onClick={signIn}>View usage</Button>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <p className="text-sm text-muted-foreground">
            Paste an API key — an admin key opens the fleet view, a user key
            shows your own usage.
          </p>
        </div>
      ) : session.view === 'admin' ? (
        <AdminView apiKey={session.key} />
      ) : (
        <UserView apiKey={session.key} />
      )}
    </main>
  )
}
