import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Undo2 } from "lucide-react"
import { useState } from "react"

import { BoxesService, type BoxPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { STAGES, stageMeta } from "./stages"

interface RejectBoxProps {
  box: BoxPublic
}

const RejectBox = ({ box }: RejectBoxProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { user: currentUser } = useAuth()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const index = STAGES.findIndex((s) => s.value === box.stage)
  const previous = index > 0 ? STAGES[index - 1] : null
  const holdsBox = box.assignee_id === currentUser?.id

  const mutation = useMutation({
    mutationFn: () => BoxesService.rejectBox({ id: box.id }),
    onSuccess: () => {
      showSuccessToast(
        `Sent back to ${previous?.label ?? "the previous stage"}`,
      )
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["boxes"] })
      queryClient.invalidateQueries({ queryKey: ["box", box.id] })
      queryClient.invalidateQueries({ queryKey: ["docs", box.id] })
    },
  })

  if (!previous || !holdsBox || box.stage === "completed") {
    return null
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <Undo2 className="mr-1 size-3.5" />
          Send back
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Send back to {previous.label}</DialogTitle>
          <DialogDescription>
            This box will return to {previous.label} and be released back to the
            pool. Every doc will need to be {previous.verb} again, and the work
            already recorded for {stageMeta(box.stage).label} and{" "}
            {previous.label} will be cleared.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="mt-4">
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            variant="destructive"
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            Send back
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default RejectBox
