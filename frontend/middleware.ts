import { NextRequest, NextResponse } from "next/server";

const PROTECTED_PATHS = ["/dashboard", "/opportunities", "/signals", "/workflow", "/rag", "/reports"];
const AUTH_PATHS = ["/login", "/register"];
const TOKEN_COOKIE = "mg_auth_token";

function isProtectedPath(pathname: string) {
  return PROTECTED_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get(TOKEN_COOKIE)?.value;

  if (!token && isProtectedPath(pathname)) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  if (token && AUTH_PATHS.includes(pathname)) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard",
    "/dashboard/:path*",
    "/opportunities",
    "/opportunities/:path*",
    "/signals",
    "/signals/:path*",
    "/workflow",
    "/workflow/:path*",
    "/rag",
    "/reports",
    "/reports/:path*",
    "/login",
    "/register",
  ],
};
