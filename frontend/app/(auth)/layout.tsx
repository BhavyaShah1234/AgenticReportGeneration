import { Logo } from "@/components/layout/Logo";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-1 flex-col items-center justify-center bg-gradient-to-b from-indigo-50/60 via-zinc-50 to-zinc-50 px-4 py-12">
      <Logo className="mb-8 text-lg" />
      <div className="w-full max-w-md">{children}</div>
      <p className="mt-8 text-xs text-zinc-400">Reports over your Snowflake data, designed once and generated per client.</p>
    </div>
  );
}
