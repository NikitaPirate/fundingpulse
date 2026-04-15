"use client";

import Link from "next/link";

import { formatFundingValue } from "../../_lib/formatFundingValue";
import styles from "../page.module.css";
import type {
  AssetFundingFilters,
  AssetFundingRow,
  SortDirection,
  SortField,
} from "../_lib/types";

type AssetFundingTableProps = {
  filters: AssetFundingFilters;
  rows: AssetFundingRow[] | null;
  loading: boolean;
  error: string | null;
  onSortChange: (field: SortField) => void;
};

const SORTABLE_COLUMNS: Array<{
  key: SortField;
  label: string;
}> = [
  { key: "section", label: "Exchange" },
  { key: "quote", label: "Quote" },
  { key: "live", label: "Live" },
  { key: "lastSettled", label: "Last settled" },
  { key: "avg7d", label: "7d" },
  { key: "avg30d", label: "30d" },
  { key: "avg90d", label: "90d" },
];

function renderSortIndicator(
  active: boolean,
  direction: SortDirection,
) {
  if (!active) {
    return "↕";
  }

  return direction === "asc" ? "↑" : "↓";
}

function metricClassName(value: number | null) {
  if (value === null) {
    return styles.mutedValue;
  }

  return value >= 0 ? styles.positiveValue : styles.negativeValue;
}

function renderMetric(value: number | null) {
  if (value === null) {
    return "—";
  }

  return formatFundingValue(value);
}

export function AssetFundingTable({
  filters,
  rows,
  loading,
  error,
  onSortChange,
}: AssetFundingTableProps) {
  const rowCount = rows?.length ?? 0;

  return (
    <section className={styles.tableSection} aria-label="Asset funding contracts">
      <div className={styles.tableHeader}>
        <div className={styles.tableHeaderCopy}>
          <span className={styles.bandTitle}>Contracts Surface</span>
          <strong className={styles.tableCount}>
            {filters.asset ? `${rowCount} contracts` : "Contracts"}
          </strong>
        </div>

        <div className={styles.tableMeta}>
          {filters.asset ? <span>{filters.asset}</span> : null}
          <span>{filters.normalize}</span>
          <span>Client-sorted</span>
        </div>
      </div>

      {error ? (
        <div className={styles.messagePanel} role="alert">
          Failed to load asset funding data: {error}
        </div>
      ) : null}

      {!filters.asset ? (
        <div className={styles.emptyState}>
          Choose an asset to see contract-level live, settled, and rolling funding context.
        </div>
      ) : null}

      {!error && !loading && filters.asset && rows && rows.length === 0 ? (
        <div className={styles.emptyState}>
          No contracts match the current asset filters.
        </div>
      ) : null}

      <div className={styles.tableShell}>
        <div className={styles.tableHead}>
          {SORTABLE_COLUMNS.map((column) => (
            <button
              className={styles.columnButton}
              key={column.key}
              onClick={() => onSortChange(column.key)}
              type="button"
            >
              <span>{column.label}</span>
              <span className={styles.sortIndicator}>
                {renderSortIndicator(
                  filters.sortBy === column.key,
                  filters.sortDir,
                )}
              </span>
            </button>
          ))}
        </div>

        <div className={styles.tableBody}>
          {loading && filters.asset
            ? Array.from({ length: 10 }).map((_, index) => (
                <div className={styles.tableRowSkeleton} key={`loading-${index}`}>
                  {Array.from({ length: SORTABLE_COLUMNS.length }).map((__, cellIndex) => (
                    <span className={styles.cellBar} key={cellIndex} />
                  ))}
                </div>
              ))
            : rows?.map((row) => (
                <Link
                  className={styles.tableRow}
                  href={`/contract-analysis?c1=${row.contractId}`}
                  key={row.contractId}
                >
                  <span className={styles.primaryCell}>{row.section}</span>
                  <span className={styles.secondaryCell}>{row.quote}</span>
                  <span className={metricClassName(row.live)}>{renderMetric(row.live)}</span>
                  <span className={metricClassName(row.lastSettled)}>
                    {renderMetric(row.lastSettled)}
                  </span>
                  <span className={metricClassName(row.avg7d)}>{renderMetric(row.avg7d)}</span>
                  <span className={metricClassName(row.avg30d)}>{renderMetric(row.avg30d)}</span>
                  <span className={metricClassName(row.avg90d)}>{renderMetric(row.avg90d)}</span>
                </Link>
              ))}
        </div>
      </div>
    </section>
  );
}
