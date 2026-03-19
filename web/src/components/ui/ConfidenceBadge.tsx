import React from "react";

interface ConfidenceBadgeProps {
  confidence: number | null | undefined;
}

function getLevel(confidence: number | null | undefined) {
  if (confidence == null) return { label: "N/A", color: "#6B7280", bg: "#6B728018", border: "#6B728040" };
  const pct = confidence * 100;
  if (pct >= 95) return { label: "High", color: "#00D4AA", bg: "#00D4AA18", border: "#00D4AA40" };
  if (pct >= 80) return { label: "Medium", color: "#6C5CE7", bg: "#6C5CE718", border: "#6C5CE740" };
  if (pct >= 50) return { label: "Low", color: "#F39C12", bg: "#F39C1218", border: "#F39C1240" };
  return { label: "Needs Review", color: "#E74C3C", bg: "#E74C3C18", border: "#E74C3C40" };
}

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  const level = getLevel(confidence);
  const display = confidence != null ? `${Math.round(confidence * 100)}%` : "—";

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        padding: "2px 8px",
        borderRadius: "8px",
        fontSize: "12px",
        fontWeight: 500,
        color: level.color,
        backgroundColor: level.bg,
        border: `1px solid ${level.border}`,
      }}
    >
      {display} {level.label}
    </span>
  );
}
