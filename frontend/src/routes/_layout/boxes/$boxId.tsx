import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, FileText } from "lucide-react"
import { Suspense } from "react"

import { BoxesService, type BoxPublic, DocsService } from "@/client"
import ClaimBox from "@/components/Boxes/ClaimBox"
import RejectBox from "@/components/Boxes/RejectBox"
import { stageMeta } from "@/components/Boxes/stages"
import { DataTable } from "@/components/Common/DataTable"
import AddDoc from "@/components/Docs/AddDoc"
import { getColumns } from "@/components/Docs/columns"
import PendingDocs from "@/components/Pending/PendingDocs"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"

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

function BoxHeader({ box }: { box: BoxPublic }) {
  const { user: currentUser } = useAuth()
  const meta = stageMeta(box.stage)
  const holdsBox = box.assignee_id === currentUser?.id
  const isFinished = box.stage === "completed"
  const canEditDocs =
    !isFinished &&
    (Boolean(currentUser?.is_superuser) || holdsBox || !box.assignee_id)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">{box.name}</h1>
            <Badge variant={isFinished ? "default" : "secondary"}>
              {meta.label}
            </Badge>
          </div>
          <p className="text-muted-foreground">
            {box.description || "No description"}
          </p>
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Badge variant="outline">
              {box.doc_count} doc{box.doc_count === 1 ? "" : "s"}
            </Badge>
            <Badge variant="outline">{box.total_pages} pages</Badge>
            {!isFinished && box.doc_count > 0 ? (
              <Badge variant="outline">
                {box.stage_done_count} of {box.doc_count} {meta.verb}
              </Badge>
            ) : null}
            {box.assignee_name ? (
              <Badge variant="outline">
                Claimed by {holdsBox ? "you" : box.assignee_name}
              </Badge>
            ) : null}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <RejectBox box={box} />
          <ClaimBox box={box} size="default" />
          {canEditDocs ? <AddDoc boxId={box.id} /> : null}
        </div>
      </div>

      {isFinished ? (
        <p className="text-sm text-muted-foreground">
          This box has been through every stage and is now read-only.
        </p>
      ) : !box.assignee_id && box.doc_count > 0 ? (
        <p className="text-sm text-muted-foreground">
          Claim this box to start marking its docs as {meta.verb}.
        </p>
      ) : null}
    </div>
  )
}

function DocsTableContent({ box }: { box: BoxPublic }) {
  const { data: docs } = useSuspenseQuery(getDocsQueryOptions(box.id))

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

  return <DataTable columns={getColumns(box)} data={docs.data} />
}

function BoxContent({ boxId }: { boxId: string }) {
  const { data: box } = useSuspenseQuery(getBoxQueryOptions(boxId))

  return (
    <>
      <BoxHeader box={box} />
      <Suspense fallback={<PendingDocs />}>
        <DocsTableContent box={box} />
      </Suspense>
    </>
  )
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

      <Suspense fallback={<PendingDocs />}>
        <BoxContent boxId={boxId} />
      </Suspense>
    </div>
  )
}
