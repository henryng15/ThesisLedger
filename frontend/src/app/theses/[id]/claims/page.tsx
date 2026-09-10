"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/errors";
import { saveLastJobId } from "@/lib/storage";
import { Spinner } from "@/components/Spinner";
import type { Claim, Thesis } from "@/lib/api/types";
import styles from "./claims.module.css";

const MAX_CLAIM_LENGTH = 2000;

export default function ClaimReviewPage() {
  const params = useParams<{ id: string }>();
  const thesisId = params.id;
  const router = useRouter();

  const [thesis, setThesis] = useState<Thesis | null>(null);
  const [loading, setLoading] = useState(true);
  const [awaitingClaims, setAwaitingClaims] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [savingEditId, setSavingEditId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const [reloadKey, setReloadKey] = useState(0);

  function retryLoadThesis() {
    setLoading(true);
    setLoadError(null);
    setReloadKey((key) => key + 1);
  }

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    // Claim extraction runs in a worker, so the thesis arrives as `draft` with
    // no claims and fills in a minute or two later. Poll until it does.
    async function loadThesis() {
      try {
        const loaded = await api.getThesis(thesisId);
        if (cancelled) return;
        setThesis(loaded);
        setSelectedIds(new Set(loaded.claims.filter((c) => c.is_approved).map((c) => c.id)));

        if (loaded.status === "draft" && loaded.claims.length === 0) {
          setAwaitingClaims(true);
          timer = setTimeout(loadThesis, 3000);
          return;
        }
        setAwaitingClaims(false);
      } catch (err) {
        if (cancelled) return;
        setLoadError(errorMessage(err));
      }
      if (!cancelled) setLoading(false);
    }

    loadThesis();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [thesisId, reloadKey]);

  const approvedCount = useMemo(
    () => thesis?.claims.filter((c) => c.is_approved).length ?? 0,
    [thesis],
  );

  function toggleSelected(claimId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(claimId)) {
        next.delete(claimId);
      } else {
        next.add(claimId);
      }
      return next;
    });
  }

  function toggleSelectAll() {
    if (!thesis) return;
    setSelectedIds((prev) =>
      prev.size === thesis.claims.length ? new Set() : new Set(thesis.claims.map((c) => c.id)),
    );
  }

  function startEdit(claim: Claim) {
    setActionError(null);
    setEditingId(claim.id);
    setEditText(claim.text);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditText("");
  }

  async function saveEdit(claimId: string) {
    if (!thesis) return;
    const trimmed = editText.trim();
    if (!trimmed) {
      setActionError("Claim text must not be empty.");
      return;
    }
    if (trimmed.length > MAX_CLAIM_LENGTH) {
      setActionError(`Claim text must be ${MAX_CLAIM_LENGTH} characters or fewer.`);
      return;
    }

    const previousClaims = thesis.claims;
    setActionError(null);
    setSavingEditId(claimId);
    setThesis((prev) =>
      prev
        ? {
            ...prev,
            claims: prev.claims.map((c) =>
              c.id === claimId ? { ...c, text: trimmed, origin: "user" } : c,
            ),
          }
        : prev,
    );

    try {
      const updated = await api.updateClaim(claimId, trimmed);
      setThesis((prev) =>
        prev ? { ...prev, claims: prev.claims.map((c) => (c.id === claimId ? updated : c)) } : prev,
      );
      setEditingId(null);
    } catch (err) {
      setThesis((prev) => (prev ? { ...prev, claims: previousClaims } : prev));
      setActionError(errorMessage(err));
    } finally {
      setSavingEditId(null);
    }
  }

  async function handleDelete(claimId: string) {
    if (!thesis) return;
    const previousClaims = thesis.claims;
    setActionError(null);
    setDeletingId(claimId);
    setThesis((prev) =>
      prev ? { ...prev, claims: prev.claims.filter((c) => c.id !== claimId) } : prev,
    );
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.delete(claimId);
      return next;
    });

    try {
      await api.deleteClaim(claimId);
    } catch (err) {
      setThesis((prev) => (prev ? { ...prev, claims: previousClaims } : prev));
      setActionError(errorMessage(err));
    } finally {
      setDeletingId(null);
    }
  }

  async function handleApprove() {
    if (!thesis) return;
    if (selectedIds.size === 0) {
      setActionError("Select at least one claim to approve.");
      return;
    }

    const previousClaims = thesis.claims;
    const previousStatus = thesis.status;
    const idsToApprove = Array.from(selectedIds);

    setActionError(null);
    setApproving(true);
    setThesis((prev) =>
      prev
        ? {
            ...prev,
            status: "approved",
            claims: prev.claims.map((c) => ({ ...c, is_approved: idsToApprove.includes(c.id) })),
          }
        : prev,
    );

    try {
      const result = await api.approveClaims(thesis.id, idsToApprove);
      setThesis((prev) =>
        prev
          ? {
              ...prev,
              status: result.status,
              claims: prev.claims.map((c) => ({
                ...c,
                is_approved: result.approved_claim_ids.includes(c.id),
              })),
            }
          : prev,
      );
    } catch (err) {
      setThesis((prev) =>
        prev ? { ...prev, claims: previousClaims, status: previousStatus } : prev,
      );
      setActionError(errorMessage(err));
    } finally {
      setApproving(false);
    }
  }

  async function handleAnalyze() {
    if (!thesis) return;
    setActionError(null);
    setAnalyzing(true);
    try {
      const result = await api.analyzeThesis(thesis.id);
      saveLastJobId(result.job_id);
      router.push(`/jobs/${result.job_id}?thesisId=${thesis.id}`);
    } catch (err) {
      setActionError(errorMessage(err));
      setAnalyzing(false);
    }
  }

  if (loading) {
    return (
      <Spinner
        size="lg"
        label={
          awaitingClaims
            ? "Generating claims — this can take a minute or two…"
            : "Loading thesis…"
        }
      />
    );
  }

  if (loadError) {
    return (
      <div>
        <div className="errorBanner" role="alert">
          Could not load this thesis: {loadError}
        </div>
        <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem" }}>
          <button type="button" className="button buttonSecondary" onClick={retryLoadThesis}>
            Retry
          </button>
          <Link href="/" className="button buttonSecondary">
            Start a new analysis
          </Link>
        </div>
      </div>
    );
  }

  if (!thesis) {
    return null;
  }

  const canAnalyze = thesis.status === "approved" && approvedCount > 0 && !analyzing && !approving;

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Review claims</h1>
        <p className={styles.meta}>
          {thesis.company.ticker} &mdash; {thesis.company.name}
        </p>
        <p className={styles.thesisText}>{thesis.text}</p>
        <span
          className={`${styles.statusBadge} ${
            thesis.status === "approved" ? styles.statusApproved : ""
          }`}
        >
          {thesis.status.replace("_", " ")}
        </span>
      </div>

      {actionError && (
        <div className="errorBanner" role="alert" style={{ marginBottom: "1rem" }}>
          {actionError}
        </div>
      )}

      {thesis.claims.length === 0 ? (
        <p className={styles.helpText}>
          No claims were generated for this thesis.{" "}
          <Link href="/">Start a new analysis</Link> to try again.
        </p>
      ) : (
        <>
          <div className={styles.listHeader}>
            <label className={styles.selectAllLabel}>
              <input
                type="checkbox"
                checked={selectedIds.size === thesis.claims.length}
                onChange={toggleSelectAll}
                disabled={approving}
                aria-label="Select all claims"
              />
              Select all
            </label>
            <span className={styles.helpText}>
              {selectedIds.size} of {thesis.claims.length} selected
            </span>
          </div>

          <ul className={styles.claimList}>
            {thesis.claims.map((claim) => {
              const isEditing = editingId === claim.id;
              const isSaving = savingEditId === claim.id;
              const isDeleting = deletingId === claim.id;

              return (
                <li key={claim.id} className={`card ${styles.claimRow}`}>
                  <input
                    type="checkbox"
                    className={styles.claimCheckbox}
                    checked={selectedIds.has(claim.id)}
                    onChange={() => toggleSelected(claim.id)}
                    disabled={approving || isEditing}
                    aria-label={`Select claim ${claim.ordinal + 1}: ${claim.text}`}
                  />
                  <div className={styles.claimBody}>
                    <div className={styles.claimTopRow}>
                      <span className={styles.ordinal}>#{claim.ordinal + 1}</span>
                      <span className={styles.originBadge}>{claim.origin}</span>
                      {claim.is_approved && (
                        <span className={`${styles.statusBadge} ${styles.statusApproved}`}>
                          Approved
                        </span>
                      )}
                    </div>

                    {isEditing ? (
                      <div className={styles.editRow}>
                        <label className="visuallyHidden" htmlFor={`edit-${claim.id}`}>
                          Edit claim {claim.ordinal + 1}
                        </label>
                        <textarea
                          id={`edit-${claim.id}`}
                          className="textArea"
                          value={editText}
                          onChange={(event) => setEditText(event.target.value)}
                          disabled={isSaving}
                        />
                        <div className={styles.claimActions}>
                          <button
                            type="button"
                            className="button buttonPrimary"
                            onClick={() => saveEdit(claim.id)}
                            disabled={isSaving}
                          >
                            {isSaving ? "Saving…" : "Save"}
                          </button>
                          <button
                            type="button"
                            className="button buttonSecondary"
                            onClick={cancelEdit}
                            disabled={isSaving}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className={styles.claimText}>{claim.text}</p>
                        <div className={styles.claimActions}>
                          <button
                            type="button"
                            className="button buttonSecondary"
                            onClick={() => startEdit(claim)}
                            disabled={approving}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="button buttonDanger"
                            onClick={() => handleDelete(claim.id)}
                            disabled={approving || isDeleting}
                          >
                            {isDeleting ? "Deleting…" : "Delete"}
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>

          <div className={styles.footerActions}>
            <button
              type="button"
              className="button buttonPrimary"
              onClick={handleApprove}
              disabled={approving || selectedIds.size === 0}
            >
              {approving ? "Approving…" : "Approve selected"}
            </button>
            <button
              type="button"
              className="button buttonPrimary"
              onClick={handleAnalyze}
              disabled={!canAnalyze}
            >
              {analyzing ? "Starting analysis…" : "Analyze"}
            </button>
            {thesis.status !== "approved" && (
              <span className={styles.helpText}>
                Approve at least one claim before running an analysis.
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
