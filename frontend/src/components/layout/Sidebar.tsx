"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  TrendingUp,
  Sparkles,
  Star,
  BookmarkCheck,
  Target,
  Package,
  Layers,
  Scale,
  DollarSign,
  LineChart,
  Rocket,
  ShieldAlert,
  Archive,
  Calendar,
  UploadCloud,
  Cpu,
  Database,
  Radio,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
} from "lucide-react";

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  isImplemented?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    title: "Core Discovery",
    items: [
      { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard, isImplemented: true },
      { name: "E-com Trend", href: "/trends", icon: TrendingUp, isImplemented: true },
      { name: "AI Trending Page", href: "/ai-trends", icon: Sparkles, isImplemented: true },
      { name: "My Shortlist", href: "/my-shortlist", icon: Star, isImplemented: true },
      { name: "AI Shortlist", href: "/ai-shortlist", icon: BookmarkCheck, isImplemented: true },
    ],
  },
  {
    title: "Pipeline & Evaluation",
    items: [
      { name: "Opportunities", href: "/opportunities", icon: Target, isImplemented: true },
      { name: "Product Catalog", href: "/products", icon: Package, isImplemented: true },
      { name: "Price Compare", href: "/price-compare", icon: Scale, isImplemented: true },
      { name: "Supplier & Sourcing", href: "/supplier", icon: Layers, isImplemented: true },
      { name: "15-Factor Economics", href: "/economics", icon: DollarSign, isImplemented: true },
      { name: "ML Predictions", href: "/predictions", icon: LineChart, isImplemented: true },
    ],
  },
  {
    title: "War Room & Operations",
    items: [
      { name: "Launchpad", href: "/launchpad", icon: Rocket, isImplemented: true },
      { name: "War Room", href: "/war-room", icon: ShieldAlert, isImplemented: true },
      { name: "Keepa / BSR", href: "/keepa", icon: Radio, isImplemented: true },
      { name: "Archive", href: "/archive", icon: Archive, isImplemented: true },
    ],
  },
  {
    title: "V8 Engine & Admin",
    items: [
      { name: "V8 Scheduler", href: "/v8-scheduler", icon: Calendar, isImplemented: true },
      { name: "Outcome Ingestion", href: "/outcome-ingestion", icon: UploadCloud, isImplemented: true },
      { name: "Calibration & Learning", href: "/calibration", icon: Cpu, isImplemented: true },
      { name: "Database Explorer", href: "/db-explorer", icon: Database, isImplemented: true },
      { name: "Integration Center", href: "/integrations", icon: Radio, isImplemented: true },
    ],
  },
];

export const Sidebar: React.FC = () => {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    "Core Discovery": true,
    "Pipeline & Evaluation": true,
    "War Room & Operations": true,
    "V8 Engine & Admin": true,
  });

  const toggleSection = (title: string) => {
    setOpenSections((prev) => ({ ...prev, [title]: !prev[title] }));
  };

  return (
    <aside
      className={`fixed top-0 left-0 z-40 h-screen transition-all duration-300 ease-in-out bg-[#0B0F19] text-slate-300 flex flex-col border-r border-slate-800 ${
        collapsed ? "w-18" : "w-64"
      }`}
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between px-4 h-16 border-b border-slate-800/80">
        <Link href="/dashboard" className="flex items-center gap-2.5 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-base shadow-md shadow-indigo-600/30 flex-shrink-0">
            A
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-bold text-white text-base tracking-tight leading-tight">
                APRS
              </span>
              <span className="text-[10px] text-indigo-400 font-medium tracking-wide uppercase">
                Autonomous Research
              </span>
            </div>
          )}
        </Link>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
        {NAV_SECTIONS.map((section) => {
          const isOpen = openSections[section.title] ?? true;
          return (
            <div key={section.title} className="space-y-1">
              {!collapsed && (
                <button
                  onClick={() => toggleSection(section.title)}
                  className="w-full flex items-center justify-between px-2 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider hover:text-slate-200 transition-colors text-left"
                >
                  <span>{section.title}</span>
                  <ChevronDown
                    className={`w-3 h-3 transition-transform duration-200 ${
                      isOpen ? "rotate-0" : "-rotate-90"
                    }`}
                  />
                </button>
              )}
              {(isOpen || collapsed) && (
                <div className="space-y-1 mt-1">
                  {section.items.map((item) => {
                    const isActive =
                      pathname === item.href ||
                      (item.href !== "/dashboard" && pathname?.startsWith(item.href));
                    const Icon = item.icon;

                    return (
                      <Link
                        key={item.name}
                        href={item.href}
                        title={collapsed ? item.name : undefined}
                        className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                          isActive
                            ? "bg-indigo-600 text-white shadow-sm shadow-indigo-600/30 font-semibold"
                            : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60"
                        }`}
                      >
                        <Icon
                          className={`w-4 h-4 flex-shrink-0 ${
                            isActive ? "text-white" : "text-slate-400 group-hover:text-slate-200"
                          }`}
                        />
                        {!collapsed && (
                          <div className="flex-1 flex items-center justify-between truncate">
                            <span className="truncate">{item.name}</span>
                            {!item.isImplemented && (
                              <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                                Phase 3+
                              </span>
                            )}
                          </div>
                        )}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* User / Direct Access Footer */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-900/50">
        <div className="flex items-center gap-3 px-2 py-1.5 rounded-lg bg-slate-800/40">
          <div className="w-8 h-8 rounded-full bg-slate-700 text-slate-200 flex items-center justify-center text-xs font-semibold flex-shrink-0 border border-slate-600">
            AP
          </div>
          {!collapsed && (
            <div className="flex flex-col truncate">
              <span className="text-xs font-medium text-slate-200 truncate">APRS Operator</span>
              <span className="text-[10px] text-emerald-400 font-medium truncate flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Free Direct Access
              </span>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
