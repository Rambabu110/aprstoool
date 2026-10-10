import React from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { TopTrendingItem } from "@/types/api";
import { ArrowUpRight } from "lucide-react";

interface TopTrendingCardProps {
  items: TopTrendingItem[];
}

export const TopTrendingCard: React.FC<TopTrendingCardProps> = ({ items }) => {
  return (
    <Card className="flex flex-col justify-between space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <h2 className="text-base font-semibold text-slate-900">Top trending now</h2>
        <Link
          href="/trends"
          className="text-xs font-medium text-indigo-600 hover:text-indigo-700 flex items-center gap-1 transition-colors"
        >
          View all
          <ArrowUpRight className="w-3 h-3" />
        </Link>
      </div>

      {/* List */}
      <div className="space-y-3 divide-y divide-slate-100">
        {items.slice(0, 5).map((item) => (
          <div
            key={item.product_id}
            className="pt-2.5 first:pt-0 flex items-center justify-between group hover:bg-slate-50/50 -mx-2 px-2 py-1 rounded-lg transition-colors"
          >
            <div className="flex items-center gap-3 overflow-hidden pr-2">
              <span className="w-4 text-xs font-bold text-slate-400 flex-shrink-0">
                {item.rank}
              </span>
              <div className="truncate">
                <Link
                  href={`/products?selected=${encodeURIComponent(item.product_id)}`}
                  className="text-sm font-medium text-slate-800 hover:text-indigo-600 truncate block transition-colors"
                >
                  {item.name}
                </Link>
                <span className="text-[11px] text-slate-400 block truncate">
                  {item.price ? `₹${item.price.toLocaleString()} • ` : ""}
                  {item.source}
                </span>
              </div>
            </div>

            <Badge variant="info" className="flex-shrink-0 font-bold text-[11px]">
              Score {Math.round(item.score)}
            </Badge>
          </div>
        ))}

        {items.length === 0 && (
          <div className="py-6 text-center text-xs text-slate-400">
            No trending products recorded yet
          </div>
        )}
      </div>
    </Card>
  );
};
