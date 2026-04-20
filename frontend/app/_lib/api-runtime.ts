const DEFAULT_API_BASE_URL = "";

export const apiMocksEnabled =
  process.env.NODE_ENV !== "production" &&
  process.env.NEXT_PUBLIC_ENABLE_API_MOCKS === "true";

let apiMockStartup: Promise<void> | null = null;

export function getApiBaseUrl() {
  const configuredBaseUrl = process.env.NEXT_PUBLIC_FUNDING_API_BASE_URL?.trim();

  return configuredBaseUrl ? configuredBaseUrl.replace(/\/$/, "") : DEFAULT_API_BASE_URL;
}

export function buildApiUrl(path: string) {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  return `${getApiBaseUrl()}${path}`;
}

export async function ensureApiMocksReady() {
  if (!apiMocksEnabled || typeof window === "undefined") {
    return;
  }

  if (!apiMockStartup) {
    apiMockStartup = import("../../mocks/browser")
      .then(async ({ worker }) => {
        await worker.start({
          onUnhandledRequest: "error",
        });
      })
      .catch((error: unknown) => {
        apiMockStartup = null;

        throw new Error(
          error instanceof Error
            ? `Failed to start FundingPulse API mocks: ${error.message}`
            : "Failed to start FundingPulse API mocks.",
        );
      });
  }

  await apiMockStartup;
}
