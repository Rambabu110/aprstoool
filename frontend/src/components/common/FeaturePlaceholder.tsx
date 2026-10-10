"use client";

import React from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ArrowLeft, Clock, Layers, Sparkles } from "lucide-react";

interface FeaturePlaceholderProps {
  title: string;
  category: string;
  targetPhase: string;
  description: string;
  plannedCapabilities: string[];
}

export const FeaturePlaceholder: React.FC<FeaturePlaceholderProps> = ({
  title,
  category,
  targetPhase,
  description,
  plannedCapabilities,
}) => {
  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-indigo-600 uppercase tracking-wider">
              {category}
            </span>
            <span className="text-slate-300">•</span>
            <Badge variant="warning" className="text-xs">
              <Clock className="w-3 h-3 mr-1" />
              Planned for {targetPhase}
            </Badge>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{title}</h1>
          <p className="text-sm text-slate-500 mt-1">{description}</p>
        </div>

        <Link href="/dashboard">
          <Button variant="outline" size="sm" icon={<ArrowLeft className="w-4 h-4" />}>
            Back to Dashboard
          </Button>
        </Link>
      </div>

      {/* Main Info Card */}
      <Card className="p-6 space-y-6 border-indigo-100 bg-linear-to-br from-white to-indigo-50/20">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-100 flex items-center justify-center text-indigo-600 flex-shrink-0">
            <Layers className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h2 className="text-base font-semibold text-slate-900">
              Module Architecture &amp; Readiness
            </h2>
            <p className="text-sm text-slate-600">
              The underlying Python backend, database tables, and calculation models for this feature are already preserved in APRS V6 Pro. The frontend interface will be connected during {targetPhase} without altering business logic.
            </p>
          </div>
        </div>

        <div className="border-t border-slate-100 pt-5 space-y-3">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            Planned Capabilities for {title}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {plannedCapabilities.map((cap, i) => (
              <div
                key={i}
                className="flex items-center gap-2.5 p-3 rounded-lg bg-white border border-slate-200/80 text-sm text-slate-700"
              >
                <Sparkles className="w-4 h-4 text-indigo-500 flex-shrink-0" />
                <span>{cap}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="border-t border-slate-100 pt-4 flex items-center justify-between text-xs text-slate-400">
          <span>APRS V6 Pro Enterprise Modernization</span>
          <span className="font-medium text-emerald-600">Free Direct Access • Zero Auth Required</span>
        </div>
      </Card>
    </div>
  );
};
