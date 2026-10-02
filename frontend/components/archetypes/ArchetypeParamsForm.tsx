"use client";

// JSON-schema-driven params form for an archetype (pydantic `model_json_schema()` output).
import { clsx } from "clsx";
import { X } from "lucide-react";
import { useId } from "react";
import type { ArchetypeSpec, ColumnInfo, ColumnType } from "@/lib/types";

export interface ArchetypeParamsFormProps {
  spec: ArchetypeSpec;
  /** Columns of the widget's data source, used for column pickers */
  columns: ColumnInfo[];
  value: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
}

type Schema = {
  type?: string | string[];
  title?: string;
  description?: string;
  default?: unknown;
  enum?: unknown[];
  const?: unknown;
  anyOf?: Schema[];
  oneOf?: Schema[];
  allOf?: Schema[];
  items?: Schema;
  $ref?: string;
  properties?: Record<string, Schema>;
  required?: string[];
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  minItems?: number;
  maxItems?: number;
  examples?: unknown[];
  $defs?: Record<string, Schema>;
  definitions?: Record<string, Schema>;
};

interface Field {
  name: string;
  label: string;
  description?: string;
  /** resolved non-null schema */
  schema: Schema;
  nullable: boolean;
  required: boolean;
  defaultValue: unknown;
}

function resolveRef(s: Schema, root: Schema, depth = 0): Schema {
  if (!s || depth > 8) return s ?? {};
  if (s.$ref) {
    const m = /^#\/(\$defs|definitions)\/(.+)$/.exec(s.$ref);
    const target = m ? (root[m[1] as "$defs" | "definitions"] ?? {})[m[2]] : undefined;
    const { $ref: _ignored, ...rest } = s;
    void _ignored;
    return resolveRef({ ...(target ?? {}), ...rest }, root, depth + 1);
  }
  if (s.allOf?.length === 1) {
    const { allOf, ...rest } = s;
    return resolveRef({ ...allOf[0], ...rest }, root, depth + 1);
  }
  return s;
}

function toField(name: string, raw: Schema, root: Schema, required: boolean): Field {
  let s = resolveRef(raw, root);
  let nullable = false;
  const variants = s.anyOf ?? s.oneOf;
  if (variants) {
    const resolved = variants.map((v) => resolveRef(v, root));
    const nonNull = resolved.filter((v) => v.type !== "null");
    nullable = nonNull.length < resolved.length;
    const { anyOf: _a, oneOf: _o, ...rest } = s;
    void _a;
    void _o;
    s = { ...(nonNull[0] ?? {}), ...rest };
  }
  if (Array.isArray(s.type)) {
    nullable = nullable || s.type.includes("null");
    s = { ...s, type: s.type.find((t) => t !== "null") };
  }
  return {
    name,
    label: s.title ?? name.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()),
    description: s.description,
    schema: s,
    nullable,
    required,
    defaultValue: s.default,
  };
}

const COLUMN_NAME = /(^|_)(column|columns|dimension|dimensions|measure|measures|series)$/i;

type ColumnRole = "measure" | "date" | "any";

function columnRole(name: string): ColumnRole | null {
  if (!COLUMN_NAME.test(name) && name !== "series") return null;
  if (/measure/i.test(name)) return "measure";
  if (/date/i.test(name)) return "date";
  return "any";
}

function rankColumns(columns: ColumnInfo[], role: ColumnRole): { preferred: ColumnInfo[]; other: ColumnInfo[] } {
  const want: ColumnType | null = role === "measure" ? "number" : role === "date" ? "date" : null;
  if (!want) return { preferred: columns, other: [] };
  return { preferred: columns.filter((c) => c.type === want), other: columns.filter((c) => c.type !== want) };
}

const TYPE_HINT: Record<ColumnType, string> = { number: "#", date: "date", string: "abc" };

const inputCls =
  "w-full rounded-md border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-900 shadow-xs outline-none " +
  "focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 disabled:bg-zinc-50";

