"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronsUpDown, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { inputClass } from "./Input";
import { Spinner } from "./Spinner";

/** Searchable single-select over a list of strings. */
export function Combobox({
  value,
  onChange,
  options,
  placeholder = "Select…",
  loading,
  clearable = true,
  size = "md",
  className,
  emptyLabel = "No matches",
}: {
  value: string | null | undefined;
  onChange: (v: string | null) => void;
  options: string[];
  placeholder?: string;
  loading?: boolean;
  clearable?: boolean;
  size?: "sm" | "md";
  className?: string;
  emptyLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q ? options.filter((o) => o.toLowerCase().includes(q)) : options;
    return list.slice(0, 300);
  }, [options, query]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const choose = (v: string) => {
    onChange(v);
    setOpen(false);
    setQuery("");
  };

  return (
    <div ref={rootRef} className={cn("relative w-full", className)}>
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o);
          setActive(0);
          setTimeout(() => searchRef.current?.focus(), 0);
        }}
        className={cn(
          inputClass,
          "flex items-center justify-between gap-2 text-left",
          size === "sm" ? "h-8 text-xs" : "h-9",
        )}
      >
        <span className={cn("truncate", !value && "text-zinc-400")}>{value || placeholder}</span>
        <span className="flex items-center gap-1 text-zinc-400">
          {loading && <Spinner className="size-3.5" />}
          {clearable && value ? (
            <span
              role="button"
              tabIndex={-1}
              aria-label="Clear"
              onClick={(e) => {
                e.stopPropagation();
                onChange(null);
              }}
              className="rounded p-0.5 hover:bg-zinc-100 hover:text-zinc-700"
            >
              <X className="size-3.5" />
            </span>
          ) : null}
          <ChevronsUpDown className="size-3.5" />
        </span>
      </button>
      {open && (
        <div className="absolute z-40 mt-1 w-full min-w-56 overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-lg">
          <div className="flex items-center gap-2 border-b border-zinc-100 px-2.5">
            <Search className="size-3.5 text-zinc-400" />
            <input
              ref={searchRef}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setActive(0);
              }}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  setActive((a) => Math.min(a + 1, filtered.length - 1));
                } else if (e.key === "ArrowUp") {
                  e.preventDefault();
                  setActive((a) => Math.max(a - 1, 0));
                } else if (e.key === "Enter") {
                  e.preventDefault();
                  if (filtered[active]) choose(filtered[active]);
                } else if (e.key === "Escape") {
                  setOpen(false);
                }
              }}
              placeholder="Search…"
              className="h-9 w-full bg-transparent text-sm outline-none placeholder:text-zinc-400"
            />
          </div>
          <ul className="max-h-64 overflow-y-auto py-1">
            {filtered.length === 0 && (
              <li className="px-3 py-2 text-sm text-zinc-500">{loading ? "Loading…" : emptyLabel}</li>
            )}
            {filtered.map((o, i) => (
              <li key={o}>
                <button
                  type="button"
                  onMouseEnter={() => setActive(i)}
                  onClick={() => choose(o)}
                  className={cn(
                    "flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm",
                    i === active ? "bg-indigo-50 text-indigo-900" : "text-zinc-700",
                  )}
                >
                  <span className="truncate">{o}</span>
                  {o === value && <Check className="size-3.5 text-indigo-600" />}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
