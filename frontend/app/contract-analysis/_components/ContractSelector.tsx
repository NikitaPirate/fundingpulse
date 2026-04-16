"use client";

import { useEffect, useMemo, useState } from "react";

import { FilterPopover } from "../../_components/FilterPopover";
import { fetchContractSearch } from "../_lib/api";
import type { ContractMeta, ContractSearchResult } from "../_lib/types";
import styles from "./ContractSelector.module.css";

type ContractSelectorProps = {
  label: string;
  selectedMeta: ContractMeta | null;
  error: string | null;
  onChange: (contractId: string | null) => void;
};

function formatContractLabel(meta: {
  assetName: string;
  sectionName: string;
  quoteName: string;
}) {
  return `${meta.assetName} / ${meta.sectionName} / ${meta.quoteName}`;
}

export function ContractSelector({
  label,
  selectedMeta,
  error,
  onChange,
}: ContractSelectorProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ContractSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const trimmedQuery = query.trim();

  useEffect(() => {
    if (!trimmedQuery) {
      return;
    }

    const abortController = new AbortController();
    const timeoutId = window.setTimeout(() => {
      setLoading(true);

      fetchContractSearch(trimmedQuery, 10, abortController.signal)
        .then((nextResults) => {
          setResults(nextResults);
          setSearchError(null);
          setLoading(false);
        })
        .catch((nextError: unknown) => {
          if (abortController.signal.aborted) {
            return;
          }

          setResults([]);
          setSearchError(nextError instanceof Error ? nextError.message : "Unknown error");
          setLoading(false);
        });
    }, 250);

    return () => {
      window.clearTimeout(timeoutId);
      abortController.abort();
    };
  }, [trimmedQuery]);

  const summary = useMemo(() => {
    if (selectedMeta) {
      return formatContractLabel(selectedMeta);
    }

    return "Search contracts";
  }, [selectedMeta]);
  const visibleResults = trimmedQuery ? results : [];
  const visibleLoading = trimmedQuery ? loading : false;
  const visibleSearchError = trimmedQuery ? searchError : null;

  return (
    <div className={styles.selector}>
      <FilterPopover active={selectedMeta !== null} label={label} summary={summary}>
        {({ close }) => (
          <>
            <div className={styles.panelHeader}>
              <strong className={styles.panelTitle}>{label}</strong>
              <button
                className={styles.panelAction}
                onClick={() => {
                  onChange(null);
                  setQuery("");
                  close();
                }}
                type="button"
              >
                Clear
              </button>
            </div>

            <input
              autoComplete="off"
              className={styles.searchInput}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search asset, exchange, or quote..."
              type="search"
              value={query}
            />

            {error ? <div className={styles.inlineError}>Selected contract failed to load: {error}</div> : null}
            {visibleSearchError ? (
              <div className={styles.inlineError}>Search failed: {visibleSearchError}</div>
            ) : null}

            <div className={styles.resultsList}>
              {!trimmedQuery ? (
                <span className={styles.emptyState}>Type to search contracts.</span>
              ) : visibleLoading ? (
                <span className={styles.emptyState}>Searching…</span>
              ) : visibleResults.length === 0 ? (
                <span className={styles.emptyState}>No matching contracts.</span>
              ) : (
                visibleResults.map((result) => (
                  <button
                    className={styles.resultRow}
                    key={result.id}
                    onClick={() => {
                      onChange(result.id);
                      setQuery("");
                      close();
                    }}
                    type="button"
                  >
                    <span className={styles.resultPrimary}>
                      {result.assetName} / {result.sectionName} / {result.quoteName}
                    </span>
                    <span className={styles.resultMeta}>{result.fundingInterval}h funding</span>
                  </button>
                ))
              )}
            </div>
          </>
        )}
      </FilterPopover>

      {selectedMeta ? (
        <button
          aria-label={`Clear ${label}`}
          className={styles.clearButton}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onChange(null);
          }}
          type="button"
        >
          ×
        </button>
      ) : null}
    </div>
  );
}
