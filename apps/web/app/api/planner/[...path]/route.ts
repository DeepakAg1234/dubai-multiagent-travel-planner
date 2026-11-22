import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

const HOP = new Set(["host", "connection", "content-length"]);

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const base = (process.env.PLANNER_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
  const target = new URL(`${base}/${path.join("/")}`);
  target.search = request.nextUrl.search;
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP.has(key.toLowerCase())) headers.set(key, value);
  });
  const init: RequestInit = { method: request.method, headers, cache: "no-store" };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }
  const upstream = await fetch(target, init);
  const outgoing = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP.has(key.toLowerCase())) outgoing.set(key, value);
  });
  return new Response(upstream.body, { status: upstream.status, headers: outgoing });
}

export const GET = proxy;
export const POST = proxy;
