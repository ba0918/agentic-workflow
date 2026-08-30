import { test } from "node:test";
import assert from "node:assert/strict";
import { canonicalPath, sign } from "../src/signing.ts";
import { buildRequest } from "../src/request.ts";

test("a plain path is its own canonical path", () => {
  assert.equal(canonicalPath("/v1/items"), "/v1/items");
});

test("the same path and secret always give the same signature", () => {
  assert.equal(sign("/v1/items", "test-secret"), sign("/v1/items", "test-secret"));
});

test("a different path gives a different signature", () => {
  assert.notEqual(sign("/v1/items", "test-secret"), sign("/v1/orders", "test-secret"));
});

test("the request carries the signature of its path", () => {
  const request = buildRequest("/v1/items", "https://api.example", "test-secret");
  assert.equal(request.path, "/v1/items");
  assert.equal(request.headers["X-Signature"], sign("/v1/items", "test-secret"));
});
