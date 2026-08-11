import { useMutation, useQueryClient } from "@tanstack/react-query"
import { UserMinus, UserPlus } from "lucide-react"

import { type DocPublic, DocsService } from "@/client"
import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface ClaimDocProps {
  doc: DocPublic
}

const ClaimDoc = ({ doc }: ClaimDocProps) => {
  const queryClient = useQueryClient()
  const { user: currentUser } = useAuth()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["docs", doc.box_id] })
    queryClient.invalidateQueries({ queryKey: ["boxes"] })
    queryClient.invalidateQueries({ queryKey: ["box", doc.box_id] })
  }

  const claimMutation = useMutation({
    mutationFn: () => DocsService.claimDoc({ id: doc.id }),
    onSuccess: () => showSuccessToast("You claimed this doc"),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const releaseMutation = useMutation({
    mutationFn: () => DocsService.unclaimDoc({ id: doc.id }),
    onSuccess: () => showSuccessToast("You released this doc"),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const isPending = claimMutation.isPending || releaseMutation.isPending
  const isMine = doc.assignee_id === currentUser?.id
  const canRelease = isMine || currentUser?.is_superuser

  if (!doc.assignee_id) {
    return (
      <Button
        variant="outline"
        size="sm"
        disabled={isPending}
        onClick={() => claimMutation.mutate()}
      >
        <UserPlus className="mr-1 size-3.5" />
        Claim
      </Button>
    )
  }

  if (canRelease) {
    return (
      <Button
        variant="ghost"
        size="sm"
        disabled={isPending}
        onClick={() => releaseMutation.mutate()}
      >
        <UserMinus className="mr-1 size-3.5" />
        Release
      </Button>
    )
  }

  return null
}

export default ClaimDoc
