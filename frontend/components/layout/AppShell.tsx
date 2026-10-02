"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { PageSpinner } from "@/components/ui/Spinner";
import { useSession } from "@/lib/stores/session";
import { TopNav } from "./TopNav";

/**
 * Client-side auth guard for every authenticated page: validates the session cookie
 * via /api/auth/me and redirects to /login when it is missing or expired.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const status = useSession((s) => s.status);
  const refresh = useSession((s) => s.refresh);

  useEffect(() => {
    if (status === "idle") void refresh();
  }, [status, refresh]);

  useEffect(() => {
    if (status === "anon") router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [status, router, pathname]);

  if (status !== "authed") {
    return (
      <div className="flex min-h-screen flex-col">
        <PageSpinner label={status === "anon" ? "Redirecting to login…" : "Loading your workspace…"} />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <TopNav />
      <main className="flex flex-1 flex-col">{children}</main>
    </div>
  );
}
