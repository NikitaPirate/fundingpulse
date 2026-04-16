"use client";

import { useEffect, useState } from "react";

import styles from "../../page.module.css";
import { fetchHistoricalPoints, fetchLivePoints } from "../../_lib/chart-api";
import type { AnalysisMode, ContractMeta, FundingPoint, Normalization } from "../../_lib/types";
import { HistoricalFundingChart } from "./HistoricalFundingChart";
import { LiveFundingChart } from "./LiveFundingChart";
import { LiveVsHistoricalChart } from "./LiveVsHistoricalChart";

type ChartStackProps = {
  c1Meta: ContractMeta | null;
  c2Meta: ContractMeta | null;
  normalize: Normalization;
  mode: AnalysisMode;
};

type PointsState = {
  c1: FundingPoint[];
  c2: FundingPoint[];
  error: string | null;
  settledKey: string | null;
};

const EMPTY_POINTS_STATE: PointsState = {
  c1: [],
  c2: [],
  error: null,
  settledKey: null,
};

function buildKey(
  label: string,
  c1Meta: ContractMeta | null,
  c2Meta: ContractMeta | null,
  normalize: Normalization,
  fromTs: number,
  toTs: number,
) {
  return `${label}:${c1Meta?.id ?? "-"}:${c2Meta?.id ?? "-"}:${normalize}:${fromTs}:${toTs}`;
}

