import { type NextRequest, NextResponse } from 'next/server'

// Route protection lives in <AuthGuard /> (client-side Supabase session check).
// Kept as a passthrough so static-asset matching stays in one place.
export async function middleware(_request: NextRequest) {
  return NextResponse.next()
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
