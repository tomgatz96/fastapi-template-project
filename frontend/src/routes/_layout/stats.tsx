import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { useState } from "react"

import { StatsService, type UserStats } from "@/client"
import PeriodTabs from "@/components/Stats/PeriodTabs"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export const Route = createFileRoute("/_layout/stats")({
  component: Stats,
  head: () => ({
    meta: [
      {
        title: "Stats - Box-Doc Manager",
      },
    ],
  }),
})

function Stats() {
  const [selected, setSelected] = useState<UserStats | null>(null)

  // The API stores timestamps in UTC; tell it which day "today" is for us.
  const tzOffset = new Date().getTimezoneOffset()

  const { data, isLoading } = useQuery({
    queryKey: ["stats", tzOffset],
    queryFn: () => StatsService.readStats({ tzOffsetMinutes: tzOffset }),
  })

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const selectedUser = selected
    ? (data?.users.find((u) => u.user_id === selected.user_id) ?? selected)
    : null

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Stats</h1>
        <p className="text-muted-foreground">
          Docs and pages completed, by stage and period
        </p>
      </div>

      {selectedUser ? (
        <div className="flex flex-col gap-4">
          <Button
            variant="ghost"
            size="sm"
            className="w-fit -ml-2"
            onClick={() => setSelected(null)}
          >
            <ArrowLeft className="mr-1 size-4" />
            Back to everyone
          </Button>
          <Card>
            <CardHeader>
              <CardTitle>{selectedUser.user_name}</CardTitle>
              <CardDescription>Work recorded by this person</CardDescription>
            </CardHeader>
            <CardContent>
              <PeriodTabs buckets={selectedUser.stats} />
            </CardContent>
          </Card>
        </div>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Everyone</CardTitle>
              <CardDescription>Across all users</CardDescription>
            </CardHeader>
            <CardContent>
              <PeriodTabs buckets={data?.totals} />
            </CardContent>
          </Card>

          <div className="flex flex-col gap-3">
            <h2 className="text-lg font-semibold">By person</h2>
            <div className="flex flex-col gap-2">
              {data?.users.map((user) => (
                <button
                  key={user.user_id}
                  type="button"
                  onClick={() => setSelected(user)}
                  className="flex items-center justify-between gap-4 rounded-lg border p-4 text-left transition-colors hover:bg-muted"
                >
                  <span className="font-medium">{user.user_name}</span>
                  <span className="text-sm text-muted-foreground tabular-nums">
                    {user.stats.month?.total?.docs ?? 0} docs ·{" "}
                    {user.stats.month?.total?.pages ?? 0} pages this month
                  </span>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
