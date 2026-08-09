import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Package } from "lucide-react"
import { Suspense } from "react"

import { BoxesService } from "@/client"
import AddBox from "@/components/Boxes/AddBox"
import { columns } from "@/components/Boxes/columns"
import { DataTable } from "@/components/Common/DataTable"
import PendingBoxes from "@/components/Pending/PendingBoxes"

function getBoxesQueryOptions() {
  return {
    queryFn: () => BoxesService.readBoxes({ skip: 0, limit: 100 }),
    queryKey: ["boxes"],
  }
}

export const Route = createFileRoute("/_layout/boxes/")({
  component: Boxes,
  head: () => ({
    meta: [
      {
        title: "Boxes - Box-Doc Manager",
      },
    ],
  }),
})

function BoxesTableContent() {
  const { data: boxes } = useSuspenseQuery(getBoxesQueryOptions())

  if (boxes.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Package className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">You don't have any boxes yet</h3>
        <p className="text-muted-foreground">Add a new box to get started</p>
      </div>
    )
  }

  return <DataTable columns={columns} data={boxes.data} />
}

function BoxesTable() {
  return (
    <Suspense fallback={<PendingBoxes />}>
      <BoxesTableContent />
    </Suspense>
  )
}

function Boxes() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Boxes</h1>
          <p className="text-muted-foreground">
            Create and manage your boxes of documents
          </p>
        </div>
        <AddBox />
      </div>
      <BoxesTable />
    </div>
  )
}
