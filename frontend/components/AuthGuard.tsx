"use client";

import React, { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { getSupabase } from "@/lib/supabase";

/**
 * Wraps the authenticated app routes. Unauthenticated visitors are sent to
 * /login; the login page itself is excluded so it can render.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(pathname === "/login");

  useEffect(() => {
    if (pathname === "/login") {
      setChecked(true);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const { data } = await getSupabase().auth.getSession();
        if (!data.session && !cancelled) {
          router.replace("/login");
          return;
        }
      } catch {
        if (!cancelled) router.replace("/login");
        return;
      }
      if (!cancelled) setChecked(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  if (!checked) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-slate-500" />
      </div>
    );
  }

  return <>{children}</>;
}
