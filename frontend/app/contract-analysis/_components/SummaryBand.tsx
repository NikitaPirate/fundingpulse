"use client";

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

function WindowRow({
  label,
  values,
}: {
  label: string;
  values: Record<WindowDays, number | null>;
}) {
  return (
    <div className={styles.windowRow}>
      <span className={styles.windowLabel}>{label}</span>
      <div className={styles.windowValues}>
        {SUMMARY_WINDOWS.map((window) => (
          <div className={styles.windowCell} key={window}>
            <span className={styles.windowKey}>{window}d</span>
            <span className={metricClassName(values[window])}>{formatMetric(values[window])}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SummaryCard({
  title,
  subtitle,
  liveLabel,
  liveValue,
  settledLabel,
  settledValue,
  settledTimestamp,
  avgValues,
  totalValues,
  note,
}: {
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
}) {
  return (
    <article className={styles.summaryCard}>
      <div className={styles.cardTop}>
        <span className={styles.cardTitle}>{title}</span>
        <strong className={styles.cardSubtitle}>{subtitle}</strong>
      </div>

      <div className={styles.metricsGrid}>
        <div className={styles.metricBlock}>
          <span className={styles.headlineLabel}>{liveLabel}</span>
          <strong className={metricClassName(liveValue)}>{formatMetric(liveValue)}</strong>
        </div>
        <div className={styles.metricBlock}>
          <span className={styles.headlineLabel}>{settledLabel}</span>
          <strong className={metricClassName(settledValue)}>{formatMetric(settledValue)}</strong>
          <span className={styles.headlineMeta}>{formatTimestamp(settledTimestamp)}</span>
        </div>
      </div>

      <WindowRow label="Average by period" values={avgValues} />
      <WindowRow label="Accumulated by period" values={totalValues} />
      {note ? <span className={styles.cardNote}>{note}</span> : null}
    </article>
  );
}

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
        <div className={styles.cardsGrid}>
          <SummaryCard
            avgValues={primarySummary?.avgWindows ?? EMPTY_WINDOWS}
            liveLabel="Current live"
            liveValue={primarySummary?.liveRate ?? null}
            note={primaryMeta ? undefined : "Choose a contract"}
            settledLabel="Last settled"
            settledTimestamp={primarySummary?.lastSettledTimestamp ?? null}
            settledValue={primarySummary?.lastSettledRate ?? null}
            subtitle={formatContractShort(primaryMeta)}
            title="Contract 1"
            totalValues={primarySummary?.accumulatedWindows ?? EMPTY_WINDOWS}
          />

          <SummaryCard
            avgValues={secondarySummary?.avgWindows ?? EMPTY_WINDOWS}
            liveLabel="Current live"
            liveValue={secondarySummary?.liveRate ?? null}
            note={showSpread ? undefined : "Add a second contract to compare funding side by side."}
            settledLabel="Last settled"
            settledTimestamp={secondarySummary?.lastSettledTimestamp ?? null}
            settledValue={secondarySummary?.lastSettledRate ?? null}
            subtitle={formatContractShort(secondaryMeta)}
            title="Contract 2"
            totalValues={secondarySummary?.accumulatedWindows ?? EMPTY_WINDOWS}
          />

          <SummaryCard
            avgValues={pairSummary?.avgSpreadWindows ?? EMPTY_WINDOWS}
            liveLabel="Current spread"
            liveValue={pairSummary?.currentSpread ?? null}
            note={showSpread ? "Spread is calculated as contract 1 minus contract 2." : "Spread becomes available after you select two contracts."}
            settledLabel="Settled spread"
            settledTimestamp={pairSummary?.lastSettledTimestamp ?? null}
            settledValue={pairSummary?.lastSettledSpread ?? null}
            subtitle={showSpread ? "c1 - c2" : "Awaiting comparison"}
            title="Spread"
            totalValues={pairSummary?.accumulatedSpreadWindows ?? EMPTY_WINDOWS}
          />
        </div>
      )}
    </section>
  );
}