function ColumnOptions({ columns, role }: { columns: ColumnInfo[]; role: ColumnRole }) {
  const { preferred, other } = rankColumns(columns, role);
  const opt = (c: ColumnInfo) => (
    <option key={c.name} value={c.name}>
      {c.name} ({TYPE_HINT[c.type]})
    </option>
  );
  if (!other.length) return <>{preferred.map(opt)}</>;
  return (
    <>
      <optgroup label={role === "measure" ? "Numeric columns" : "Date columns"}>{preferred.map(opt)}</optgroup>
      <optgroup label="Other columns">{other.map(opt)}</optgroup>
    </>
  );
}

function ColumnSelect({
  id,
  value,
  columns,
  role,
  allowEmpty,
  onChange,
}: {
  id: string;
  value: unknown;
  columns: ColumnInfo[];
  role: ColumnRole;
  allowEmpty: boolean;
  onChange: (v: string | null) => void;
}) {
  const v = typeof value === "string" ? value : "";
  const known = columns.some((c) => c.name === v);
  return (
    <select id={id} className={inputCls} value={v} onChange={(e) => onChange(e.target.value || null)}>
      {(allowEmpty || !v) && <option value="">{allowEmpty ? "— none —" : "Select a column…"}</option>}
      {v && !known && <option value={v}>{v} (not in table)</option>}
      <ColumnOptions columns={columns} role={role} />
    </select>
  );
}

