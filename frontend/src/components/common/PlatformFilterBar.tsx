import React from "react";
import { Star, Bookmark, Plus } from "lucide-react";

export interface SourceOption {
  id: string;
  name: string;
  dotColor?: string;
}

interface PlatformFilterBarProps {
  selectedSource: string;
  onSelectSource: (sourceId: string) => void;
  showLegends?: boolean;
  onAddSourceClick?: () => void;
  className?: string;
}

export const PLATFORM_SOURCES: SourceOption[] = [
  { id: "all", name: "All sources" },
  { id: "amazon", name: "Amazon", dotColor: "bg-amber-400" },
  { id: "flipkart", name: "Flipkart", dotColor: "bg-blue-500" },
  { id: "myntra", name: "Myntra", dotColor: "bg-pink-500" },
  { id: "meesho", name: "Meesho", dotColor: "bg-purple-500" },
  { id: "nykaa", name: "Nykaa", dotColor: "bg-rose-500" },
];

export const PlatformFilterBar: React.FC<PlatformFilterBarProps> = ({
  selectedSource,
  onSelectSource,
  showLegends = true,
  onAddSourceClick,
  className = "",
}) => {
  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-3 py-3 border-b border-slate-100 ${className}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 mr-1">
          Sources
        </span>
        {PLATFORM_SOURCES.map((src) => {
          const isSelected = selectedSource === src.id;
          return (
            <button
              key={src.id}
              type="button"
              onClick={() => onSelectSource(src.id)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                isSelected
                  ? "bg-indigo-600 text-white shadow-xs"
                  : "bg-white text-slate-700 border border-slate-200/80 hover:bg-slate-50"
              }`}
            >
              {src.dotColor && !isSelected && (
                <span className={`w-2 h-2 rounded-full ${src.dotColor}`} />
              )}
              {src.name}
            </button>
          );
        })}

        {onAddSourceClick && (
          <button
            type="button"
            onClick={onAddSourceClick}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border border-dashed border-slate-300 text-slate-500 hover:text-slate-700 hover:border-slate-400 bg-white transition-colors"
          >
            <Plus className="w-3 h-3" />
            Add source
          </button>
        )}
      </div>

      {showLegends && (
        <div className="flex items-center gap-4 text-xs text-slate-500 font-medium">
          <span className="inline-flex items-center gap-1.5">
            <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-500" />
            My shortlist
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Bookmark className="w-3.5 h-3.5 fill-indigo-600 text-indigo-600" />
            AI recommended
          </span>
        </div>
      )}
    </div>
  );
};
