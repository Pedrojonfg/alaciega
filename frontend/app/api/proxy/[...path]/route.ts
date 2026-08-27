import { NextRequest, NextResponse } from "next/server";
import { authorize, upstream } from "../../../../lib/proxy";

async function forward(req: NextRequest, path: string[]) {
  const api = process.env.API_URL ?? "http://127.0.0.1:8000";
  const headers = new Headers();
  authorize(headers, process.env.API_TOKEN ?? "");
  const ct = req.headers.get("content-type");
  if (ct) headers.set("content-type", ct);
  const init: RequestInit = { method: req.method, headers };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }
  const r = await fetch(upstream(api, path), init);
  const body = await r.text();
  return new NextResponse(body, {
    status: r.status,
    headers: { "content-type": r.headers.get("content-type") ?? "application/json" },
  });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, (await ctx.params).path);
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, (await ctx.params).path);
}

export async function DELETE(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, (await ctx.params).path);
}
