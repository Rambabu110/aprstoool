import React from "react";

interface ScoreBadgeProps {
  score?: number | null;
  className?: string;
  size?: "sm" | "md" | "lg";
}

export const ScoreBadge: React.FC<ScoreBadgeProps> = ({
  score,
  className = "",
  size = "md",
}) => {
  if (score === undefined || score === null) {
    return <span className="text-xs text-slate-400 font-mono">-</span>;
  }

  const rounded = Math.round(score);

  let colorClasses = "bg-slate-100 text-slate-700 border-slate-200";
  if (rounded >= 85) {
    colorClasses = "bg-indigo-50 text-indigo-700 border-indigo-200 font-bold";
  } else if (rounded >= 70) {
    colorClasses = "bg-emerald-50 text-emerald-700 border-emerald-200 font-bold";
  } else if (rounded >= 50) {
    colorClasses = "bg-amber-50 text-amber-700 border-amber-200 font-medium";
  } else {
    colorClasses = "bg-rose-50 text-rose-700 border-rose-200 font-medium";
  }

  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs",
    md: "px-2.5 py-1 text-xs",
    lg: "px-3 py-1.5 text-sm font-bold",
  }[size];

  return (
    <span
      className={`inline-flex items-center justify-center rounded-lg border font-mono tabular-nums shadow-2xs ${colorClasses} ${sizeClasses} ${className}`}
    >
      {rounded}
    </span>
  );
};
