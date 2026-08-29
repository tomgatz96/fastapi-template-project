import { useMutation, useQueryClient } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { useState } from "react"

import { type BoxPublic, type DocPublic, DocsService } from "@/client"
import { formatTimestamp, STAGES, stageMeta } from "@/components/Boxes/stages"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
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

/**
 * When to ask before changing a doc's completion state.
 *
 * "always"  - confirm every tick and untick.
 * "last"    - only confirm the tick that finishes the stage, and any untick
 *             that discards a recorded stamp. Less clicking through dialogs
 *             on a box with many docs.
 */
const CONFIRM_COMPLETION: "always" | "last" = "always"

function CompletedToggle({ doc, box }: { doc: DocPublic; box: BoxPublic }) {
  const queryClient = useQueryClient()
  const { user: currentUser } = useAuth()
  const { showErrorToast } = useCustomToast()
  const [pendingValue, setPendingValue] = useState<boolean | null>(null)

  const mutation = useMutation({
    mutationFn: (completed: boolean) =>
      DocsService.updateDoc({ id: doc.id, requestBody: { completed } }),
    onSuccess: () => setPendingValue(null),
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

  const meta = stageMeta(box.stage)
  const nextStage = STAGES[STAGES.findIndex((s) => s.value === box.stage) + 1]

  // Ticking the last outstanding doc sends the whole box on to the next
  // stage and releases it, so it deserves a mention whatever the setting.
  const isLastOutstanding =
    !doc.completed && box.stage_done_count + 1 >= box.doc_count
  const discardsRecord = Boolean(doc.completed && doc[meta.atField])

  const needsConfirmation = (next: boolean) =>
    CONFIRM_COMPLETION === "always" ||
    (next ? isLastOutstanding : discardsRecord)

  const requestChange = (next: boolean) => {
    if (needsConfirmation(next)) {
      setPendingValue(next)
    } else {
      mutation.mutate(next)
    }
  }

  const confirmCopy = (next: boolean) => {
    if (next && isLastOutstanding) {
      return {
        title: `Finish ${meta.label}?`,
        description: `This is the last doc left. Marking it ${meta.verb} moves ${box.name} on to ${nextStage?.label ?? "the next stage"} and releases it back to the pool, so you will no longer be holding it.`,
        confirmLabel: `Mark ${meta.verb} and finish`,
        destructive: false,
      }
    }
    if (next) {
      return {
        title: `Mark as ${meta.verb}?`,
        description: `${doc.name} will be recorded as ${meta.verb} by you, with the current time.`,
        confirmLabel: `Mark ${meta.verb}`,
        destructive: false,
      }
    }
    return {
      title: `Undo ${meta.verb}?`,
      description: `The record of who ${meta.verb} ${doc.name} and when will be discarded.`,
      confirmLabel: "Undo",
      destructive: true,
    }
  }

  const copy = confirmCopy(pendingValue ?? true)

  const checkbox = (
    <Checkbox
      checked={doc.completed ?? false}
      disabled={mutation.isPending || !canComplete}
      onCheckedChange={(checked) => requestChange(checked === true)}
      aria-label={`Mark as ${meta.verb}`}
    />
  )

  if (canComplete) {
    return (
      <>
        {checkbox}
        <ConfirmDialog
          open={pendingValue !== null}
          onOpenChange={(open) => !open && setPendingValue(null)}
          title={copy.title}
          description={copy.description}
          confirmLabel={copy.confirmLabel}
          destructive={copy.destructive}
          loading={mutation.isPending}
          onConfirm={() =>
            pendingValue !== null && mutation.mutate(pendingValue)
          }
        />
      </>
    )
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
