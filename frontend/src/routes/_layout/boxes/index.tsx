import { useQueries } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Package } from "lucide-react"

import { BoxesService, type BoxPublic } from "@/client"
import AddBox from "@/components/Boxes/AddBox"
import { columns } from "@/components/Boxes/columns"
import { STAGES } from "@/components/Boxes/stages"
import { DataTable } from "@/components/Common/DataTable"
import PendingBoxes from "@/components/Pending/PendingBoxes"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

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

const EMPTY_MESSAGES: Record<string, string> = {
  preparation: "No boxes waiting to be prepared",
  scan: "No boxes ready for scanning",
  quality_control: "No boxes waiting for quality control",
  completed: "No boxes have been completed yet",
}

function StagePanel({
  stage,
  boxes,
  isLoading,
}: {
  stage: string
  boxes: BoxPublic[]
  isLoading: boolean
}) {
  if (isLoading) {
    return <PendingBoxes />
  }

  if (boxes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Package className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">{EMPTY_MESSAGES[stage]}</h3>
        <p className="text-muted-foreground">
          Boxes arrive here as work in the previous stage is finished
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={boxes} />
}

function Boxes() {
  const results = useQueries({
    queries: STAGES.map((stage) => ({
      queryKey: ["boxes", stage.value],
      queryFn: () =>
        BoxesService.readBoxes({ stage: stage.value, skip: 0, limit: 100 }),
    })),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Boxes</h1>
          <p className="text-muted-foreground">
            Track boxes through preparation, scanning and quality control
          </p>
        </div>
        <AddBox />
      </div>

      <Tabs defaultValue={STAGES[0].value}>
        <TabsList>
          {STAGES.map((stage, index) => {
            const count = results[index].data?.count
            return (
              <TabsTrigger key={stage.value} value={stage.value}>
                {stage.label}
                {count !== undefined && count > 0 ? (
                  <Badge variant="secondary" className="ml-2">
                    {count}
                  </Badge>
                ) : null}
              </TabsTrigger>
            )
          })}
        </TabsList>

        {STAGES.map((stage, index) => (
          <TabsContent key={stage.value} value={stage.value} className="mt-4">
            <StagePanel
              stage={stage.value}
              boxes={results[index].data?.data ?? []}
              isLoading={results[index].isLoading}
            />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