export function ChartStack({ c1Meta, c2Meta, normalize, mode }: ChartStackProps) {
  const [liveState, setLiveState] = useState<PointsState>(EMPTY_POINTS_STATE);
  const [historicalState, setHistoricalState] = useState<PointsState>(EMPTY_POINTS_STATE);
  const [nowTs] = useState(() => Math.floor(Date.now() / 1000));
  const hasContracts = c1Meta !== null || c2Meta !== null;
  const liveFromTs = nowTs - 7 * 24 * 60 * 60;
  const historicalFromTs = nowTs - 90 * 24 * 60 * 60;

  const expectedLiveKey = buildKey("live", c1Meta, c2Meta, normalize, liveFromTs, nowTs);
  const expectedHistoricalKey = buildKey(
    "historical",
    c1Meta,
    c2Meta,
    normalize,
    historicalFromTs,
    nowTs,
  );

  useEffect(() => {
    const abortController = new AbortController();

    const load = async () => {
      const liveResults = await Promise.all([
        c1Meta
          ? fetchLivePoints(c1Meta.id, liveFromTs, nowTs, normalize, abortController.signal)
          : Promise.resolve([]),
        c2Meta
          ? fetchLivePoints(c2Meta.id, liveFromTs, nowTs, normalize, abortController.signal)
          : Promise.resolve([]),
      ]);

      setLiveState({
        c1: liveResults[0],
        c2: liveResults[1],
        error: null,
        settledKey: expectedLiveKey,
      });
    };

    void load().catch((error: unknown) => {
      if (abortController.signal.aborted) {
        return;
      }

      setLiveState({
        c1: [],
        c2: [],
        error: error instanceof Error ? error.message : "Unknown error",
        settledKey: expectedLiveKey,
      });
    });

    return () => abortController.abort();
  }, [c1Meta, c2Meta, expectedLiveKey, liveFromTs, normalize, nowTs]);

  useEffect(() => {
    const abortController = new AbortController();

    const load = async () => {
      const historicalResults = await Promise.all([
        c1Meta
          ? fetchHistoricalPoints(
              c1Meta.id,
              historicalFromTs,
              nowTs,
              normalize,
              abortController.signal,
            )
          : Promise.resolve([]),
        c2Meta
          ? fetchHistoricalPoints(
              c2Meta.id,
              historicalFromTs,
              nowTs,
              normalize,
              abortController.signal,
            )
          : Promise.resolve([]),
      ]);

      setHistoricalState({
        c1: historicalResults[0],
        c2: historicalResults[1],
        error: null,
        settledKey: expectedHistoricalKey,
      });
    };

    void load().catch((error: unknown) => {
      if (abortController.signal.aborted) {
        return;
      }

      setHistoricalState({
        c1: [],
        c2: [],
        error: error instanceof Error ? error.message : "Unknown error",
        settledKey: expectedHistoricalKey,
      });
    });

    return () => abortController.abort();
  }, [c1Meta, c2Meta, expectedHistoricalKey, historicalFromTs, normalize, nowTs]);

  const liveLoading = hasContracts && liveState.settledKey !== expectedLiveKey;
  const historicalLoading = hasContracts && historicalState.settledKey !== expectedHistoricalKey;
  const pairMode = mode === "pair";

  return (
    <section className={styles.chartStack} aria-label="Contract analysis charts">
      <section className={styles.chartSection}>
        <div className={styles.chartHeader}>
          <div className={styles.chartHeaderCopy}>
            <span className={styles.bandTitle}>Live Funding Rates</span>
            <span className={styles.chartMeta}>Last 7d</span>
          </div>
        </div>

        <LiveFundingChart
          c1Meta={c1Meta}
          c1Points={liveState.c1}
          c2Meta={c2Meta}
          c2Points={liveState.c2}
          error={liveState.error}
          loading={liveLoading}
          pairMode={pairMode}
        />
      </section>

      <section className={styles.chartSection}>
        <div className={styles.chartHeader}>
          <div className={styles.chartHeaderCopy}>
            <span className={styles.bandTitle}>Historical Funding Rates</span>
            <span className={styles.chartMeta}>Last 90d</span>
          </div>
        </div>

        <HistoricalFundingChart
          c1Meta={c1Meta}
          c1Points={historicalState.c1}
          c2Meta={c2Meta}
          c2Points={historicalState.c2}
          error={historicalState.error}
          loading={historicalLoading}
          pairMode={pairMode}
        />
      </section>

      <section className={styles.chartSection}>
        <div className={styles.chartHeader}>
          <div className={styles.chartHeaderCopy}>
            <span className={styles.bandTitle}>Live vs Historical</span>
            <span className={styles.chartMeta}>Per contract</span>
          </div>
        </div>

        <div className={styles.liveVsHistoricalGrid}>
          {c1Meta ? (
            <div className={styles.chartSubsection}>
              <div className={styles.chartSubheader}>{c1Meta.sectionName} / {c1Meta.quoteName}</div>
              <LiveVsHistoricalChart
                historicalError={historicalState.error}
                historicalLoading={historicalLoading}
                historicalPoints={historicalState.c1}
                liveError={liveState.error}
                liveLoading={liveLoading}
                livePoints={liveState.c1}
                meta={c1Meta}
              />
            </div>
          ) : (
            <div className={styles.chartSubsection}>
              <div className={styles.chartSubheader}>Contract 1</div>
              <LiveVsHistoricalChart
                historicalError={null}
                historicalLoading={false}
                historicalPoints={[]}
                liveError={null}
                liveLoading={false}
                livePoints={[]}
                meta={null}
              />
            </div>
          )}

          {c2Meta ? (
            <div className={styles.chartSubsection}>
              <div className={styles.chartSubheader}>{c2Meta.sectionName} / {c2Meta.quoteName}</div>
              <LiveVsHistoricalChart
                historicalError={historicalState.error}
                historicalLoading={historicalLoading}
                historicalPoints={historicalState.c2}
                liveError={liveState.error}
                liveLoading={liveLoading}
                livePoints={liveState.c2}
                meta={c2Meta}
              />
            </div>
          ) : (
            <div className={styles.chartSubsection}>
              <div className={styles.chartSubheader}>Contract 2</div>
              <LiveVsHistoricalChart
                historicalError={null}
                historicalLoading={false}
                historicalPoints={[]}
                liveError={null}
                liveLoading={false}
                livePoints={[]}
                meta={null}
              />
            </div>
          )}
        </div>
      </section>
    </section>
  );
}
