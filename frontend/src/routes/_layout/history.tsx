import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ArrowLeft, History as HistoryIcon, Search } from "lucide-react"
import { useEffect, useState } from "react"

import { BoxesService, type BoxPublic } from "@/client"
import { stageMeta } from "@/components/Boxes/stages"
import BoxHistory from "@/components/History/BoxHistory"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"

export const Route = createFileRoute("/_layout/history")({
  component: History,
  head: () => ({
    meta: [
      {
        title: "History - Box-Doc Manager",
      },
    ],
  }),
})

/** Wait for typing to settle before hitting the API. */
function useDebounced(value: string, delay = 300) {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debounced
}

function SearchResults({
  term,
  onSelect,
}: {
  term: string
  onSelect: (box: BoxPublic) => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["boxes", "search", term],
    queryFn: () => BoxesService.readBoxes({ q: term, skip: 0, limit: 50 }),
    enabled: term.trim().length > 0,
  })

  if (!term.trim()) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <HistoryIcon className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">Search for a box</h3>
        <p className="text-muted-foreground">
          Type part of a box name to see everything that has happened to it
        </p>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-16 w-full" />
        ))}
      </div>
    )
  }

  if (!data || data.data.length === 0) {
    return (
      <p className="text-muted-foreground py-12 text-center">
        No boxes match “{term}”.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {data.data.map((box) => (
        <button
          key={box.id}
          type="button"
          onClick={() => onSelect(box)}
          className="flex items-center justify-between gap-4 rounded-lg border p-4 text-left transition-colors hover:bg-muted"
        >
          <div className="flex flex-col gap-1">
            <span className="font-medium">{box.name}</span>
            <span className="text-sm text-muted-foreground">
              {box.description || "No description"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground tabular-nums">
              {box.doc_count} docs
            </span>
            <Badge variant={box.completed ? "default" : "secondary"}>
              {stageMeta(box.stage).label}
            </Badge>
          </div>
        </button>
      ))}
    </div>
  )
}

function History() {
  const [term, setTerm] = useState("")
  const [selected, setSelected] = useState<BoxPublic | null>(null)
  const debouncedTerm = useDebounced(term)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">History</h1>
        <p className="text-muted-foreground">
          Look up any box to see who handled each stage, and when
        </p>
      </div>

      {selected ? (
        <div className="flex flex-col gap-6">
          <Button
            variant="ghost"
            size="sm"
            className="w-fit -ml-2"
            onClick={() => setSelected(null)}
          >
            <ArrowLeft className="mr-1 size-4" />
            Back to search
          </Button>
          <BoxHistory box={selected} />
        </div>
      ) : (
        <>
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search boxes by name"
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              className="pl-9"
            />
          </div>
          <SearchResults term={debouncedTerm} onSelect={setSelected} />
        </>
      )}
    </div>
  )
}
