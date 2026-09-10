"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { api } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/errors";
import { saveLastJobId } from "@/lib/storage";
import { EvidenceCard } from "@/components/EvidenceCard";
import { Spinner } from "@/components/Spinner";
import type { AnalysisJob, JobStatus } from "@/lib/api/types";
import styles from "./job.module.css";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES: JobStatus[] = ["done", "failed"];

const STATUS_LABEL: Record<JobStatus, string> = {
  pending: "Pending",
  running: "Running",
  done: "Done",
  failed: "Failed",
};

const STATUS_BADGE_CLASS: Record<JobStatus, string> = {
  pending: styles.badgePending,
  running: styles.badgeRunning,
  done: styles.badgeDone,
  failed: styles.badgeFailed,
};

function JobPageInner() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;
  const searchParams = useSearchParams();
  const thesisId = searchParams.get("thesisId");

  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    saveLastJobId(jobId);
  }, [jobId]);

  useEffect(() => {
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const result = await api.getJob(jobId);
        if (cancelled) return;
        setJob(result);
        setError(null);
        if (!TERMINAL_STATUSES.includes(result.status)) {
          timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setError(errorMessage(err));
      }
    }

    poll();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [jobId, refreshKey]);

  const progressPct = job && job.total_claims > 0 ? Math.round((job.progress / job.total_claims) * 100) : 0;

  return (
    <div>
      <div className={styles.header}>
        {thesisId && (
          <Link className={styles.backLink} href={`/theses/${thesisId}/claims`}>
            &larr; Back to claim review
          </Link>
        )}
        <h1 className={styles.title}>Analysis results</h1>
      </div>

      {process.env.NODE_ENV === "development" && (
        <div className="noticeBanner" style={{ marginBottom: "1.25rem" }}>
          Dev note: evidence quality below depends on whether the backend is
          running in mock or real analysis mode — check with whoever's running
          it if a result looks off.
        </div>
      )}

      {error && (
        <div className="errorBanner" role="alert" style={{ marginBottom: "1.25rem" }}>
          <p>Could not load this job: {error}</p>
          <button
            type="button"
            className="button buttonSecondary"
            style={{ marginTop: "0.6rem" }}
            onClick={() => setRefreshKey((key) => key + 1)}
          >
            Retry
          </button>
        </div>
      )}

      {!job && !error && <Spinner size="lg" label="Loading analysis job…" />}

      {job && (
        <>
          <div className={styles.statusRow}>
            <span className={`${styles.badge} ${STATUS_BADGE_CLASS[job.status]}`}>
              {STATUS_LABEL[job.status]}
            </span>
            <span className={styles.progressText}>
              {job.progress} / {job.total_claims} claims processed
            </span>
          </div>
          <div className={styles.progressTrack}>
            <div className={styles.progressFill} style={{ width: `${progressPct}%` }} />
          </div>

          {job.status === "failed" && job.error && (
            <div className="errorBanner" role="alert" style={{ marginBottom: "1.25rem" }}>
              {job.error}
            </div>
          )}

          {!TERMINAL_STATUSES.includes(job.status) && job.results.length === 0 && (
            <Spinner label="Waiting for the first result… checking every 2 seconds." />
          )}

          {job.results.length > 0 && (
            <ul className={styles.resultList}>
              {job.results.map((result) => (
                <li key={result.evidence.id}>
                  <EvidenceCard claim={result.claim} evidence={result.evidence} />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

export default function JobPage() {
  return (
    <Suspense fallback={<Spinner size="lg" label="Loading analysis job…" />}>
      <JobPageInner />
    </Suspense>
  );
}
