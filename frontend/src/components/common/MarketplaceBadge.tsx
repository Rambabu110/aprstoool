import React from "react";

interface MarketplaceBadgeProps {
  source?: string | null;
  className?: string;
}

export const MarketplaceBadge: React.FC<MarketplaceBadgeProps> = ({
  source,
  className = "",
}) => {
  if (!source) {
    return <span className="text-xs text-slate-400">-</span>;
  }

  const s = source.toLowerCase();

  let dotColor = "bg-slate-400";
  let label = source;

  if (s.includes("amazon")) {
    dotColor = "bg-amber-500";
    label = "Amazon";
  } else if (s.includes("flipkart")) {
    dotColor = "bg-blue-500";
    label = "Flipkart";
  } else if (s.includes("myntra")) {
    dotColor = "bg-pink-500";
    label = "Myntra";
  } else if (s.includes("meesho")) {
    dotColor = "bg-purple-500";
    label = "Meesho";
  } else if (s.includes("nykaa")) {
    dotColor = "bg-rose-500";
    label = "Nykaa";
  } else if (s.includes("tiktok")) {
    dotColor = "bg-slate-900";
    label = "TikTok Shop";
  } else if (s.includes("instagram")) {
    dotColor = "bg-fuchsia-500";
    label = "Instagram";
  } else if (s.includes("reddit")) {
    dotColor = "bg-orange-500";
    label = "Reddit";
  } else if (s.includes("google")) {
    dotColor = "bg-emerald-500";
    label = "Google Trends";
  } else if (s.includes("ebay")) {
    dotColor = "bg-yellow-500";
    label = "eBay";
  } else if (s.includes("aliexpress")) {
    dotColor = "bg-red-500";
    label = "AliExpress";
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium text-slate-700 ${className}`}
    >
      <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
      <span>{label}</span>
    </span>
  );
};
