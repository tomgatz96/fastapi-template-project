import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, FileText } from "lucide-react"
import { Suspense } from "react"

import { BoxesService, DocsService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import AddDoc from "@/components/Docs/AddDoc"
import { columns } from "@/components/Docs/columns"
import PendingDocs from "@/components/Pending/PendingDocs"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

function getBoxQueryOptions(boxId: string) {
  return {
    queryFn: () => BoxesService.readBox({ id: boxId }),
    queryKey: ["box", boxId],
  }
}

function getDocsQueryOptions(boxId: string) {
  return {
    queryFn: () => DocsService.readDocs({ boxId }),
    queryKey: ["docs", boxId],
  }
}

export const Route = createFileRoute("/_layout/boxes/$boxId")({
  component: BoxDetail,
  head: () => ({
    meta: [
      {
        title: "Box - Box-Doc Manager",
      },
    ],
  }),
})

function BoxHeader({ boxId }: { boxId: string }) {
  const { data: box } = useSuspenseQuery(getBoxQueryOptions(boxId))

  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight">{box.name}</h1>
        <p className="text-muted-foreground">
          {box.description || "No description"}
        </p>
        <div className="flex items-center gap-2 pt-1">
          <Badge variant="outline">
            {box.doc_count} doc{box.doc_count === 1 ? "" : "s"}
          </Badge>
          <Badge variant="outline">{box.total_pages} pages</Badge>
          {box.doc_count === 0 ? (
            <Badge variant="outline">Empty</Badge>
          ) : box.completed ? (
            <Badge variant="default">Completed</Badge>
          ) : (
            <Badge variant="secondary">In progress</Badge>
          )}
        </div>
      </div>
      <AddDoc boxId={boxId} />
    </div>
  )
}

function DocsTableContent({ boxId }: { boxId: string }) {
  const { data: docs } = useSuspenseQuery(getDocsQueryOptions(boxId))

  if (docs.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <FileText className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">This box is empty</h3>
        <p className="text-muted-foreground">Add a doc to get started</p>
      </div>
    )
  }

  return <DataTable columns={columns} data={docs.data} />
}

function BoxDetail() {
  const { boxId } = Route.useParams()

  return (
    <div className="flex flex-col gap-6">
      <Button variant="ghost" size="sm" className="w-fit -ml-2" asChild>
        <Link to="/boxes">
          <ArrowLeft className="mr-1 size-4" />
          Back to boxes
        </Link>
      </Button>

      <Suspense fallback={<div className="h-24" />}>
        <BoxHeader boxId={boxId} />
      </Suspense>

      <Suspense fallback={<PendingDocs />}>
        <DocsTableContent boxId={boxId} />
      </Suspense>
    </div>
  )
}
