"use client";

import { buildApiUrl, ensureApiMocksReady } from "./api-runtime";

type ApiErrorPayload = {
  error?: {
    message?: string;
  };
};

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function fetchApiJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  await ensureApiMocksReady();

  const response = await fetch(buildApiUrl(path), {
    ...init,
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;

    try {
      const payload = (await response.json()) as ApiErrorPayload;
      if (payload.error?.message) {
        message = payload.error.message;
      }
    } catch {
      // Keep the generic error when the server body is not JSON.
    }

    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}
