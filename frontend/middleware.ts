import { type NextRequest, NextResponse } from 'next/server'

// Auth removed for the demo: no Supabase session check on any route.
export async function middleware(_request: NextRequest) {
  return NextResponse.next()
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
