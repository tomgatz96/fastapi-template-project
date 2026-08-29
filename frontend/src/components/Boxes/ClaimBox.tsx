import { useMutation, useQueryClient } from "@tanstack/react-query"
import { UserMinus, UserPlus } from "lucide-react"
import { useState } from "react"

import { BoxesService, type BoxPublic } from "@/client"
import { stageMeta } from "@/components/Boxes/stages"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface ClaimBoxProps {
  box: BoxPublic
  size?: "sm" | "default"
}

const ClaimBox = ({ box, size = "sm" }: ClaimBoxProps) => {
  const [confirmRelease, setConfirmRelease] = useState(false)
  const queryClient = useQueryClient()
  const { user: currentUser } = useAuth()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["boxes"] })
    queryClient.invalidateQueries({ queryKey: ["box", box.id] })
    queryClient.invalidateQueries({ queryKey: ["docs", box.id] })
  }

  const claimMutation = useMutation({
    mutationFn: () => BoxesService.claimBox({ id: box.id }),
    onSuccess: () => showSuccessToast("You claimed this box"),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const releaseMutation = useMutation({
    mutationFn: () => BoxesService.unclaimBox({ id: box.id }),
    onSuccess: () => showSuccessToast("You released this box"),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const isPending = claimMutation.isPending || releaseMutation.isPending
  const isMine = box.assignee_id === currentUser?.id
  const canRelease = isMine || currentUser?.is_superuser

  // Releasing is only worth a pause once there is progress to hand over:
  // letting go of an untouched box costs nothing.
  const hasProgress = box.stage_done_count > 0
  const meta = stageMeta(box.stage)

  if (box.assignee_id) {
    if (!canRelease) {
      return null
    }
    return (
      <>
        <Button
          variant="ghost"
          size={size}
          disabled={isPending}
          onClick={() =>
            hasProgress ? setConfirmRelease(true) : releaseMutation.mutate()
          }
        >
          <UserMinus className="mr-1 size-3.5" />
          Release
        </Button>
        <ConfirmDialog
          open={confirmRelease}
          onOpenChange={setConfirmRelease}
          title="Release this box?"
          description={
            isMine
              ? `${box.stage_done_count} of ${box.doc_count} docs are already ${meta.verb}. That work is kept, but the box goes back to the pool and anyone can pick it up — including someone else finishing it.`
              : `This box is claimed by ${box.assignee_name}. Releasing it returns the box to the pool while ${box.stage_done_count} of ${box.doc_count} docs are ${meta.verb}.`
          }
          confirmLabel="Release"
          loading={releaseMutation.isPending}
          onConfirm={() => {
            releaseMutation.mutate()
            setConfirmRelease(false)
          }}
        />
      </>
    )
  }

  if (box.completed) {
    return null
  }

  return (
    <Button
      variant="outline"
      size={size}
      disabled={isPending}
      onClick={() => claimMutation.mutate()}
    >
      <UserPlus className="mr-1 size-3.5" />
      Claim
    </Button>
  )
}

export default ClaimBox
