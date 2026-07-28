// Client-only convenience so the "Results" nav link can resume the most
// recent analysis job. The backend has no job-listing endpoint, so this is
// a browser-local shortcut, not a real history feature.
const LAST_JOB_ID_KEY = "thesisledger:lastJobId";

export function saveLastJobId(jobId: string): void {
  window.localStorage.setItem(LAST_JOB_ID_KEY, jobId);
}

export function getLastJobId(): string | null {
  return window.localStorage.getItem(LAST_JOB_ID_KEY);
}
