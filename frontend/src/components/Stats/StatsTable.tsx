import type { PeriodStats, StageStats } from "@/client"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const ROWS: { key: keyof PeriodStats; label: string }[] = [
  { key: "preparation", label: "Preparation" },
  { key: "scan", label: "Scan" },
  { key: "quality_control", label: "Quality Control" },
]

const EMPTY: StageStats = { docs: 0, pages: 0 }

interface StatsTableProps {
  period?: PeriodStats
}

const StatsTable = ({ period }: StatsTableProps) => {
  const total = period?.total ?? EMPTY

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Stage</TableHead>
          <TableHead className="text-right">Docs</TableHead>
          <TableHead className="text-right">Pages</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {ROWS.map((row) => {
          const stats = (period?.[row.key] as StageStats | undefined) ?? EMPTY
          return (
            <TableRow key={row.key}>
              <TableCell>{row.label}</TableCell>
              <TableCell className="text-right tabular-nums">
                {stats.docs ?? 0}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {stats.pages ?? 0}
              </TableCell>
            </TableRow>
          )
        })}
        <TableRow className="font-semibold">
          <TableCell>Total</TableCell>
          <TableCell className="text-right tabular-nums">
            {total.docs ?? 0}
          </TableCell>
          <TableCell className="text-right tabular-nums">
            {total.pages ?? 0}
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  )
}

export default StatsTable
