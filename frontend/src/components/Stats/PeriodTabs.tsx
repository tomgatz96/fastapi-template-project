import type { StatsBuckets } from "@/client"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import StatsTable from "./StatsTable"

const PERIODS: { key: keyof StatsBuckets; label: string }[] = [
  { key: "day", label: "Today" },
  { key: "week", label: "This week" },
  { key: "month", label: "This month" },
]

interface PeriodTabsProps {
  buckets?: StatsBuckets
}

const PeriodTabs = ({ buckets }: PeriodTabsProps) => (
  <Tabs defaultValue="day">
    <TabsList>
      {PERIODS.map((period) => (
        <TabsTrigger key={period.key} value={period.key}>
          {period.label}
        </TabsTrigger>
      ))}
    </TabsList>
    {PERIODS.map((period) => (
      <TabsContent key={period.key} value={period.key} className="mt-4">
        <StatsTable period={buckets?.[period.key]} />
      </TabsContent>
    ))}
  </Tabs>
)

export default PeriodTabs
