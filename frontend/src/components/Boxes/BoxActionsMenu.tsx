import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { BoxPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteBox from "./DeleteBox"
import EditBox from "./EditBox"

interface BoxActionsMenuProps {
  box: BoxPublic
}

export const BoxActionsMenu = ({ box }: BoxActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditBox box={box} onSuccess={() => setOpen(false)} />
        <DeleteBox
          id={box.id}
          docCount={box.doc_count}
          onSuccess={() => setOpen(false)}
        />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
