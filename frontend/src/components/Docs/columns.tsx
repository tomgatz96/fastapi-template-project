import { useMutation, useQueryClient } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"

import { type DocPublic, DocsService } from "@/client"
import { Checkbox } from "@/components/ui/checkbox"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"
import { DocActionsMenu } from "./DocActionsMenu"

function CompletedToggle({ doc }: { doc: DocPublic }) {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: (completed: boolean) =>
      DocsService.updateDoc({
        id: doc.id,
        requestBody: { completed },
      }),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["docs", doc.box_id] })
      queryClient.invalidateQueries({ queryKey: ["boxes"] })
      queryClient.invalidateQueries({ queryKey: ["box", doc.box_id] })
    },
  })

  return (
    <Checkbox
      checked={doc.completed ?? false}
      disabled={mutation.isPending}
      onCheckedChange={(checked) => mutation.mutate(checked === true)}
      aria-label="Toggle completed"
    />
  )
}

export const columns: ColumnDef<DocPublic>[] = [
  {
    id: "completed",
    header: "Done",
    cell: ({ row }) => <CompletedToggle doc={row.original} />,
  },
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
      <span
        className={cn(
          "font-medium",
          row.original.completed && "line-through text-muted-foreground",
        )}
      >
        {row.original.name}
      </span>
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
    accessorKey: "pages",
    header: "Pages",
    cell: ({ row }) => (
      <span className="tabular-nums">{row.original.pages ?? 0}</span>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <DocActionsMenu doc={row.original} />
      </div>
    ),
  },
]
