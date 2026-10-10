import React from "react";
import { Search, RotateCcw } from "lucide-react";

interface FilterBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  selectedRegion: string;
  onRegionChange: (region: string) => void;
  selectedCategory?: string;
  onCategoryChange?: (category: string) => void;
  categories?: string[];
  selectedSort: string;
  onSortChange: (sort: string) => void;
  sortOptions?: Array<{ id: string; label: string }>;
  onReset?: () => void;
  placeholder?: string;
  className?: string;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  searchQuery,
  onSearchChange,
  selectedRegion,
  onRegionChange,
  selectedCategory = "all",
  onCategoryChange,
  categories = [],
  selectedSort,
  onSortChange,
  sortOptions = [
    { id: "score_desc", label: "Sort: Trend score" },
    { id: "date_desc", label: "Sort: Newest first" },
    { id: "price_asc", label: "Price: Low to High" },
    { id: "price_desc", label: "Price: High to Low" },
  ],
  onReset,
  placeholder = "Search products...",
  className = "",
}) => {
  return (
    <div
      className={`flex flex-wrap items-center gap-3 py-3 ${className}`}
    >
      {/* Search Input */}
      <div className="relative flex-1 min-w-[220px]">
        <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={placeholder}
          className="w-full pl-9 pr-3.5 py-2 text-xs bg-white border border-slate-200 rounded-lg text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all shadow-2xs"
        />
      </div>

      {/* Country / Region */}
      <div className="relative">
        <select
          value={selectedRegion}
          onChange={(e) => onRegionChange(e.target.value)}
          aria-label="Country / Region"
          className="appearance-none pl-3 pr-8 py-2 text-xs bg-white border border-slate-200 rounded-lg text-slate-700 font-medium hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-2xs cursor-pointer"
        >
          <option value="all">Country: All Regions</option>
          <option value="India">Country: India</option>
          <option value="USA">Country: USA</option>
          <option value="Europe">Country: Europe</option>
          <option value="UK">Country: United Kingdom</option>
          <option value="GCC_MiddleEast">Country: GCC / Middle East</option>
        </select>
        <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-slate-400">
          ▼
        </span>
      </div>

      {/* Category */}
      {onCategoryChange && (
        <div className="relative">
          <select
            value={selectedCategory}
            onChange={(e) => onCategoryChange(e.target.value)}
            aria-label="Category"
            className="appearance-none pl-3 pr-8 py-2 text-xs bg-white border border-slate-200 rounded-lg text-slate-700 font-medium hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-2xs cursor-pointer max-w-[180px] truncate"
          >
            <option value="all">Category: All</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
          <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-slate-400">
            ▼
          </span>
        </div>
      )}

      {/* Sorting */}
      <div className="relative">
        <select
          value={selectedSort}
          onChange={(e) => onSortChange(e.target.value)}
          aria-label="Sort order"
          className="appearance-none pl-3 pr-8 py-2 text-xs bg-white border border-slate-200 rounded-lg text-slate-700 font-medium hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-2xs cursor-pointer"
        >
          {sortOptions.map((opt) => (
            <option key={opt.id} value={opt.id}>
              {opt.label}
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-slate-400">
          ▼
        </span>
      </div>

      {/* Reset filters */}
      {onReset && (
        <button
          type="button"
          onClick={onReset}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-600 hover:text-slate-900 bg-white border border-slate-200 hover:border-slate-300 rounded-lg shadow-2xs transition-colors"
        >
          <RotateCcw className="w-3 h-3 text-slate-400" />
          Reset filters
        </button>
      )}
    </div>
  );
};
