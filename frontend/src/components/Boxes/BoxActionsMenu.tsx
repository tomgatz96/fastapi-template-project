import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { BoxPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useAuth from "@/hooks/useAuth"
import DeleteBox from "./DeleteBox"
import EditBox from "./EditBox"

interface BoxActionsMenuProps {
  box: BoxPublic
}

export const BoxActionsMenu = ({ box }: BoxActionsMenuProps) => {
  const [open, setOpen] = useState(false)
  const { user: currentUser } = useAuth()

  const canEdit = currentUser?.is_superuser || box.owner_id === currentUser?.id
  const canDelete = Boolean(currentUser?.is_superuser)

  if (!canEdit && !canDelete) {
    return null
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {canEdit ? (
          <EditBox box={box} onSuccess={() => setOpen(false)} />
        ) : null}
        {canDelete ? (
          <DeleteBox
            id={box.id}
            docCount={box.doc_count}
            onSuccess={() => setOpen(false)}
          />
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
