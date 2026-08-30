import { createHmac } from "node:crypto";

export function canonicalPath(path: string): string {
  return encodeURI(path);
}

export function sign(path: string, secret: string): string {
  return createHmac("sha256", secret).update(canonicalPath(path)).digest("hex");
}
