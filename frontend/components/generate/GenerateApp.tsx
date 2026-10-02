"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { format as fmtDate } from "date-fns";
import { CheckCircle2, Circle, Download, ExternalLink, FileText, Loader2, Play, TriangleAlert, UserRound } from "lucide-react";
import { toast } from "sonner";
import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { ParamValueInput } from "@/components/params/ParamValueInput";
import { cleanValues, defaultValues, isDateRange } from "@/components/params/presets";
import { RunsTable, RunValues } from "@/components/runs/RunsTable";
import { Badge } from "@/components/ui/Badge";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Field } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { PageSpinner } from "@/components/ui/Spinner";
import { connectionApi, formatApi, runApi } from "@/lib/endpoints";
import { useQuery } from "@/lib/hooks";
import type { ParamValues, ReportFormat, RunSummary } from "@/lib/types";
import { cn, errorMessage } from "@/lib/utils";

export function GenerateApp({ initialFormatId }: { initialFormatId: string | null }) {
  const formats = useQuery("formats", formatApi.list, { cache: false });
  const runs = useQuery("runs", runApi.list, { cache: false });
  const connection = useQuery("connection", connectionApi.get);
  const [formatId, setFormatId] = useState<string | null>(initialFormatId);
  const [activeRun, setActiveRun] = useState<RunSummary | null>(null);
  const [historyFilter, setHistoryFilter] = useState<string>(initialFormatId ?? "");

  const format = formats.data?.find((f) => f.id === formatId) ?? null;
  const table = format?.default_source?.table ?? connection.data?.default_table ?? null;

  const history = useMemo(
    () =>
      [...(runs.data ?? [])]
        .filter((r) => !historyFilter || r.format_id === historyFilter)
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [runs.data, historyFilter],
  );

  return (
    <PageContainer className="max-w-7xl">
      <PageHeader
        title="Generate a report"
        description="Pick a saved format, choose the client and period, and get a ready-to-send PDF."
      />
      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>1. Report format</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {formats.loading ? (
                <PageSpinner />
              ) : formats.error ? (
                <p className="text-sm text-red-600">{formats.error}</p>
              ) : (formats.data ?? []).length === 0 ? (
                <p className="text-sm text-zinc-500">
                  No report formats yet.{" "}
                  <Link href="/designer/new" className="font-medium text-indigo-600">
                    Design one
                  </Link>
                </p>
              ) : (
                <>
                  <Select
                    value={formatId ?? ""}
                    placeholder="Choose a report format…"
                    onValueChange={(id) => {
                      setFormatId(id || null);
                      if (id) setHistoryFilter(id);
                    }}
                    options={(formats.data ?? []).map((f) => ({ value: f.id, label: f.name }))}
                  />
                  {format && <FormatSummary format={format} />}
                </>
              )}
            </CardContent>
          </Card>
          {format && (
            <RunForm
              key={format.id}
              format={format}
              table={table}
              onDone={(run) => {
                setActiveRun(run);
                runs.reload();
              }}
            />
          )}
        </div>

        <ResultPanel run={activeRun} />
      </div>

      <Card className="mt-8">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Run history</CardTitle>
          <Select
            selectSize="sm"
            className="w-60"
            value={historyFilter}
            onValueChange={setHistoryFilter}
            placeholder="All formats"
            options={(formats.data ?? []).map((f) => ({ value: f.id, label: f.name }))}
          />
        </CardHeader>
        {runs.loading ? (
          <PageSpinner />
        ) : runs.error ? (
          <p className="px-5 py-4 text-sm text-red-600">{runs.error}</p>
        ) : (
          <RunsTable runs={history} onView={setActiveRun} activeId={activeRun?.id} />
        )}
      </Card>
    </PageContainer>
  );
}

function FormatSummary({ format }: { format: ReportFormat }) {
  return (
    <div className="rounded-lg bg-zinc-50 px-3 py-2.5 text-sm">
      {format.description && <p className="text-zinc-600">{format.description}</p>}
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Badge tone="indigo">{format.widgets.length} widgets</Badge>
        <Badge>v{format.version}</Badge>
        {format.client_scope && (
          <Badge tone="amber">
            <UserRound className="size-3" /> {format.client_scope}
          </Badge>
        )}
        {format.widgets.some((w) => w.options?.narrative) && <Badge tone="green">AI narrative</Badge>}
      </div>
    </div>
  );
}

const STAGES = [
  { at: 0, label: "Running queries in Snowflake" },
  { at: 4, label: "Computing archetypes" },
  { at: 9, label: "Writing the AI narrative" },
  { at: 20, label: "Rendering the PDF" },
];

