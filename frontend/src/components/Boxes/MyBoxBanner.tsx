import { Link } from "@tanstack/react-router"
import { ArrowRight, Package } from "lucide-react"

import type { BoxPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { stageMeta } from "./stages"

interface MyBoxBannerProps {
  box: BoxPublic
}

const MyBoxBanner = ({ box }: MyBoxBannerProps) => {
  const meta = stageMeta(box.stage)
  const remaining = box.doc_count - box.stage_done_count

  return (
    <Card className="border-primary/40 bg-primary/5">
      <CardContent className="flex flex-wrap items-center justify-between gap-4 py-4">
        <div className="flex items-center gap-3">
          <div className="rounded-full bg-primary/10 p-2">
            <Package className="size-5 text-primary" />
          </div>
          <div className="flex flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">{box.name}</span>
              <Badge variant="secondary">{meta.label}</Badge>
            </div>
            <span className="text-sm text-muted-foreground">
              {box.doc_count === 0
                ? "This box has no docs yet"
                : remaining === 0
                  ? `All ${box.doc_count} docs ${meta.verb}`
                  : `${remaining} of ${box.doc_count} docs still to be ${meta.verb}`}
            </span>
          </div>
        </div>

        <Button asChild>
          <Link to="/boxes/$boxId" params={{ boxId: box.id }}>
            Continue
            <ArrowRight className="ml-1 size-4" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  )
}

export default MyBoxBanner
