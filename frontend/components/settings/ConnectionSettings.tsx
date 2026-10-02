"use client";

import { useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { CheckCircle2, CircleAlert, HelpCircle, KeyRound, PlugZap, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Input";
import { PageSpinner } from "@/components/ui/Spinner";
import { connectionApi, schemaApi } from "@/lib/endpoints";
import { invalidate, useQuery } from "@/lib/hooks";
import { useSession } from "@/lib/stores/session";
import type { ConnectionInfo } from "@/lib/types";
import { errorMessage } from "@/lib/utils";

const DEFAULT_TABLE = "DEMO_CORP.SALES.V_SALES";

export function ConnectionSettings() {
  const conn = useQuery("connection", connectionApi.get, { cache: false });
  const me = useSession((s) => s.me);

  return (
    <PageContainer className="max-w-5xl">
      <PageHeader
        title="Snowflake connection"
        description={`One connection is shared by everyone at ${me?.company.name ?? "your company"}. Business data stays in Snowflake.`}
      />
      {conn.loading ? (
        <PageSpinner />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <ConnectionForm
            key={conn.data?.last_tested_at ?? (conn.data?.connected ? "c" : "n")}
            info={conn.data ?? { connected: false }}
            loadError={conn.error}
            onSaved={conn.reload}
          />
          <HelpBox />
        </div>
      )}
    </PageContainer>
  );
}

function ConnectionForm({
  info,
  loadError,
  onSaved,
}: {
  info: ConnectionInfo;
  loadError?: string;
  onSaved: () => void;
}) {
  const refreshSession = useSession((s) => s.refresh);
  const canEdit = useSession((s) => s.me?.role === "designer");
  const [form, setForm] = useState({
    account: info.account ?? "",
    user: info.user ?? "",
    warehouse: info.warehouse ?? "COMPUTE_WH",
    role: info.role ?? "",
    default_table: info.default_table ?? DEFAULT_TABLE,
    token: "",
  });
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tables = useQuery(info.connected ? "tables" : null, schemaApi.tables);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await connectionApi.save({
        account: form.account.trim(),
        user: form.user.trim(),
        token: form.token.trim() || null,
        warehouse: form.warehouse.trim() || null,
        role: form.role.trim() || null,
        default_table: form.default_table.trim() || null,
      });
      toast.success("Connected to Snowflake");
      invalidate("connection");
      invalidate("tables");
      invalidate("columns:");
      invalidate("values:");
      await refreshSession();
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      const r = await connectionApi.test();
      if (r.ok) toast.success("Connection works");
      else toast.error(r.error ?? "Connection test failed");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setTesting(false);
    }
  };

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>Connection details</CardTitle>
          <CardDescription>Authenticate with a Programmatic Access Token (PAT).</CardDescription>
        </div>
        {info.connected ? (
          <Badge tone="green">
            <CheckCircle2 className="size-3" /> Connected
          </Badge>
        ) : (
          <Badge tone="amber">
            <CircleAlert className="size-3" /> Not connected
          </Badge>
        )}
      </CardHeader>
      <form onSubmit={save}>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          {loadError && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 sm:col-span-2">
              Could not load the current connection: {loadError}
            </p>
          )}
          {info.connected && (
            <div className="flex items-center justify-between rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800 sm:col-span-2">
              <span>
                Connected as <b>{info.user}</b> on <b>{info.account}</b>
                {info.last_tested_at &&
                  ` · tested ${formatDistanceToNow(new Date(info.last_tested_at), { addSuffix: true })}`}
              </span>
              <Button size="sm" variant="outline" onClick={test} loading={testing}>
                <RefreshCw className="size-3.5" /> Re-test
              </Button>
            </div>
          )}
          <Field label="Account identifier" htmlFor="account" hint="ORGNAME-ACCOUNTNAME, e.g. HEGKLQQ-OI17617">
            <Input id="account" required value={form.account} onChange={set("account")} placeholder="ORG-ACCOUNT" />
          </Field>
          <Field label="User (login name)" htmlFor="user">
            <Input id="user" required value={form.user} onChange={set("user")} placeholder="JDOE" />
          </Field>
          <Field label="Warehouse" htmlFor="warehouse">
            <Input id="warehouse" value={form.warehouse} onChange={set("warehouse")} placeholder="COMPUTE_WH" />
          </Field>
          <Field label="Role" htmlFor="role" hint="Optional; uses your default role if empty.">
            <Input id="role" value={form.role} onChange={set("role")} placeholder="ACCOUNTADMIN" />
          </Field>
          <Field
            label={
              <span className="flex items-center gap-1">
                <KeyRound className="size-3.5" /> Programmatic Access Token
              </span>
            }
            htmlFor="token"
            className="sm:col-span-2"
            hint={
              info.connected
                ? "Stored encrypted and never shown again. Leave empty to keep the current token."
                : "Stored encrypted; it is never sent back to the browser."
            }
          >
            <Input
              id="token"
              type="password"
              required={!info.connected}
              autoComplete="off"
              value={form.token}
              onChange={set("token")}
              placeholder={info.connected ? "•••••••• (unchanged)" : "Paste your PAT"}
            />
          </Field>
          <Field
            label="Default table or view"
            htmlFor="default_table"
            className="sm:col-span-2"
            hint="Used by new widgets unless a format or widget picks another source."
          >
            <Input
              id="default_table"
              list="table-options"
              value={form.default_table}
              onChange={set("default_table")}
              placeholder={DEFAULT_TABLE}
              className="font-mono text-xs"
            />
            <datalist id="table-options">
              {tables.data?.map((t) => <option key={t.table} value={t.table} />)}
            </datalist>
          </Field>
          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm whitespace-pre-wrap text-red-700 sm:col-span-2">
              {error}
            </p>
          )}
        </CardContent>
        <CardFooter className="justify-end">
          {!canEdit && <span className="mr-auto text-xs text-zinc-500">Only designers can change the connection.</span>}
          <Button type="submit" loading={saving} disabled={!canEdit}>
            <PlugZap className="size-4" /> Test &amp; Save
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}

function HelpBox() {
  return (
    <Card className="h-fit border-indigo-100 bg-indigo-50/40">
      <CardHeader className="border-indigo-100">
        <CardTitle className="flex items-center gap-1.5">
          <HelpCircle className="size-4 text-indigo-600" /> Where do I find these?
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 text-sm text-zinc-600">
        <div>
          <div className="font-medium text-zinc-900">Account identifier</div>
          <p className="mt-1">
            In Snowsight open your profile menu → <i>Connect a tool to Snowflake</i> → <i>Account identifier</i>, or
            run in a worksheet:
          </p>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-zinc-900 px-3 py-2 font-mono text-[11px] text-zinc-100">
            SELECT CURRENT_ORGANIZATION_NAME()||&apos;-&apos;||CURRENT_ACCOUNT_NAME();
          </pre>
        </div>
        <div>
          <div className="font-medium text-zinc-900">User</div>
          <p className="mt-1">
            Your <i>login name</i> from the same Account details panel, or:
          </p>
          <pre className="mt-2 rounded-lg bg-zinc-900 px-3 py-2 font-mono text-[11px] text-zinc-100">
            SELECT CURRENT_USER();
          </pre>
        </div>
        <div>
          <div className="font-medium text-zinc-900">Programmatic Access Token</div>
          <p className="mt-1">
            Snowsight → profile → <i>Settings</i> → <i>Authentication</i> → <i>Programmatic access tokens</i> →{" "}
            <i>Generate new token</i>. Your user may need a network policy that allows your IP.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
