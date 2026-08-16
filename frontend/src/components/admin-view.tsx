import { Fragment, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { LimitMeters } from "@/components/meters"
import { ModelTable } from "@/components/model-table"
import { usePoll } from "@/use-poll"
import { api, formatDollars, type AdminUser } from "@/api"

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <Button variant="ghost" size="xs" onClick={copy}>
      {copied ? "copied" : "copy"}
    </Button>
  )
}

// Inline limit editor: empty field = no limit (∞); PUT sends explicit nulls to clear.
function EditLimits({
  apiKey,
  user,
  onDone,
}: {
  apiKey: string
  user: AdminUser
  onDone: () => void
}) {
  const [rpm, setRpm] = useState(
    user.limits.requests_per_minute?.toString() ?? "",
  )
  const [tpd, setTpd] = useState(user.limits.tokens_per_day?.toString() ?? "")
  const [spend, setSpend] = useState(
    user.limits.lifetime_spend_dollars?.toString() ?? "",
  )

  const save = async () => {
    await api(apiKey, `/admin/users/${user.id}/limits`, {
      method: "PUT",
      body: JSON.stringify({
        requests_per_minute: rpm === "" ? null : Number(rpm),
        tokens_per_day: tpd === "" ? null : Number(tpd),
        lifetime_spend_dollars: spend === "" ? null : Number(spend),
      }),
    })
    onDone()
  }

  const fields: [string, string, (v: string) => void][] = [
    ["requests / minute", rpm, setRpm],
    ["tokens / day", tpd, setTpd],
    ["lifetime spend $", spend, setSpend],
  ]
  return (
    <div className="flex flex-wrap items-end gap-3">
      {fields.map(([label, value, set]) => (
        <label
          key={label}
          className="flex flex-col gap-1.5 text-xs text-muted-foreground"
        >
          {label}
          <Input
            className="w-36"
            type="number"
            min="0"
            placeholder="∞ (no limit)"
            value={value}
            onChange={(e) => set(e.target.value)}
          />
        </label>
      ))}
      <Button onClick={save}>Save</Button>
      <span className="flex h-8 items-center text-xs text-muted-foreground">
        empty field = no limit
      </span>
    </div>
  )
}

function CreateUser({
  apiKey,
  onCreated,
}: {
  apiKey: string
  onCreated: () => void
}) {
  const [name, setName] = useState("")
  const [isAdmin, setIsAdmin] = useState(false)

  const create = async () => {
    if (!name.trim()) return
    await api(apiKey, "/admin/users", {
      method: "POST",
      body: JSON.stringify({ name: name.trim(), is_admin: isAdmin }),
    })
    setName("")
    setIsAdmin(false)
    onCreated()
  }

  return (
    <div className="flex items-center gap-3">
      <Input
        className="w-48"
        placeholder="new user name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && create()}
      />
      <label className="flex items-center gap-1.5 text-sm">
        <Checkbox
          checked={isAdmin}
          onCheckedChange={(c) => setIsAdmin(c === true)}
        />
        admin
      </label>
      <Button size="sm" onClick={create}>
        Create user
      </Button>
      <span className="text-xs text-muted-foreground">
        key appears in the table
      </span>
    </div>
  )
}

export function AdminView({ apiKey }: { apiKey: string }) {
  const { data: users, refresh } = usePoll<AdminUser[]>(apiKey, "/admin/users")
  const [expanded, setExpanded] = useState<number | null>(null)
  const [editing, setEditing] = useState<number | null>(null)

  if (!users) return <p className="text-muted-foreground">Loading…</p>

  const totalRequests = users.reduce((n, u) => n + u.usage.total_requests, 0)
  const totalSpend = users.reduce(
    (n, u) => n + u.usage.lifetime_spend_dollars,
    0,
  )

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {users.length} users · {totalRequests.toLocaleString()} requests ·{" "}
        {formatDollars(totalSpend)} spend · refreshing every 2s
      </p>
      <Card>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>API key</TableHead>
                <TableHead className="w-2xl">Limits</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <Fragment key={user.id}>
                  <TableRow>
                    <TableCell>
                      {user.name}
                      {user.is_admin && (
                        <Badge variant="secondary" className="ml-2">
                          admin
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {user.api_key.slice(0, 14)}…{" "}
                      <CopyButton text={user.api_key} />
                    </TableCell>
                    <TableCell>
                      <LimitMeters usage={user.usage} limits={user.limits} />
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap">
                      <Button
                        variant="ghost"
                        size="xs"
                        onClick={() =>
                          setExpanded(expanded === user.id ? null : user.id)
                        }
                      >
                        models
                      </Button>
                      <Button
                        variant="ghost"
                        size="xs"
                        onClick={() =>
                          setEditing(editing === user.id ? null : user.id)
                        }
                      >
                        edit limits
                      </Button>
                    </TableCell>
                  </TableRow>
                  {expanded === user.id && (
                    <TableRow>
                      <TableCell colSpan={4} className="bg-muted/30">
                        <ModelTable byModel={user.usage.by_model} />
                      </TableCell>
                    </TableRow>
                  )}
                  {editing === user.id && (
                    <TableRow>
                      <TableCell colSpan={4} className="bg-muted/30">
                        <EditLimits
                          apiKey={apiKey}
                          user={user}
                          onDone={() => {
                            setEditing(null)
                            refresh()
                          }}
                        />
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <CreateUser apiKey={apiKey} onCreated={refresh} />
    </div>
  )
}
