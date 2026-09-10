"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/errors";
import { Spinner } from "@/components/Spinner";
import type { Company } from "@/lib/api/types";
import styles from "./page.module.css";

const MAX_THESIS_LENGTH = 5000;

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
    <div>
      <div className={styles.intro}>
        <h1 className={styles.title}>Start a new analysis</h1>
        <p className={styles.subtitle}>
          Pick a company and write your investment thesis. ThesisLedger extracts up
          to five testable claims and checks each one against that company&apos;s SEC
          filings.
        </p>
      </div>

      {companiesError && (
        <div className={`errorBanner`} role="alert" style={{ marginBottom: "1.25rem" }}>
          <p>Could not load companies: {companiesError}</p>
          <button
            type="button"
            className="button buttonSecondary"
            style={{ marginTop: "0.6rem" }}
            onClick={retryLoadCompanies}
          >
            Retry
          </button>
        </div>
      )}

      {!companiesError && companies === null && <Spinner label="Loading companies…" />}

      {!companiesError && companies !== null && companies.length === 0 && (
        <p className={styles.subtitle} role="status">
          No companies are available to analyze yet. If you&apos;re running this
          locally, seed them with <code>manage.py seed_companies</code> on the
          backend, then reload this page.
        </p>
      )}

      {!companiesError && companies !== null && companies.length > 0 && (
        <form className={`card ${styles.form}`} onSubmit={handleSubmit}>
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
                  {company.ticker} &mdash; {company.name}
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
            <span
              id="thesis-char-count"
              className={`${styles.charCount} ${overLimit ? styles.charCountOver : ""}`}
            >
              {thesisText.length} / {MAX_THESIS_LENGTH}
            </span>
          </div>

          {submitError && (
            <div className="errorBanner" role="alert">
              {submitError}
            </div>
          )}

          <div className={styles.actions}>
            <button type="submit" className="button buttonPrimary" disabled={!canSubmit}>
              {submitting ? "Generating claims…" : "Generate claims"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
