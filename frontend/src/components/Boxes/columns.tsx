import { Link } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"

import type { BoxPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { BoxActionsMenu } from "./BoxActionsMenu"

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
    accessorKey: "owner_name",
    header: "Owner",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {row.original.owner_name ?? "Unknown"}
      </span>
    ),
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
    accessorKey: "completed",
    header: "Status",
    cell: ({ row }) => {
      const { completed, doc_count } = row.original
      if (doc_count === 0) {
        return <Badge variant="outline">Empty</Badge>
      }
      return completed ? (
        <Badge variant="default">Completed</Badge>
      ) : (
        <Badge variant="secondary">In progress</Badge>
      )
    },
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
