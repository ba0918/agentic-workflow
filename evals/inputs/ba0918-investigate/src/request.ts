import { sign } from "./signing.ts";

export interface SignedRequest {
  url: string;
  path: string;
  headers: Record<string, string>;
}

export function buildRequest(path: string, base: string, secret: string): SignedRequest {
  const url = new URL(path, base);
  return {
    url: url.toString(),
    path: url.pathname,
    headers: { "X-Signature": sign(path, secret) },
  };
}
