"use client";

import { Fragment, type ReactNode } from "react";
import type { WidgetData, WidgetSpec } from "@/lib/types";
import type { RenderMode } from "./chartData";

/** Inline markdown-lite: **bold**, *italic*, `code`. */
function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const t = m[0];
    if (t.startsWith("**")) out.push(<strong key={k++} className="font-semibold text-zinc-900">{t.slice(2, -2)}</strong>);
    else if (t.startsWith("`")) out.push(<code key={k++} className="rounded bg-zinc-100 px-1 text-[0.9em]">{t.slice(1, -1)}</code>);
    else out.push(<em key={k++}>{t.slice(1, -1)}</em>);
    last = m.index + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

type Block = { kind: "p" | "ul" | "ol" | "h"; lines: string[]; level?: number };

function parse(md: string): Block[] {
  const blocks: Block[] = [];
  let cur: Block | null = null;
  for (const raw of md.replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trim();
    if (!line) {
      cur = null;
      continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    const ul = /^[-*•]\s+(.*)$/.exec(line);
    const ol = /^\d+[.)]\s+(.*)$/.exec(line);
    if (h) {
      blocks.push({ kind: "h", lines: [h[2]], level: h[1].length });
      cur = null;
    } else if (ul) {
      if (cur?.kind !== "ul") blocks.push((cur = { kind: "ul", lines: [] }));
      cur.lines.push(ul[1]);
    } else if (ol) {
      if (cur?.kind !== "ol") blocks.push((cur = { kind: "ol", lines: [] }));
      cur.lines.push(ol[1]);
    } else {
      if (cur?.kind !== "p") blocks.push((cur = { kind: "p", lines: [] }));
      cur.lines.push(line);
    }
  }
  return blocks;
}

export function MarkdownLite({ text }: { text: string }) {
  return (
    <>
      {parse(text).map((b, i) => {
        if (b.kind === "h")
          return (
            <p key={i} className="font-semibold text-zinc-900">
              {inline(b.lines[0])}
            </p>
          );
        if (b.kind === "ul" || b.kind === "ol") {
          const List = b.kind === "ul" ? "ul" : "ol";
          return (
            <List key={i} className={b.kind === "ul" ? "list-disc space-y-0.5 pl-5" : "list-decimal space-y-0.5 pl-5"}>
              {b.lines.map((l, j) => (
                <li key={j}>{inline(l)}</li>
              ))}
            </List>
          );
        }
        return (
          <p key={i}>
            {b.lines.map((l, j) => (
              <Fragment key={j}>
                {j > 0 && " "}
                {inline(l)}
              </Fragment>
            ))}
          </p>
        );
      })}
    </>
  );
}

/** Rich text / narrative. Body = options.text, or data.meta.text for LLM narrative widgets. */
export function TextWidget({ spec, data, mode }: { spec: WidgetSpec; data?: WidgetData | null; mode: RenderMode }) {
  const metaText = typeof data?.meta?.text === "string" ? (data.meta.text as string) : "";
  const text = (spec.options?.narrative ? metaText || spec.options?.text : spec.options?.text || metaText) ?? "";
  if (!text.trim()) {
    return (
      <div className="flex h-full items-center px-4 text-xs text-zinc-400 italic">
        {spec.options?.narrative
          ? mode === "design"
            ? "AI narrative — generated from this report's data when the report runs."
            : "No narrative generated."
          : "Empty text block"}
      </div>
    );
  }
  return (
    // bottom padding keeps text clear of the designer's bottom-left "AI narrative" badge
    <div className={mode === "print" ? "h-full px-4 pb-3" : "h-full overflow-auto px-4 pb-8"}>
      <div className="space-y-2 text-sm leading-relaxed text-zinc-700">
        <MarkdownLite text={text} />
      </div>
      {spec.options?.narrative && typeof data?.meta?.model === "string" && (
        <p className="mt-2 text-[11px] text-zinc-400">Written by {describeModel(data.meta.model as string)}</p>
      )}
    </div>
  );
}

/** "cortex:llama3.3-70b" -> "llama3.3-70b (open-weight) via Snowflake Cortex"; "ollama:qwen3:8b" -> "qwen3:8b (open-weight) via Ollama". */
function describeModel(label: string): string {
  const [provider, ...rest] = label.split(":");
  const model = rest.join(":") || label;
  const via = provider === "cortex" ? "Snowflake Cortex" : provider === "ollama" ? "Ollama, running locally" : provider;
  return `${model} (open-weight) via ${via}`;
}
