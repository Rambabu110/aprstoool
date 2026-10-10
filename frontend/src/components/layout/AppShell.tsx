"use client";

import React, { Suspense } from "react";
import { Sidebar } from "./Sidebar";

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  return (
    <div className="min-h-screen bg-[#F8FAFC] flex">
      {/* Sidebar Navigation */}
      <Suspense
        fallback={
          <aside className="fixed top-0 left-0 z-40 h-screen w-64 bg-[#0B0F19] border-r border-slate-800" />
        }
      >
        <Sidebar />
      </Suspense>

      {/* Main Content Area */}
      <main className="flex-1 ml-64 min-h-screen flex flex-col p-6 lg:p-8 max-w-[1600px] transition-all duration-300">
        <Suspense fallback={<div className="p-8 text-slate-400">Loading page...</div>}>
          {children}
        </Suspense>
      </main>
    </div>
  );
};

