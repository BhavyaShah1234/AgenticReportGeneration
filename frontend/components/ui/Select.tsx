import { forwardRef, type SelectHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { inputClass } from "./Input";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "onChange"> {
  options?: SelectOption[];
  placeholder?: string;
  onValueChange?: (v: string) => void;
  onChange?: SelectHTMLAttributes<HTMLSelectElement>["onChange"];
  selectSize?: "sm" | "md";
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, options, placeholder, onValueChange, onChange, children, selectSize = "md", ...props },
  ref,
) {
  return (
    <div className={cn("relative w-full", className)}>
      <select
        ref={ref}
        className={cn(inputClass, "appearance-none pr-8", selectSize === "sm" ? "h-8 text-xs" : "h-9")}
        onChange={(e) => {
          onChange?.(e);
          onValueChange?.(e.target.value);
        }}
        {...props}
      >
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options?.map((o) => (
          <option key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
          </option>
        ))}
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-zinc-400" />
    </div>
  );
});
