import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { DocPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useAuth from "@/hooks/useAuth"
import DeleteDoc from "./DeleteDoc"
import EditDoc from "./EditDoc"

interface DocActionsMenuProps {
  doc: DocPublic
}

export const DocActionsMenu = ({ doc }: DocActionsMenuProps) => {
  const [open, setOpen] = useState(false)
  const { user: currentUser } = useAuth()

  const canDelete = Boolean(currentUser?.is_superuser)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditDoc doc={doc} onSuccess={() => setOpen(false)} />
        {canDelete ? (
          <DeleteDoc
            id={doc.id}
            boxId={doc.box_id}
            onSuccess={() => setOpen(false)}
          />
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
