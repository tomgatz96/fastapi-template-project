import { useMutation, useQueryClient } from "@tanstack/react-query"
import { UserMinus, UserPlus } from "lucide-react"

import { BoxesService, type BoxPublic } from "@/client"
import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface ClaimBoxProps {
  box: BoxPublic
  size?: "sm" | "default"
}

const ClaimBox = ({ box, size = "sm" }: ClaimBoxProps) => {
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

  if (box.assignee_id) {
    if (!canRelease) {
      return null
    }
    return (
      <Button
        variant="ghost"
        size={size}
        disabled={isPending}
        onClick={() => releaseMutation.mutate()}
      >
        <UserMinus className="mr-1 size-3.5" />
        Release
      </Button>
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
