import { test } from "node:test";
import assert from "node:assert/strict";
import { withRetry } from "../src/retry.ts";

function sequence(statuses: number[]) {
  let calls = 0;
  const send = async () => ({ status: statuses[Math.min(calls++, statuses.length - 1)] });
  return { send, calls: () => calls };
}

test("429 is retried and the later success is returned", async () => {
  const s = sequence([429, 200]);
  assert.equal((await withRetry(s.send)).status, 200);
  assert.equal(s.calls(), 2);
});

test("503 is retried and the later success is returned", async () => {
  const s = sequence([503, 503, 200]);
  assert.equal((await withRetry(s.send)).status, 200);
  assert.equal(s.calls(), 3);
});

test("500 is returned without a retry", async () => {
  const s = sequence([500, 200]);
  assert.equal((await withRetry(s.send)).status, 500);
  assert.equal(s.calls(), 1);
});

test("a persistent 429 stops after three attempts in total", async () => {
  const s = sequence([429]);
  assert.equal((await withRetry(s.send)).status, 429);
  assert.equal(s.calls(), 3);
});
