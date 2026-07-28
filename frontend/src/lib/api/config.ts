const DEFAULT_API_BASE_URL = "http://localhost:8000/api";

const rawBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL;

export const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");
