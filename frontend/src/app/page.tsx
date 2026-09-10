"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/errors";
import { Spinner } from "@/components/Spinner";
import type { Company } from "@/lib/api/types";
import styles from "./page.module.css";

const MAX_THESIS_LENGTH = 5000;

const STEPS = ["Your thesis", "Up to 5 claims", "Cited evidence"];

export default function HomePage() {
  const router = useRouter();

  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [companiesError, setCompaniesError] = useState<string | null>(null);
  const [selectedCompanyId, setSelectedCompanyId] = useState("");
  const [thesisText, setThesisText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  function retryLoadCompanies() {
    setCompanies(null);
    setCompaniesError(null);
    setReloadKey((key) => key + 1);
  }

  useEffect(() => {
    let cancelled = false;

    async function loadCompanies() {
      try {
        const response = await api.listCompanies();
        if (cancelled) return;
        setCompanies(response.results);
        if (response.results.length > 0) {
          setSelectedCompanyId(response.results[0].id);
        }
      } catch (err) {
        if (cancelled) return;
        setCompaniesError(errorMessage(err));
      }
    }

    loadCompanies();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const trimmedLength = thesisText.trim().length;
  const overLimit = thesisText.length > MAX_THESIS_LENGTH;
  const fillPct = Math.min(100, (thesisText.length / MAX_THESIS_LENGTH) * 100);
  const nearLimit = fillPct >= 90 && !overLimit;
  const canSubmit =
    !submitting &&
    Boolean(companies?.length) &&
    Boolean(selectedCompanyId) &&
    trimmedLength > 0 &&
    !overLimit;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;

    setSubmitError(null);
    setSubmitting(true);
    try {
      const thesis = await api.createThesis({
        company_id: selectedCompanyId,
        text: thesisText.trim(),
      });
      await api.generateClaims(thesis.id);
      router.push(`/theses/${thesis.id}/claims`);
    } catch (err) {
      setSubmitError(errorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.wrap}>
      <header className={styles.hero}>
        <span className={styles.eyebrow}>SEC-grounded · no fabricated citations</span>
        <h1 className={styles.title}>Pressure-test your investment thesis.</h1>
        <p className={styles.lede}>
          ThesisLedger breaks your thesis into up to five testable claims and checks
          each one against the company&apos;s SEC filings — every verdict quotes a real
          passage.
        </p>
        <ol className={styles.steps} aria-label="How it works">
          {STEPS.map((step, i) => (
            <li key={step} className={styles.step}>
              <span className={styles.stepNum}>{i + 1}</span>
              {step}
            </li>
          ))}
        </ol>
      </header>

      {companiesError && (
        <div className="errorBanner" role="alert">
          <p>Could not load companies: {companiesError}</p>
          <button
            type="button"
            className="button buttonSecondary"
            style={{ marginTop: "0.7rem" }}
            onClick={retryLoadCompanies}
          >
            Retry
          </button>
        </div>
      )}

      {!companiesError && companies === null && (
        <div className={styles.formCard}>
          <Spinner label="Loading companies…" />
        </div>
      )}

      {!companiesError && companies !== null && companies.length === 0 && (
        <div className={`card ${styles.formCard}`}>
          <p className={styles.emptyText}>
            No companies are available to analyze yet. If you&apos;re running this
            locally, seed them with <code>manage.py seed_companies</code> on the backend,
            then reload.
          </p>
        </div>
      )}

      {!companiesError && companies !== null && companies.length > 0 && (
        <form className={`card ${styles.formCard}`} onSubmit={handleSubmit}>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="company">
              Company
            </label>
            <select
              id="company"
              className="select"
              value={selectedCompanyId}
              onChange={(event) => setSelectedCompanyId(event.target.value)}
              disabled={submitting}
              required
            >
              {companies.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.ticker} — {company.name}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.field}>
            <label className={styles.label} htmlFor="thesis-text">
              Investment thesis
            </label>
            <textarea
              id="thesis-text"
              className="textArea"
              value={thesisText}
              onChange={(event) => setThesisText(event.target.value)}
              disabled={submitting}
              placeholder="e.g. Services revenue will keep growing faster than hardware, expanding overall margins."
              aria-describedby="thesis-char-count"
              required
            />
            <div className={styles.meter} aria-hidden="true">
              <div
                className={`${styles.meterFill} ${overLimit ? styles.meterOver : ""} ${
                  nearLimit ? styles.meterNear : ""
                }`}
                style={{ width: `${fillPct}%` }}
              />
            </div>
            <span
              id="thesis-char-count"
              className={`${styles.charCount} ${overLimit ? styles.charCountOver : ""} ${
                nearLimit ? styles.charCountNear : ""
              }`}
            >
              {thesisText.length.toLocaleString()} / {MAX_THESIS_LENGTH.toLocaleString()}
            </span>
          </div>

          {submitError && (
            <div className="errorBanner" role="alert">
              {submitError}
            </div>
          )}

          <button type="submit" className={`button buttonPrimary ${styles.submit}`} disabled={!canSubmit}>
            {submitting ? (
              <>
                <span className={styles.btnSpinner} aria-hidden="true" />
                Generating claims…
              </>
            ) : (
              "Generate claims"
            )}
          </button>
        </form>
      )}
    </div>
  );
}
