import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"
import {
  formatDollars,
  formatTokens,
  type Limits,
  type UsageSummary,
} from "@/api"

function Meter({
  label,
  used,
  limit,
  format,
}: {
  label: string
  used: number
  limit: number | null
  format: (n: number) => string
}) {
  const percent = limit ? Math.min(100, (used / limit) * 100) : 0
  const maxed = limit !== null && used >= limit
  return (
    <div className="min-w-44 flex-1">
      <div className="flex justify-between gap-2 text-xs text-muted-foreground">
        <span className="whitespace-nowrap">{label}</span>
        <span
          className={cn(
            "tabular-nums whitespace-nowrap",
            maxed && "font-semibold text-destructive",
          )}
        >
          {format(used)} / {limit === null ? "∞" : format(limit)}
        </span>
      </div>
      <Progress
        value={percent}
        className={cn(
          "mt-1",
          maxed && "[&>[data-slot=progress-indicator]]:bg-destructive",
        )}
      />
    </div>
  )
}

export function LimitMeters({
  usage,
  limits,
}: {
  usage: UsageSummary
  limits: Limits
}) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-2">
      <Meter
        label="req/min"
        used={usage.requests_last_minute}
        limit={limits.requests_per_minute}
        format={String}
      />
      <Meter
        label="tokens/day"
        used={usage.tokens_last_day}
        limit={limits.tokens_per_day}
        format={formatTokens}
      />
      <Meter
        label="spend"
        used={usage.lifetime_spend_dollars}
        limit={limits.lifetime_spend_dollars}
        format={formatDollars}
      />
    </div>
  )
}
