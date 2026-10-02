"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ChevronDown, Database, LayoutDashboard, LogOut, PenTool, Play, Settings } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { useSession } from "@/lib/stores/session";
import { cn } from "@/lib/utils";
import { Logo } from "./Logo";

export function TopNav() {
  const pathname = usePathname();
  const me = useSession((s) => s.me);
  const isDesigner = me?.role === "designer";

  const links = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, match: "/dashboard" },
    ...(isDesigner ? [{ href: "/designer/new", label: "Designer", icon: PenTool, match: "/designer" }] : []),
    { href: "/generate", label: "Generate", icon: Play, match: "/generate" },
    { href: "/settings/connection", label: "Settings", icon: Settings, match: "/settings" },
  ];

  return (
    <header className="sticky top-0 z-30 border-b border-zinc-200 bg-white/90 backdrop-blur">
      <div className="flex h-14 items-center gap-6 px-4 sm:px-6">
        <Link href="/dashboard">
          <Logo />
        </Link>
        <nav className="flex items-center gap-1">
          {links.map((l) => {
            const active = pathname.startsWith(l.match);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors",
                  active ? "bg-zinc-100 text-zinc-900" : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900",
                )}
              >
                <l.icon className="size-4" />
                <span className="hidden sm:inline">{l.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          {me && !me.snowflake_connected && (
            <Link href="/settings/connection" className="hidden md:block">
              <Badge tone="amber">
                <Database className="size-3" /> Snowflake not connected
              </Badge>
            </Link>
          )}
          <UserMenu />
        </div>
      </div>
    </header>
  );
}

function UserMenu() {
  const router = useRouter();
  const me = useSession((s) => s.me);
  const logout = useSession((s) => s.logout);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  if (!me) return null;
  const initials = me.full_name
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-lg py-1 pr-1.5 pl-1 hover:bg-zinc-100"
      >
        <span className="flex size-7 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
          {initials}
        </span>
        <span className="hidden text-left leading-tight md:block">
          <span className="block text-sm font-medium text-zinc-900">{me.full_name}</span>
          <span className="block text-[11px] text-zinc-500">{me.company.name}</span>
        </span>
        <ChevronDown className="size-4 text-zinc-400" />
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-64 overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-lg">
          <div className="border-b border-zinc-100 px-4 py-3">
            <div className="text-sm font-medium text-zinc-900">{me.full_name}</div>
            <div className="truncate text-xs text-zinc-500">{me.email}</div>
            <div className="mt-2 flex items-center gap-1.5">
              <Badge tone="indigo">{me.role === "designer" ? "Designer" : "Report viewer"}</Badge>
              <Badge>{me.company.name}</Badge>
            </div>
          </div>
          <Link
            href="/settings/connection"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50"
          >
            <Database className="size-4 text-zinc-400" /> Snowflake connection
          </Link>
          <button
            type="button"
            onClick={async () => {
              setOpen(false);
              await logout();
              router.replace("/login");
            }}
            className="flex w-full items-center gap-2 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50"
          >
            <LogOut className="size-4 text-zinc-400" /> Log out
          </button>
        </div>
      )}
    </div>
  );
}
