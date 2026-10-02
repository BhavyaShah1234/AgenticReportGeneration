import { cookies } from "next/headers";
import { redirect } from "next/navigation";

// Landing: send signed-in users to the dashboard, everyone else to login.
// (The (app) layout re-validates the session against /api/auth/me.)
export default async function Home() {
  const jar = await cookies();
  redirect(jar.get("session") ? "/dashboard" : "/login");
}
