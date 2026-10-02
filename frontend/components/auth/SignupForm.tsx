"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { FileText, PenTool } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Input";
import { authApi } from "@/lib/endpoints";
import { useSession } from "@/lib/stores/session";
import type { Role } from "@/lib/types";
import { cn, errorMessage } from "@/lib/utils";

const ROLES: { value: Role; title: string; body: string; icon: typeof PenTool }[] = [
  { value: "designer", title: "Designer", body: "Build reusable report formats", icon: PenTool },
  { value: "viewer", title: "Report viewer", body: "Generate PDFs from saved formats", icon: FileText },
];

export function SignupForm() {
  const router = useRouter();
  const setMe = useSession((s) => s.setMe);
  const [form, setForm] = useState({ company_name: "", full_name: "", email: "", password: "" });
  const [role, setRole] = useState<Role>("designer");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const me = await authApi.signup({ ...form, email: form.email.trim(), role });
      setMe(me);
      toast.success(`Welcome to Agentic Reports, ${me.full_name.split(" ")[0]}`);
      router.replace(me.snowflake_connected ? "/dashboard" : "/settings/connection");
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardContent className="px-6 py-6">
        <h1 className="text-xl font-semibold text-zinc-900">Create your account</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Colleagues with the same email domain join the same company workspace.
        </p>
        <form onSubmit={submit} className="mt-6 flex flex-col gap-4">
          <Field label="Company name" htmlFor="company">
            <Input id="company" required value={form.company_name} onChange={set("company_name")} placeholder="Classic Models Inc." />
          </Field>
          <Field label="Full name" htmlFor="name">
            <Input id="name" required autoComplete="name" value={form.full_name} onChange={set("full_name")} />
          </Field>
          <Field label="Work email" htmlFor="email">
            <Input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={form.email}
              onChange={set("email")}
              placeholder="you@company.com"
            />
          </Field>
          <Field label="Password" htmlFor="password" hint="At least 8 characters.">
            <Input
              id="password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={form.password}
              onChange={set("password")}
            />
          </Field>
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-zinc-700">Role</span>
            <div className="grid grid-cols-2 gap-2">
              {ROLES.map((r) => (
                <button
                  key={r.value}
                  type="button"
                  onClick={() => setRole(r.value)}
                  className={cn(
                    "flex flex-col items-start gap-1 rounded-lg border px-3 py-2.5 text-left transition-colors",
                    role === r.value
                      ? "border-indigo-500 bg-indigo-50/60 ring-2 ring-indigo-500/20"
                      : "border-zinc-200 hover:bg-zinc-50",
                  )}
                >
                  <span className="flex items-center gap-1.5 text-sm font-medium text-zinc-900">
                    <r.icon className="size-4 text-indigo-600" />
                    {r.title}
                  </span>
                  <span className="text-xs text-zinc-500">{r.body}</span>
                </button>
              ))}
            </div>
          </div>
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          <Button type="submit" size="lg" loading={busy} className="mt-1 w-full">
            Create account
          </Button>
        </form>
        <p className="mt-6 text-center text-sm text-zinc-500">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-indigo-600 hover:text-indigo-500">
            Log in
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
