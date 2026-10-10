import React from "react";

export type BadgeVariant =
  | "default"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "purple"
  | "amazon"
  | "flipkart"
  | "myntra"
  | "meesho"
  | "nykaa"
  | "neutral";

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
  dot?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = "default",
  className = "",
  dot = false,
}) => {
  const variantStyles: Record<BadgeVariant, { badge: string; dot: string }> = {
    default: {
      badge: "bg-slate-100 text-slate-700 border border-slate-200",
      dot: "bg-slate-400",
    },
    success: {
      badge: "bg-emerald-50 text-emerald-700 border border-emerald-200",
      dot: "bg-emerald-500",
    },
    warning: {
      badge: "bg-amber-50 text-amber-700 border border-amber-200",
      dot: "bg-amber-500",
    },
    danger: {
      badge: "bg-rose-50 text-rose-700 border border-rose-200",
      dot: "bg-rose-500",
    },
    info: {
      badge: "bg-indigo-50 text-indigo-700 border border-indigo-200",
      dot: "bg-indigo-500",
    },
    purple: {
      badge: "bg-purple-50 text-purple-700 border border-purple-200",
      dot: "bg-purple-500",
    },
    amazon: {
      badge: "bg-amber-50 text-amber-800 border border-amber-200",
      dot: "bg-amber-500",
    },
    flipkart: {
      badge: "bg-blue-50 text-blue-700 border border-blue-200",
      dot: "bg-blue-500",
    },
    myntra: {
      badge: "bg-pink-50 text-pink-700 border border-pink-200",
      dot: "bg-pink-500",
    },
    meesho: {
      badge: "bg-purple-50 text-purple-700 border border-purple-200",
      dot: "bg-purple-500",
    },
    nykaa: {
      badge: "bg-rose-50 text-rose-700 border border-rose-200",
      dot: "bg-rose-500",
    },
    neutral: {
      badge: "bg-slate-50 text-slate-600 border border-slate-200",
      dot: "bg-slate-400",
    },
  };

  const style = variantStyles[variant] || variantStyles.default;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium transition-colors ${style.badge} ${className}`}
    >
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />}
      {children}
    </span>
  );
};
