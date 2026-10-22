"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Clock,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/timelog", label: "Timelog", icon: Clock },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-64 shrink-0 border-r border-line bg-[#0b0e14] flex flex-col gap-6 p-5">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-brand flex items-center justify-center font-bold text-white">
          J
        </div>
        <div>
          <h1 className="text-ink font-bold text-lg leading-tight">Anchor</h1>
          <p className="text-muted text-xs">Epics · Stories · Sub-task · Timelog</p>
        </div>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-surface2 text-ink border border-line"
                  : "text-muted hover:bg-surface2/60 hover:text-ink"
              }`}
            >
              <Icon size={18} />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
