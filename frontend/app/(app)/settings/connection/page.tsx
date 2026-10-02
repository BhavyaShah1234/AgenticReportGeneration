import type { Metadata } from "next";
import { ConnectionSettings } from "@/components/settings/ConnectionSettings";

export const metadata: Metadata = { title: "Snowflake connection" };

export default function ConnectionPage() {
  return <ConnectionSettings />;
}
