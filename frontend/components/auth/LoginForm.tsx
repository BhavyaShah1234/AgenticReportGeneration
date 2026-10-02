"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Input";
import { authApi } from "@/lib/endpoints";
import { useSession } from "@/lib/stores/session";
import { errorMessage } from "@/lib/utils";

export function LoginForm() {
  const router = useRouter();
  const setMe = useSession((s) => s.setMe);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const me = await authApi.login(email.trim(), password);
      setMe(me);
      toast.success(`Welcome back, ${me.full_name.split(" ")[0]}`);
      const next = new URLSearchParams(window.location.search).get("next");
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard");
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardContent className="px-6 py-6">
        <h1 className="text-xl font-semibold text-zinc-900">Log in</h1>
        <p className="mt-1 text-sm text-zinc-500">Use your company work email.</p>
        <form onSubmit={submit} className="mt-6 flex flex-col gap-4">
          <Field label="Work email" htmlFor="email">
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
            />
          </Field>
          <Field label="Password" htmlFor="password">
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          <Button type="submit" size="lg" loading={busy} className="mt-1 w-full">
            Log in
          </Button>
        </form>
        <p className="mt-6 text-center text-sm text-zinc-500">
          New to Agentic Reports?{" "}
          <Link href="/signup" className="font-medium text-indigo-600 hover:text-indigo-500">
            Create an account
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
