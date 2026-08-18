import type { BoxStage, DocPublic } from "@/client"

export interface StageMeta {
  value: BoxStage
  label: string
  /** Verb used when describing work in this stage, e.g. "3 of 8 scanned". */
  verb: string
  /** Which DocPublic fields hold this stage's completion record. */
  atField: keyof DocPublic
  nameField: keyof DocPublic
}

export const STAGES: StageMeta[] = [
  {
    value: "preparation",
    label: "Preparation",
    verb: "prepared",
    atField: "prepared_at",
    nameField: "prepared_by_name",
  },
  {
    value: "scan",
    label: "Scan",
    verb: "scanned",
    atField: "scanned_at",
    nameField: "scanned_by_name",
  },
  {
    value: "quality_control",
    label: "Quality Control",
    verb: "checked",
    atField: "checked_at",
    nameField: "checked_by_name",
  },
  {
    value: "completed",
    label: "Completed",
    verb: "completed",
    atField: "checked_at",
    nameField: "checked_by_name",
  },
]

export function stageMeta(stage: BoxStage): StageMeta {
  return STAGES.find((s) => s.value === stage) ?? STAGES[0]
}

export function formatTimestamp(value: unknown): string {
  if (typeof value !== "string" || !value) {
    return ""
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ""
  }
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}
