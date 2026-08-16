import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { LimitMeters } from "@/components/meters"
import { ModelTable } from "@/components/model-table"
import { usePoll } from "@/use-poll"
import type { OwnUsage } from "@/api"

export function UserView({ apiKey }: { apiKey: string }) {
  const { data } = usePoll<OwnUsage>(apiKey, "/usage")
  if (!data) return <p className="text-muted-foreground">Loading…</p>
  return (
    <Card>
      <CardHeader>
        <CardTitle>{data.user.name} — your usage</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <LimitMeters usage={data.usage} limits={data.limits} />
        <ModelTable byModel={data.usage.by_model} />
      </CardContent>
    </Card>
  )
}
