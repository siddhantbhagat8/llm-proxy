import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatDollars, type ModelUsage } from "@/api"

export function ModelTable({
  byModel,
}: {
  byModel: Record<string, ModelUsage>
}) {
  const models = Object.entries(byModel)
  if (models.length === 0)
    return <p className="text-sm text-muted-foreground">No requests yet.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Model</TableHead>
          <TableHead className="text-right">Requests</TableHead>
          <TableHead className="text-right">Prompt tokens</TableHead>
          <TableHead className="text-right">Completion tokens</TableHead>
          <TableHead className="text-right">Cost</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {models.map(([model, usage]) => (
          <TableRow key={model}>
            <TableCell className="font-mono">{model}</TableCell>
            <TableCell className="text-right tabular-nums">
              {usage.requests}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {usage.prompt_tokens.toLocaleString()}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {usage.completion_tokens.toLocaleString()}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatDollars(usage.cost_dollars)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
