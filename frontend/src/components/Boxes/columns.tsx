import { Link } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"

import type { BoxPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { BoxActionsMenu } from "./BoxActionsMenu"
import ClaimBox from "./ClaimBox"
import { stageMeta } from "./stages"

export const columns: ColumnDef<BoxPublic>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
      <Link
        to="/boxes/$boxId"
        params={{ boxId: row.original.id }}
        className="font-medium hover:underline"
      >
        {row.original.name}
      </Link>
    ),
  },
  {
    accessorKey: "description",
    header: "Description",
    cell: ({ row }) => {
      const description = row.original.description
      return (
        <span
          className={cn(
            "max-w-xs truncate block text-muted-foreground",
            !description && "italic",
          )}
        >
          {description || "No description"}
        </span>
      )
    },
  },
  {
    accessorKey: "doc_count",
    header: "Docs",
    cell: ({ row }) => (
      <span className="tabular-nums">{row.original.doc_count}</span>
    ),
  },
  {
    accessorKey: "total_pages",
    header: "Pages",
    cell: ({ row }) => (
      <span className="tabular-nums">{row.original.total_pages}</span>
    ),
  },
  {
    id: "progress",
    header: "Progress",
    cell: ({ row }) => {
      const { stage, doc_count, stage_done_count } = row.original
      if (stage === "completed") {
        return <Badge variant="default">Done</Badge>
      }
      if (doc_count === 0) {
        return <Badge variant="outline">Empty</Badge>
      }
      return (
        <span className="text-sm tabular-nums text-muted-foreground">
          {stage_done_count} of {doc_count} {stageMeta(stage).verb}
        </span>
      )
    },
  },
  {
    id: "assignee",
    header: "Working on it",
    cell: ({ row }) => {
      const name = row.original.assignee_name
      return (
        <span
          className={cn("text-sm", name ? "" : "text-muted-foreground italic")}
        >
          {name ?? "Unclaimed"}
        </span>
      )
    },
  },
  {
    id: "claim",
    header: () => <span className="sr-only">Claim</span>,
    cell: ({ row }) => <ClaimBox box={row.original} />,
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <BoxActionsMenu box={row.original} />
      </div>
    ),
  },
]
