export interface Response {
  status: number;
}

export const RETRYABLE_STATUSES: ReadonlySet<number> = new Set([429, 503]);
export const MAX_RETRIES = 2;

export async function withRetry(send: () => Promise<Response>): Promise<Response> {
  let response = await send();
  for (let retry = 0; retry < MAX_RETRIES && RETRYABLE_STATUSES.has(response.status); retry++) {
    response = await send();
  }
  return response;
}
