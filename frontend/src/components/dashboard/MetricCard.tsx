import React from "react";
import { Card } from "@/components/ui/Card";
import { Badge, BadgeVariant } from "@/components/ui/Badge";

interface MetricCardProps {
  label: string;
  value: number | string;
  badgeText?: string;
  badgeVariant?: BadgeVariant;
  icon?: React.ReactNode;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  badgeText,
  badgeVariant = "success",
  icon,
}) => {
  return (
    <Card className="flex flex-col justify-between h-36">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-500">{label}</span>
        {icon && <div className="text-slate-400">{icon}</div>}
      </div>

      <div className="flex items-baseline justify-between mt-2">
        <span className="text-3xl font-bold tracking-tight text-slate-900">
          {typeof value === "number" ? value.toLocaleString() : value}
        </span>
      </div>

      {badgeText && (
        <div className="mt-3">
          <Badge variant={badgeVariant} className="text-[11px] font-medium">
            {badgeText}
          </Badge>
        </div>
      )}
    </Card>
  );
};
