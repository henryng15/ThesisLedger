import type { ApiErrorCode } from "./types";

// Thrown for every non-2xx response so callers can branch on `code`/`field`
// instead of re-parsing the backend's error envelope each time.
export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode | string;
  readonly field: string | null;

  constructor(status: number, code: ApiErrorCode | string, message: string, field: string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.field = field;
  }
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}
