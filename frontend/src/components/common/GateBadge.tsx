import React from "react";

interface GateBadgeProps {
  passed: number;
  total?: number;
  status?: string | null;
  className?: string;
}

export const GateBadge: React.FC<GateBadgeProps> = ({
  passed,
  total = 5,
  status,
  className = "",
}) => {
  if (status === "KILLED" || status === "FAIL") {
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200 ${className}`}
      >
        Killed
      </span>
    );
  }

  if (passed === 0 && (!status || status === "PENDING" || status === "NOT_RUN")) {
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 ${className}`}
      >
        Gate not run
      </span>
    );
  }

  const isFull = passed >= total;
  const isPartial = passed > 0 && passed < total;

  if (isFull) {
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 ${className}`}
      >
        {passed}/{total} passed
      </span>
    );
  }

  if (isPartial) {
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 ${className}`}
      >
        {passed}/{total} passed
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200 ${className}`}
    >
      {passed}/{total} passed
    </span>
  );
};