function MultiColumnSelect({
  id,
  value,
  columns,
  max,
  onChange,
}: {
  id: string;
  value: unknown;
  columns: ColumnInfo[];
  max?: number;
  onChange: (v: string[]) => void;
}) {
  const selected = Array.isArray(value) ? value.map(String) : [];
  const remaining = columns.filter((c) => !selected.includes(c.name));
  const full = max !== undefined && selected.length >= max;
  return (
    <div className="space-y-1.5">
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {selected.map((s, i) => (
            <span
              key={s}
              className="inline-flex items-center gap-1 rounded-md bg-indigo-50 px-1.5 py-0.5 text-[11px] font-medium text-indigo-700"
            >
              {i > 0 && <span className="text-indigo-400">then</span>}
              {s}
              <button
                type="button"
                className="rounded text-indigo-400 hover:text-indigo-700"
                aria-label={`Remove ${s}`}
                onClick={() => onChange(selected.filter((x) => x !== s))}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      {!full && (
        <select
          id={id}
          className={inputCls}
          value=""
          onChange={(e) => e.target.value && onChange([...selected, e.target.value])}
        >
          <option value="">{selected.length ? "Add another column…" : "Select a column…"}</option>
          <ColumnOptions columns={remaining} role="any" />
        </select>
      )}
    </div>
  );
}

function FieldControl({
  field,
  value,
  columns,
  set,
}: {
  field: Field;
  value: unknown;
  columns: ColumnInfo[];
  set: (v: unknown) => void;
}) {
  const id = useId();
  const s = field.schema;
  const role = columnRole(field.name);
  const current = value === undefined ? field.defaultValue : value;
  const optional = field.nullable || !field.required;

  let control: React.ReactNode;
  if (s.enum) {
    control = (
      <select
        id={id}
        className={inputCls}
        value={current === null || current === undefined ? "" : String(current)}
        onChange={(e) => {
          const raw = e.target.value;
          if (!raw) return set(null);
          const match = s.enum!.find((x) => String(x) === raw);
          set(match ?? raw);
        }}
      >
        {(optional || current === undefined) && <option value="">{optional ? "— none —" : "Select…"}</option>}
        {s.enum.map((opt) => (
          <option key={String(opt)} value={String(opt)}>
            {String(opt).replace(/_/g, " ")}
          </option>
        ))}
      </select>
    );
  } else if (s.type === "boolean") {
    return (
      <label htmlFor={id} className="flex cursor-pointer items-center gap-2 py-0.5 text-xs text-zinc-700" title={field.description}>
        <input
          id={id}
          type="checkbox"
          className="h-3.5 w-3.5 rounded border-zinc-300 accent-indigo-600"
          checked={current === true}
          onChange={(e) => set(e.target.checked)}
        />
        {field.label}
      </label>
    );
  } else if (s.type === "integer" || s.type === "number") {
    control = (
      <input
        id={id}
        type="number"
        className={inputCls}
        step={s.type === "integer" ? 1 : "any"}
        min={s.minimum ?? (s.exclusiveMinimum !== undefined ? s.exclusiveMinimum + (s.type === "integer" ? 1 : 0) : undefined)}
        max={s.maximum}
        placeholder={optional ? "Any" : undefined}
        value={current === null || current === undefined ? "" : String(current)}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === "") return set(optional ? null : undefined);
          const n = s.type === "integer" ? parseInt(raw, 10) : parseFloat(raw);
          if (!Number.isNaN(n)) set(n);
        }}
      />
    );
  } else if (s.type === "array") {
    const itemSchema = s.items ? s.items : {};
    if ((itemSchema.type === "string" || !itemSchema.type) && columns.length && (role || !itemSchema.enum)) {
      control = (
        <MultiColumnSelect id={id} value={current} columns={columns} max={s.maxItems} onChange={(v) => set(v)} />
      );
    } else {
      control = (
        <input
          id={id}
          className={inputCls}
          placeholder="Comma-separated"
          value={Array.isArray(current) ? current.join(", ") : ""}
          onChange={(e) =>
            set(
              e.target.value
                .split(",")
                .map((x) => x.trim())
                .filter(Boolean),
            )
          }
        />
      );
    }
  } else if (s.type === "string" && role && columns.length) {
    control = (
      <ColumnSelect
        id={id}
        value={current}
        columns={columns}
        role={role}
        allowEmpty={optional}
        onChange={(v) => set(v === null ? (optional ? null : undefined) : v)}
      />
    );
  } else if (s.type === "object") {
    control = (
      <textarea
        id={id}
        className={clsx(inputCls, "h-20 font-mono")}
        defaultValue={current ? JSON.stringify(current, null, 2) : ""}
        onBlur={(e) => {
          try {
            set(e.target.value.trim() ? JSON.parse(e.target.value) : null);
          } catch {
            /* keep previous value on invalid JSON */
          }
        }}
      />
    );
  } else {
    const example = s.examples?.[0];
    control = (
      <input
        id={id}
        className={inputCls}
        placeholder={example !== undefined ? `e.g. ${String(example)}` : undefined}
        value={current === null || current === undefined ? "" : String(current)}
        onChange={(e) => set(e.target.value === "" ? (optional ? null : undefined) : e.target.value)}
      />
    );
  }

  return (
    <div className="space-y-1">
      <label htmlFor={id} className="flex items-baseline gap-1 text-[11px] font-medium text-zinc-600">
        {field.label}
        {field.required && !field.nullable && <span className="text-red-500" aria-label="required">*</span>}
      </label>
      {control}
      {field.description && <p className="text-[10.5px] leading-snug text-zinc-400">{field.description}</p>}
    </div>
  );
}

/** Compact form for an inspector panel. Untouched fields show schema defaults without writing them. */
export function ArchetypeParamsForm({ spec, columns, value, onChange }: ArchetypeParamsFormProps) {
  const root = (spec.params_schema ?? {}) as Schema;
  const resolvedRoot = resolveRef(root, root);
  const props = resolvedRoot.properties ?? {};
  const required = new Set(resolvedRoot.required ?? []);
  const fields = Object.entries(props).map(([name, s]) => toField(name, s, root, required.has(name)));

  if (!fields.length) {
    return (
      <p className="rounded-md bg-zinc-50 px-2.5 py-2 text-xs text-zinc-500">
        This archetype has no parameters. Report-level filters still apply.
      </p>
    );
  }

  const set = (name: string, v: unknown) => {
    const next = { ...value };
    if (v === undefined) delete next[name];
    else next[name] = v;
    onChange(next);
  };

  return (
    <div className="space-y-3">
      {fields.map((f) => (
        <FieldControl key={f.name} field={f} value={value?.[f.name]} columns={columns} set={(v) => set(f.name, v)} />
      ))}
    </div>
  );
}
