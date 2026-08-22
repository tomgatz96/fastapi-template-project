import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { ExternalLink } from "lucide-react"

import { type BoxPublic, DocsService } from "@/client"
import { formatTimestamp, stageMeta } from "@/components/Boxes/stages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface BoxHistoryProps {
  box: BoxPublic
}

function StageCell({
  name,
  at,
}: {
  name: string | null | undefined
  at: string | null | undefined
}) {
  if (!name) {
    return <span className="text-muted-foreground italic text-sm">Not yet</span>
  }
  return (
    <div className="flex flex-col gap-0.5 text-sm">
      <span>{name}</span>
      <span className="text-xs text-muted-foreground tabular-nums">
        {formatTimestamp(at)}
      </span>
    </div>
  )
}

const BoxHistory = ({ box }: BoxHistoryProps) => {
  const { data, isLoading } = useQuery({
    queryKey: ["docs", box.id],
    queryFn: () => DocsService.readDocs({ boxId: box.id }),
  })

  const meta = stageMeta(box.stage)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-semibold">{box.name}</h2>
            <Badge variant={box.completed ? "default" : "secondary"}>
              {meta.label}
            </Badge>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">
              {box.doc_count} doc{box.doc_count === 1 ? "" : "s"}
            </Badge>
            <Badge variant="outline">{box.total_pages} pages</Badge>
            <Badge variant="outline">
              Created by {box.owner_name ?? "Unknown"}
            </Badge>
            {box.assignee_name ? (
              <Badge variant="outline">Held by {box.assignee_name}</Badge>
            ) : null}
          </div>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link to="/boxes/$boxId" params={{ boxId: box.id }}>
            Open box
            <ExternalLink className="ml-1 size-3.5" />
          </Link>
        </Button>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-12 w-full" />
          ))}
        </div>
      ) : data && data.data.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Doc</TableHead>
              <TableHead>Pages</TableHead>
              <TableHead>Prepared by</TableHead>
              <TableHead>Scanned by</TableHead>
              <TableHead>Checked by</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.data.map((doc) => (
              <TableRow key={doc.id}>
                <TableCell className="font-medium">{doc.name}</TableCell>
                <TableCell className="tabular-nums">{doc.pages ?? 0}</TableCell>
                <TableCell>
                  <StageCell name={doc.prepared_by_name} at={doc.prepared_at} />
                </TableCell>
                <TableCell>
                  <StageCell name={doc.scanned_by_name} at={doc.scanned_at} />
                </TableCell>
                <TableCell>
                  <StageCell name={doc.checked_by_name} at={doc.checked_at} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <p className="text-muted-foreground py-8 text-center">
          This box has no docs, so there is nothing to show yet.
        </p>
      )}
    </div>
  )
}

export default BoxHistory
