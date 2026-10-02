import type { Metadata } from "next";
import { PrintReport } from "@/components/print/PrintReport";

export const metadata: Metadata = { title: "Report", robots: { index: false } };

// Chrome-less page rendered by the backend's headless Chromium to produce the PDF.
// Authenticates with a short-lived signed `token` query param instead of the session cookie.
export default async function PrintPage({
  params,
  searchParams,
}: {
  params: Promise<{ runId: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { runId } = await params;
  const sp = await searchParams;
  const token = typeof sp.token === "string" ? sp.token : null;
  return <PrintReport runId={runId} token={token} />;
}
