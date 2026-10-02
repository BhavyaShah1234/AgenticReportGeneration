import type { Metadata } from "next";
import { GenerateApp } from "@/components/generate/GenerateApp";

export const metadata: Metadata = { title: "Generate report" };

export default async function GeneratePage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const sp = await searchParams;
  const format = typeof sp.format === "string" ? sp.format : null;
  return <GenerateApp initialFormatId={format} />;
}
