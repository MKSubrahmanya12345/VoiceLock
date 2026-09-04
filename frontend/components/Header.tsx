"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Shield, Github, Menu, X, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useEffect, useState } from "react";
import { getSupabase } from "@/lib/supabase";

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  // Close mobile menu when route changes
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  // Track signed-in user for the header account area.
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const { data } = await getSupabase().auth.getSession();
        if (mounted) setUserEmail(data.session?.user?.email ?? null);
      } catch {
        if (mounted) setUserEmail(null);
      }
    })();
    let subscription: { unsubscribe: () => void } | null = null;
    try {
      const { data } = getSupabase().auth.onAuthStateChange((_event, session) => {
        if (mounted) setUserEmail(session?.user?.email ?? null);
      });
      subscription = data.subscription;
    } catch {
      // Supabase not configured - header simply shows signed-out state.
    }
    return () => {
      mounted = false;
      subscription?.unsubscribe();
    };
  }, [pathname]);

  const handleSignOut = async () => {
    try {
      await getSupabase().auth.signOut();
    } finally {
      setUserEmail(null);
      router.push("/login");
    }
  };

  const routes = [
    { href: "/", label: "Home", active: pathname === "/" },
    { href: "/enrollment", label: "Enrollment", active: pathname === "/enrollment" },
    { href: "/call", label: "Call Simulation", active: pathname === "/call" },
    { href: "/dashboard", label: "Agent Dashboard", active: pathname === "/dashboard" },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md supports-[backdrop-filter]:bg-slate-950/60">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        
        {/* --- LEFT SIDE CONTAINER --- */}
        <div className="flex items-center gap-4">
            {/* MOVED: Mobile Hamburger Button is now FIRST. 
               It is hidden on desktop (md:hidden).
            */}
            <Button
                variant="ghost"
                size="icon"
                // Added '-ml-2' to pull it slightly left to align with container padding
                className="md:hidden text-slate-300 hover:bg-slate-800 -ml-2 mr-2"
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            >
                {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </Button>

            {/* Logo */}
            <Link href="/" className="flex items-center space-x-2 group shrink-0">
                <div className="p-1.5 bg-blue-500/10 rounded-lg group-hover:bg-blue-500/20 transition-colors">
                <Shield className="h-5 w-5 text-blue-500" />
                </div>
                <span className="font-bold text-lg tracking-tight text-white">
                CallShield
                </span>
            </Link>

            {/* Desktop Navigation (Hidden on Mobile) */}
            <nav className="hidden md:flex items-center space-x-6 text-sm font-medium ml-4">
                {routes.map((route) => (
                <Link
                    key={route.href}
                    href={route.href}
                    className={cn(
                    "transition-colors duration-200",
                    route.active 
                        ? "text-blue-400 font-semibold" 
                        : "text-slate-400 hover:text-white"
                    )}
                >
                    {route.label}
                </Link>
                ))}
            </nav>
        </div>

        {/* --- RIGHT SIDE: Actions --- */}
        <div className="flex items-center gap-4">
          
          {/* Desktop GitHub (Hidden on Mobile) */}
          <Button 
              asChild 
              variant="ghost" 
              size="sm" 
              className="text-slate-400 hover:text-white hover:bg-slate-800 hidden md:flex"
            >
              <Link
                href="https://github.com/shreyk2/CallShield"
                target="_blank"
                rel="noreferrer"
                className="gap-2"
              >
                <Github className="w-4 h-4" />
                GitHub
              </Link>
          </Button>
            
          {/* User / Login Actions (Visible on both mobile and desktop now) */}
          <div className="flex items-center gap-2 pl-3 border-l border-slate-800">
            {userEmail ? (
              <>
                <span className="text-xs font-medium text-slate-300 max-w-40 truncate hidden sm:inline">
                  {userEmail}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleSignOut}
                  className="text-slate-400 hover:text-white hover:bg-slate-800 gap-2"
                >
                  <LogOut className="w-4 h-4" />
                  <span className="hidden sm:inline">Sign out</span>
                </Button>
              </>
            ) : (
              <Button asChild variant="ghost" size="sm" className="text-slate-300 hover:text-white hover:bg-slate-800">
                <Link href="/login">Sign in</Link>
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* --- Mobile Dropdown Menu --- */}
      {isMobileMenuOpen && (
        <div className="md:hidden border-t border-slate-800 bg-slate-950 absolute w-full left-0 animate-in slide-in-from-top-5 fade-in duration-200 shadow-2xl z-50">
          <div className="flex flex-col p-4 space-y-4">
            
            {/* Mobile Navigation Links */}
            {routes.map((route) => (
              <Link
                key={route.href}
                href={route.href}
                onClick={() => setIsMobileMenuOpen(false)}
                className={cn(
                  "px-4 py-3 rounded-lg text-sm font-medium transition-colors",
                  route.active 
                    ? "bg-blue-500/10 text-blue-400" 
                    : "text-slate-400 hover:text-white hover:bg-slate-900"
                )}
              >
                {route.label}
              </Link>
            ))}
            
            <div className="h-px bg-slate-800 my-2" />

            <Link
              href="https://github.com/shreyk2/CallShield"
              target="_blank"
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-900 rounded-lg"
            >
              <Github className="w-4 h-4" />
              GitHub Repo
            </Link>
            

          </div>
        </div>
      )}
    </header>
  );
}