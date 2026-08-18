import { useMutation, useQueryClient } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"

import { type BoxPublic, type DocPublic, DocsService } from "@/client"
import { formatTimestamp, stageMeta } from "@/components/Boxes/stages"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"
import { DocActionsMenu } from "./DocActionsMenu"

function CompletedToggle({ doc, box }: { doc: DocPublic; box: BoxPublic }) {
  const queryClient = useQueryClient()
  const { user: currentUser } = useAuth()
  const { showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: (completed: boolean) =>
      DocsService.updateDoc({ id: doc.id, requestBody: { completed } }),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["docs", doc.box_id] })
      queryClient.invalidateQueries({ queryKey: ["boxes"] })
      queryClient.invalidateQueries({ queryKey: ["box", doc.box_id] })
    },
  })

  const holdsBox = box.assignee_id === currentUser?.id
  const isFinished = box.stage === "completed"
  const canComplete =
    !isFinished && (Boolean(currentUser?.is_superuser) || holdsBox)

  const checkbox = (
    <Checkbox
      checked={doc.completed ?? false}
      disabled={mutation.isPending || !canComplete}
      onCheckedChange={(checked) => mutation.mutate(checked === true)}
      aria-label={`Mark as ${stageMeta(box.stage).verb}`}
    />
  )

  if (canComplete) {
    return checkbox
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex">{checkbox}</span>
      </TooltipTrigger>
      <TooltipContent>
        {isFinished
          ? "This box is completed"
          : box.assignee_id
            ? `${box.assignee_name} is working on this box`
            : "Claim this box before marking its docs"}
      </TooltipContent>
    </Tooltip>
  )
}

export function getColumns(box: BoxPublic): ColumnDef<DocPublic>[] {
  const meta = stageMeta(box.stage)

  return [
    {
      id: "completed",
      header: "Done",
      cell: ({ row }) => <CompletedToggle doc={row.original} box={box} />,
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
      id: "stage_record",
      header: meta.label === "Completed" ? "Checked by" : `${meta.label} by`,
      cell: ({ row }) => {
        const name = row.original[meta.nameField]
        const at = row.original[meta.atField]
        if (!name) {
          return <span className="text-muted-foreground italic text-sm">—</span>
        }
        return (
          <div className="flex flex-col gap-0.5 text-sm">
            <span>{String(name)}</span>
            <span className="text-xs text-muted-foreground tabular-nums">
              {formatTimestamp(at)}
            </span>
          </div>
        )
      },
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
}
