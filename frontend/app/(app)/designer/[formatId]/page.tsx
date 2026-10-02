import type { Metadata } from "next";
import { DesignerApp } from "@/components/designer/DesignerApp";

export const metadata: Metadata = { title: "Designer" };

export default async function DesignerPage({ params }: { params: Promise<{ formatId: string }> }) {
  const { formatId } = await params;
  return <DesignerApp formatId={formatId} />;
}
