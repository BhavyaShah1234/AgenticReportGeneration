"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { Copy, Database, LayoutGrid, Pencil, Play, Plus, Trash2, UserRound } from "lucide-react";
import { toast } from "sonner";
import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { RunsTable } from "@/components/runs/RunsTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Dialog";
import { PageSpinner } from "@/components/ui/Spinner";
import { formatApi, runApi } from "@/lib/endpoints";
import { useQuery } from "@/lib/hooks";
import { useSession } from "@/lib/stores/session";
import type { ReportFormat } from "@/lib/types";
import { errorMessage } from "@/lib/utils";

export function Dashboard() {
  const router = useRouter();
  const me = useSession((s) => s.me)!;
  const isDesigner = me.role === "designer";
  const formats = useQuery("formats", formatApi.list, { cache: false });
  const runs = useQuery("runs", runApi.list, { cache: false });
  const [toDelete, setToDelete] = useState<ReportFormat | null>(null);
  const [deleting, setDeleting] = useState(false);

  const duplicate = async (f: ReportFormat) => {
    try {
      const copy = await formatApi.duplicate(f.id);
      toast.success(`Duplicated as “${copy.name}”`);
      formats.reload();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  const remove = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await formatApi.remove(toDelete.id);
      toast.success(`Deleted “${toDelete.name}”`);
      setToDelete(null);
      formats.reload();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setDeleting(false);
    }
  };

  const formatList = [...(formats.data ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at));

  return (
    <PageContainer>
      <PageHeader
        title={`Welcome, ${me.full_name.split(" ")[0]}`}
        description={`${me.company.name} · ${isDesigner ? "Designer" : "Report viewer"}`}
        actions={
          <>
            <Button variant="outline" onClick={() => router.push("/generate")}>
              <Play className="size-4" /> Generate report
            </Button>
            {isDesigner && (
              <Button onClick={() => router.push("/designer/new")}>
                <Plus className="size-4" /> New report format
              </Button>
            )}
          </>
        }
      />

      {!me.snowflake_connected && (
        <Card className="mb-8 border-indigo-200 bg-gradient-to-r from-indigo-50 to-white">
          <CardContent className="flex flex-wrap items-center gap-4 py-5">
            <div className="flex size-10 items-center justify-center rounded-xl bg-indigo-600 text-white">
              <Database className="size-5" />
            </div>
            <div className="flex-1">
              <div className="font-semibold text-zinc-900">Connect Snowflake to get started</div>
              <p className="text-sm text-zinc-600">
                Widgets query your warehouse live. Add your account and a Programmatic Access Token.
              </p>
            </div>
            <Button onClick={() => router.push("/settings/connection")}>Connect Snowflake</Button>
          </CardContent>
        </Card>
      )}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-900">Report formats</h2>
          {formats.data && <span className="text-xs text-zinc-500">{formats.data.length} saved</span>}
        </div>
        {formats.loading ? (
          <PageSpinner />
        ) : formats.error ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{formats.error}</p>
        ) : formatList.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
              <LayoutGrid className="size-8 text-zinc-300" />
              <div className="font-medium text-zinc-900">No report formats yet</div>
              <p className="max-w-sm text-sm text-zinc-500">
                {isDesigner
                  ? "Design a reusable layout once, then generate it for any client and period."
                  : "Ask a designer at your company to create a report format."}
              </p>
              {isDesigner && (
                <Button onClick={() => router.push("/designer/new")}>
                  <Plus className="size-4" /> New report format
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {formatList.map((f) => (
              <FormatCard
                key={f.id}
                format={f}
                canEdit={isDesigner}
                onDuplicate={() => duplicate(f)}
                onDelete={() => setToDelete(f)}
              />
            ))}
          </div>
        )}
      </section>

      <section className="mt-10">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Recently generated reports</CardTitle>
            <Link href="/generate" className="text-xs font-medium text-indigo-600 hover:text-indigo-500">
              View all
            </Link>
          </CardHeader>
          {runs.loading ? (
            <PageSpinner />
          ) : runs.error ? (
            <p className="px-5 py-4 text-sm text-red-700">{runs.error}</p>
          ) : (
            <RunsTable runs={(runs.data ?? []).slice(0, 8)} />
          )}
        </Card>
      </section>

      <Dialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title="Delete report format?"
        description={`“${toDelete?.name}” will be removed for everyone at ${me.company.name}. Generated PDFs are kept.`}
        footer={
          <>
            <Button variant="outline" onClick={() => setToDelete(null)}>
              Cancel
            </Button>
            <Button variant="danger" loading={deleting} onClick={remove}>
              Delete
            </Button>
          </>
        }
      />
    </PageContainer>
  );
}

function FormatCard({
  format: f,
  canEdit,
  onDuplicate,
  onDelete,
}: {
  format: ReportFormat;
  canEdit: boolean;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const router = useRouter();
  const charts = f.widgets.filter((w) => w.type !== "heading" && w.type !== "text").length;
  return (
    <Card className="group flex flex-col transition-shadow hover:shadow-md">
      <div className="flex flex-1 flex-col gap-3 px-5 pt-5 pb-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="line-clamp-2 font-semibold text-zinc-900">{f.name}</h3>
          <Badge>v{f.version}</Badge>
        </div>
        <p className="line-clamp-2 min-h-10 text-sm text-zinc-500">{f.description || "No description"}</p>
        <div className="flex flex-wrap gap-1.5">
          <Badge tone="indigo">
            {f.widgets.length} widget{f.widgets.length === 1 ? "" : "s"}
            {charts !== f.widgets.length && ` · ${charts} data`}
          </Badge>
          {f.params.map((p) => (
            <Badge key={p.name}>{p.label}</Badge>
          ))}
          {f.client_scope && (
            <Badge tone="amber">
              <UserRound className="size-3" /> {f.client_scope}
            </Badge>
          )}
        </div>
        <div className="mt-auto text-xs text-zinc-400">
          Updated {formatDistanceToNow(new Date(f.updated_at), { addSuffix: true })}
        </div>
      </div>
      <div className="flex items-center gap-1 border-t border-zinc-100 px-3 py-2">
        <Button size="sm" onClick={() => router.push(`/generate?format=${f.id}`)}>
          <Play className="size-3.5" /> Generate
        </Button>
        {canEdit && (
          <>
            <Button size="sm" variant="ghost" onClick={() => router.push(`/designer/${f.id}`)}>
              <Pencil className="size-3.5" /> Edit
            </Button>
            <div className="ml-auto flex">
              <Button size="icon-sm" variant="ghost" title="Duplicate" onClick={onDuplicate}>
                <Copy className="size-3.5" />
              </Button>
              <Button
                size="icon-sm"
                variant="ghost"
                title="Delete"
                className="text-zinc-500 hover:bg-red-50 hover:text-red-600"
                onClick={onDelete}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
