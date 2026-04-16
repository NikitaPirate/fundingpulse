"use client";

import { Fragment } from "react";

import { formatFundingValue } from "../../_lib/formatFundingValue";
import type {
  AnalysisMode,
  ContractMeta,
  PairSummary,
  SingleContractSummary,
  WindowDays,
} from "../_lib/types";
import { SUMMARY_WINDOWS } from "../_lib/types";
import styles from "./SummaryBand.module.css";

type SummaryBandProps = {
  mode: AnalysisMode;
  loading: boolean;
  error: string | null;
  c1Meta: ContractMeta | null;
  c2Meta: ContractMeta | null;
  c1Summary: SingleContractSummary | null;
  c2Summary: SingleContractSummary | null;
  pairSummary: PairSummary | null;
};

const EMPTY_WINDOWS: Record<WindowDays, number | null> = {
  7: null,
  14: null,
  30: null,
  90: null,
  180: null,
  365: null,
};

function formatContractShort(meta: ContractMeta | null) {
  if (!meta) {
    return "—";
  }

  return `${meta.sectionName} / ${meta.quoteName}`;
}

function formatMetric(value: number | null) {
  return value === null ? "—" : formatFundingValue(value);
}

function formatTimestamp(timestamp: number | null) {
  if (timestamp === null) {
    return "—";
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(timestamp * 1000);
}

function metricClassName(value: number | null) {
  if (value === null) {
    return styles.metricMuted;
  }

  return value >= 0 ? styles.metricPositive : styles.metricNegative;
}

function MetricCluster({
  label,
  value,
  meta,
}: {
  label: string;
  value: number | null;
  meta?: string;
}) {
  return (
    <div className={styles.metricCluster}>
      <span className={styles.metricLabel}>{label}</span>
      <strong className={`${styles.metricValue} ${metricClassName(value)}`}>
        {formatMetric(value)}
      </strong>
      {meta ? <span className={styles.metricMeta}>{meta}</span> : null}
    </div>
  );
}

type SummaryColumn = {
  title: string;
  subtitle: string;
  liveLabel: string;
  liveValue: number | null;
  settledLabel: string;
  settledValue: number | null;
  settledTimestamp: number | null;
  avgValues: Record<WindowDays, number | null>;
  totalValues: Record<WindowDays, number | null>;
  note?: string;
};

export function SummaryBand({
  mode,
  loading,
  error,
  c1Meta,
  c2Meta,
  c1Summary,
  c2Summary,
  pairSummary,
}: SummaryBandProps) {
  const primaryMeta = c1Meta ?? c2Meta;
  const primarySummary = c1Summary ?? c2Summary;
  const secondaryMeta = mode === "pair" ? c2Meta : null;
  const secondarySummary = mode === "pair" ? c2Summary : null;
  const showSpread = mode === "pair";
  const columns: SummaryColumn[] = [
    {
      title: "Contract 1",
      subtitle: formatContractShort(primaryMeta),
      liveLabel: "Current live",
      liveValue: primarySummary?.liveRate ?? null,
      settledLabel: "Last settled",
      settledValue: primarySummary?.lastSettledRate ?? null,
      settledTimestamp: primarySummary?.lastSettledTimestamp ?? null,
      avgValues: primarySummary?.avgWindows ?? EMPTY_WINDOWS,
      totalValues: primarySummary?.accumulatedWindows ?? EMPTY_WINDOWS,
      note: primaryMeta ? undefined : "Choose a contract.",
    },
    {
      title: "Contract 2",
      subtitle: formatContractShort(secondaryMeta),
      liveLabel: "Current live",
      liveValue: secondarySummary?.liveRate ?? null,
      settledLabel: "Last settled",
      settledValue: secondarySummary?.lastSettledRate ?? null,
      settledTimestamp: secondarySummary?.lastSettledTimestamp ?? null,
      avgValues: secondarySummary?.avgWindows ?? EMPTY_WINDOWS,
      totalValues: secondarySummary?.accumulatedWindows ?? EMPTY_WINDOWS,
      note: showSpread ? undefined : "Add a second contract to compare side by side.",
    },
    {
      title: "Spread",
      subtitle: showSpread ? "c1 - c2" : "Awaiting comparison",
      liveLabel: "Current spread",
      liveValue: pairSummary?.currentSpread ?? null,
      settledLabel: "Settled spread",
      settledValue: pairSummary?.lastSettledSpread ?? null,
      settledTimestamp: pairSummary?.lastSettledTimestamp ?? null,
      avgValues: pairSummary?.avgSpreadWindows ?? EMPTY_WINDOWS,
      totalValues: pairSummary?.accumulatedSpreadWindows ?? EMPTY_WINDOWS,
      note: showSpread
        ? "Spread is calculated as contract 1 minus contract 2."
        : "Spread becomes available after you select two contracts.",
    },
  ];

  return (
    <section className={styles.summaryBand} aria-label="Contract analysis summary">
      <div className={styles.summaryHeader}>
        <span className={styles.bandTitle}>Summary</span>
      </div>

      {error ? <div className={styles.message}>Summary failed to load: {error}</div> : null}

      {mode === "empty" ? (
        <div className={styles.message}>Summary will appear after you choose one or two contracts.</div>
      ) : loading ? (
        <div className={styles.message}>Loading summary…</div>
      ) : (
        <div className={styles.summaryScroller}>
          <div className={styles.summaryMatrix}>
            <div className={styles.cornerCell} aria-hidden="true" />
            {columns.map((column) => (
              <div className={styles.columnHeader} key={column.title}>
                <span className={styles.columnTitle}>{column.title}</span>
                <strong className={styles.columnSubtitle}>{column.subtitle}</strong>
              </div>
            ))}

            <div className={styles.rowHeader}>
              <span className={styles.rowLabel}>Now</span>
              <span className={styles.rowMeta}>Live / settled</span>
            </div>
            {columns.map((column) => (
              <div className={styles.snapshotCell} key={`${column.title}-now`}>
                <MetricCluster label={column.liveLabel} value={column.liveValue} />
                <MetricCluster
                  label={column.settledLabel}
                  meta={formatTimestamp(column.settledTimestamp)}
                  value={column.settledValue}
                />
              </div>
            ))}

            {SUMMARY_WINDOWS.map((window) => (
              <Fragment key={window}>
                <div className={styles.rowHeader}>
                  <span className={styles.rowLabel}>{window}d</span>
                  <span className={styles.rowMeta}>Average / accumulated</span>
                </div>
                {columns.map((column) => (
                  <div className={styles.periodCell} key={`${column.title}-${window}`}>
                    <MetricCluster label="Average" value={column.avgValues[window]} />
                    <MetricCluster label="Accumulated" value={column.totalValues[window]} />
                  </div>
                ))}
              </Fragment>
            ))}

            <div className={styles.rowHeader}>
              <span className={styles.rowLabel}>Context</span>
            </div>
            {columns.map((column) => (
              <div className={styles.noteCell} key={`${column.title}-note`}>
                {column.note ?? <span aria-hidden="true">&nbsp;</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
