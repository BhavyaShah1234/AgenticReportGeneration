import { FileBarChart2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2 font-semibold tracking-tight text-zinc-900", className)}>
      <span className="flex size-7 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-sm">
        <FileBarChart2 className="size-4" />
      </span>
      Agentic Reports
    </span>
  );
}