function RunForm({
  format,
  table,
  onDone,
}: {
  format: ReportFormat;
  table: string | null;
  onDone: (run: RunSummary) => void;
}) {
  const [values, setValues] = useState<ParamValues>(() => defaultValues(format.params, format.client_scope));
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const hasNarrative = format.widgets.some((w) => w.type === "text" && w.options?.narrative);
  const stages = STAGES.filter((s) => hasNarrative || !s.label.includes("narrative"));

  useEffect(() => {
    if (!running) return;
    const started = Date.now();
    const t = setInterval(() => setElapsed((Date.now() - started) / 1000), 250);
    return () => clearInterval(t);
  }, [running]);

  const missing = format.params.filter((p) => {
    if (p.required === false) return false;
    const v = values[p.name];
    if (p.type === "date_range") return !isDateRange(v) || !v.start || !v.end;
    return v == null || v === "";
  });

  const run = async () => {
    setRunning(true);
    setElapsed(0);
    setError(null);
    try {
      const r = await runApi.create(format.id, cleanValues(values));
      if (r.status === "failed" || !r.pdf_url) {
        setError(r.error ?? "Report generation failed");
      } else {
        toast.success("Report ready", { description: format.name });
      }
      onDone(r);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setRunning(false);
    }
  };

  const currentStage = stages.reduce((idx, s, i) => (elapsed >= s.at ? i : idx), 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>2. Runtime parameters</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {format.params.length === 0 && (
          <p className="text-sm text-zinc-500">This format has no parameters; it always covers all data.</p>
        )}
        {format.params.map((p) => (
          <Field
            key={p.name}
            label={
              <span>
                {p.label}
                {p.required !== false && <span className="text-red-500"> *</span>}
              </span>
            }
          >
            <ParamValueInput
              def={p}
              table={table}
              value={values[p.name]}
              onChange={(v) => setValues((vs) => ({ ...vs, [p.name]: v }))}
            />
          </Field>
        ))}

        {running ? (
          <div className="flex flex-col gap-2 rounded-lg border border-indigo-100 bg-indigo-50/50 p-3">
            {stages.map((s, i) => (
              <div
                key={s.label}
                className={cn(
                  "flex items-center gap-2 text-sm",
                  i < currentStage ? "text-zinc-500" : i === currentStage ? "font-medium text-indigo-800" : "text-zinc-400",
                )}
              >
                {i < currentStage ? (
                  <CheckCircle2 className="size-4 text-emerald-500" />
                ) : i === currentStage ? (
                  <Loader2 className="size-4 animate-spin text-indigo-600" />
                ) : (
                  <Circle className="size-4" />
                )}
                {s.label}
                {i === currentStage && "…"}
              </div>
            ))}
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-indigo-100">
              <div
                className="h-full rounded-full bg-indigo-500 transition-[width] duration-300"
                style={{ width: `${Math.min(95, 100 * (1 - Math.exp(-elapsed / 20)))}%` }}
              />
            </div>
            <div className="text-xs text-zinc-500">{Math.round(elapsed)}s · this can take up to a minute</div>
          </div>
        ) : (
          <Button size="lg" onClick={run} disabled={missing.length > 0} className="w-full">
            <Play className="size-4" /> Generate PDF
          </Button>
        )}
        {!running && missing.length > 0 && (
          <p className="text-xs text-zinc-500">Choose {missing.map((p) => p.label).join(", ")} to continue.</p>
        )}
        {error && (
          <p className="flex items-start gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm whitespace-pre-wrap text-red-700">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" />
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function ResultPanel({ run }: { run: RunSummary | null }) {
  if (!run) {
    return (
      <Card className="flex min-h-[60vh] flex-col items-center justify-center gap-3 border-dashed p-8 text-center">
        <FileText className="size-10 text-zinc-300" />
        <div className="font-medium text-zinc-900">Your PDF will appear here</div>
        <p className="max-w-sm text-sm text-zinc-500">
          Generated reports are saved to the run history below, so anyone at your company can download them later.
        </p>
      </Card>
    );
  }
  const failed = run.status === "failed" || !run.pdf_url;
  return (
    <Card className="flex min-h-[60vh] flex-col overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 px-5 py-3">
        <div className="min-w-0">
          <div className="truncate font-semibold text-zinc-900">{run.format_name}</div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
            <RunValues values={run.values} />
            <span>· {fmtDate(new Date(run.created_at), "MMM d, yyyy HH:mm")}</span>
          </div>
        </div>
        {!failed && (
          <div className="flex gap-2">
            <a href={runApi.pdfUrl(run.id)} target="_blank" rel="noreferrer" className={buttonClass("outline", "sm")}>
              <ExternalLink className="size-3.5" /> Open
            </a>
            <a href={runApi.pdfUrl(run.id, true)} className={buttonClass("primary", "sm")}>
              <Download className="size-3.5" /> Download PDF
            </a>
          </div>
        )}
      </div>
      {failed ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
          <TriangleAlert className="size-8 text-red-400" />
          <div className="font-medium text-zinc-900">Generation failed</div>
          <p className="max-w-md text-sm whitespace-pre-wrap text-red-600">{run.error ?? run.status}</p>
        </div>
      ) : (
        <iframe key={run.id} src={runApi.pdfUrl(run.id)} title="Report PDF preview" className="min-h-[75vh] w-full flex-1 bg-zinc-100" />
      )}
    </Card>
  );
}
