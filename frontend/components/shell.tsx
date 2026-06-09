"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

const nav = [
  { href: "/dashboard", label: "Overview" },
  { href: "/opportunities", label: "Opportunities" },
  { href: "/signals", label: "Signals" },
  { href: "/workflow", label: "Workflow" },
  { href: "/rag", label: "RAG" },
  { href: "/reports", label: "Reports" },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-[1600px]">
        <aside className="hidden w-72 border-r border-white/8 bg-black/20 px-5 py-6 lg:flex lg:flex-col">
          <div className="mb-10">
            <div className="text-sm uppercase tracking-[0.35em] text-slate-400">AI Market Gap</div>
            <div className="mt-3 text-2xl font-semibold">Executive Intelligence</div>
          </div>
          <nav className="space-y-2">
            {nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`block rounded-xl px-4 py-3 text-sm transition ${
                  pathname === item.href ? "bg-accent/20 text-white ring-1 ring-accent/40" : "text-slate-300 hover:bg-white/5 hover:text-white"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="mt-auto rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
            Live backend connected through API routes.
          </div>
        </aside>
        <main className="flex-1">
          <div className="border-b border-white/8 bg-black/10 px-4 py-4 lg:px-8">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="text-sm text-slate-400">Executive Market Intelligence Dashboard</div>
                <div className="text-xl font-semibold">Opportunity Discovery Engine</div>
              </div>
              <div className="flex gap-2 text-xs text-slate-300">
                <span className="rounded-full border border-white/10 px-3 py-1">Dark mode</span>
                <span className="rounded-full border border-white/10 px-3 py-1">Live APIs</span>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2 lg:hidden">
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`rounded-full border px-3 py-1.5 text-xs ${
                    pathname === item.href ? "border-accent bg-accent/20 text-white" : "border-white/10 bg-white/5 text-slate-300"
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
          <div className="px-4 py-6 lg:px-8">{children}</div>
        </main>
      </div>
    </div>
  );
}
