import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "APRS — Autonomous Product Research System",
  description:
    "Autonomous Product Research System - Free direct-access e-commerce product discovery, 15-factor economics, and intelligence platform.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-[#F8FAFC] text-slate-900">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
