"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import styles from "../page.module.css";
import { ChartStack } from "./charts/ChartStack";
import { ContractSelectorBand } from "./ContractSelectorBand";
import { SummaryBand } from "./SummaryBand";
import {
  computePairSummary,
  fetchContractMeta,
  fetchContractSummary,
  getSummaryKey,
} from "../_lib/api";
import {
  DEFAULT_PARAMS,
  deriveMode,
  parseQueryState,
  serializeQueryState,
  swapContracts,
} from "../_lib/query-state";
import type {
  ContractAnalysisParams,
  MetaState,
  SummaryState,
} from "../_lib/types";

const EMPTY_META_STATE: MetaState = {
  contractId: null,
  meta: null,
  error: null,
  settledId: null,
};

const EMPTY_SUMMARY_STATE: SummaryState = {
  contractId: null,
  summary: null,
  error: null,
  settledKey: null,
};

function expectedSummaryKey(state: MetaState, normalize: ContractAnalysisParams["normalize"]) {
  if (!state.meta || !state.contractId || state.contractId !== state.meta.id) {
    return null;
  }

  return getSummaryKey(state.meta, normalize);
}

export function ContractAnalysisClient() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentQuery = searchParams.toString();
  const params = useMemo(() => parseQueryState(searchParams), [searchParams]);
  const mode = useMemo(() => deriveMode(params), [params]);

  const [c1MetaState, setC1MetaState] = useState<MetaState>(EMPTY_META_STATE);
  const [c2MetaState, setC2MetaState] = useState<MetaState>(EMPTY_META_STATE);
  const [c1SummaryState, setC1SummaryState] = useState<SummaryState>(EMPTY_SUMMARY_STATE);
  const [c2SummaryState, setC2SummaryState] = useState<SummaryState>(EMPTY_SUMMARY_STATE);

  const replaceParams = useCallback(
    (nextParams: ContractAnalysisParams) => {
      const serialized = serializeQueryState(nextParams).toString();
      if (serialized === currentQuery) {
        return;
      }

      const nextUrl = serialized ? `${pathname}?${serialized}` : pathname;
      window.history.replaceState(null, "", nextUrl);
    },
    [currentQuery, pathname],
  );

  const updateParams = useCallback(
    (patch: Partial<ContractAnalysisParams>) => {
      replaceParams({
        ...params,
        ...patch,
      });
    },
    [params, replaceParams],
  );

  useEffect(() => {
    const abortController = new AbortController();

    if (params.c1) {
      fetchContractMeta(params.c1, abortController.signal)
        .then((meta) => {
          setC1MetaState({
            contractId: params.c1,
            meta,
            error: null,
            settledId: params.c1,
          });
        })
        .catch((error: unknown) => {
          if (abortController.signal.aborted) {
            return;
          }

          setC1MetaState({
            contractId: params.c1,
            meta: null,
            error: error instanceof Error ? error.message : "Unknown error",
            settledId: params.c1,
          });
        });
    }

    if (params.c2) {
      fetchContractMeta(params.c2, abortController.signal)
        .then((meta) => {
          setC2MetaState({
            contractId: params.c2,
            meta,
            error: null,
            settledId: params.c2,
          });
        })
        .catch((error: unknown) => {
          if (abortController.signal.aborted) {
            return;
          }

          setC2MetaState({
            contractId: params.c2,
            meta: null,
            error: error instanceof Error ? error.message : "Unknown error",
            settledId: params.c2,
          });
        });
    }

    return () => abortController.abort();
  }, [params.c1, params.c2]);

  useEffect(() => {
    const abortController = new AbortController();

    if (c1MetaState.meta) {
      const settledKey = getSummaryKey(c1MetaState.meta, params.normalize);
      fetchContractSummary(c1MetaState.meta, params.normalize, abortController.signal)
        .then((summary) => {
          setC1SummaryState({
            contractId: c1MetaState.meta?.id ?? null,
            summary,
            error: null,
            settledKey,
          });
        })
        .catch((error: unknown) => {
          if (abortController.signal.aborted) {
            return;
          }

          setC1SummaryState({
            contractId: c1MetaState.meta?.id ?? null,
            summary: null,
            error: error instanceof Error ? error.message : "Unknown error",
            settledKey,
          });
        });
    }

    if (c2MetaState.meta) {
      const settledKey = getSummaryKey(c2MetaState.meta, params.normalize);
      fetchContractSummary(c2MetaState.meta, params.normalize, abortController.signal)
        .then((summary) => {
          setC2SummaryState({
            contractId: c2MetaState.meta?.id ?? null,
            summary,
            error: null,
            settledKey,
          });
        })
        .catch((error: unknown) => {
          if (abortController.signal.aborted) {
            return;
          }

          setC2SummaryState({
            contractId: c2MetaState.meta?.id ?? null,
            summary: null,
            error: error instanceof Error ? error.message : "Unknown error",
            settledKey,
          });
        });
    }

    return () => abortController.abort();
  }, [c1MetaState.meta, c2MetaState.meta, params.normalize]);

  const expectedC1SummaryKey = expectedSummaryKey(c1MetaState, params.normalize);
  const expectedC2SummaryKey = expectedSummaryKey(c2MetaState, params.normalize);
  const c1Meta =
    params.c1 && c1MetaState.settledId === params.c1 ? c1MetaState.meta : null;
  const c2Meta =
    params.c2 && c2MetaState.settledId === params.c2 ? c2MetaState.meta : null;
  const c1MetaError =
    params.c1 && c1MetaState.settledId === params.c1 ? c1MetaState.error : null;
  const c2MetaError =
    params.c2 && c2MetaState.settledId === params.c2 ? c2MetaState.error : null;

  const c1Summary =
    expectedC1SummaryKey && c1SummaryState.settledKey === expectedC1SummaryKey
      ? c1SummaryState.summary
      : null;
  const c2Summary =
    expectedC2SummaryKey && c2SummaryState.settledKey === expectedC2SummaryKey
      ? c2SummaryState.summary
      : null;

  const c1SummaryError =
    expectedC1SummaryKey && c1SummaryState.settledKey === expectedC1SummaryKey
      ? c1SummaryState.error
      : null;
  const c2SummaryError =
    expectedC2SummaryKey && c2SummaryState.settledKey === expectedC2SummaryKey
      ? c2SummaryState.error
      : null;

  const summaryLoading =
    (expectedC1SummaryKey !== null && c1SummaryState.settledKey !== expectedC1SummaryKey) ||
    (expectedC2SummaryKey !== null && c2SummaryState.settledKey !== expectedC2SummaryKey);

  const pairSummary =
    c1Summary && c2Summary && mode === "pair" ? computePairSummary(c1Summary, c2Summary) : null;

  return (
    <article className={styles.page}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <h1 className={styles.title}>Contract Analysis</h1>
          <p className={styles.subtitle}>
            Contract-level funding context for one venue or a role-sensitive pair.
          </p>
        </div>

        <div className={styles.headerMeta}>
          <span>{mode === "pair" ? "Pair mode" : mode === "single" ? "Single mode" : "No contracts"}</span>
          <span>{params.normalize}</span>
          <span>URL-driven</span>
        </div>
      </header>

      <section className={styles.workspace}>
        <ContractSelectorBand
          c1Meta={c1Meta}
          c1MetaError={c1MetaError}
          c2Meta={c2Meta}
          c2MetaError={c2MetaError}
          normalize={params.normalize}
          onClearAll={() => replaceParams(DEFAULT_PARAMS)}
          onNormalizeChange={(normalize) => updateParams({ normalize })}
          onSwap={() => replaceParams(swapContracts(params))}
          onUpdateC1={(c1) => updateParams({ c1 })}
          onUpdateC2={(c2) => updateParams({ c2 })}
        />

        <SummaryBand
          c1Meta={c1Meta}
          c1Summary={c1Summary}
          c2Meta={c2Meta}
          c2Summary={c2Summary}
          error={c1MetaError ?? c2MetaError ?? c1SummaryError ?? c2SummaryError}
          loading={summaryLoading}
          mode={mode}
          pairSummary={pairSummary}
        />

        {mode === "empty" ? (
          <section className={styles.messagePanel}>
            Search for a contract to begin analysis. Charts stay visible below and will fill in as soon as you pick a contract.
          </section>
        ) : null}

        <ChartStack
          c1Meta={c1Meta}
          c2Meta={c2Meta}
          mode={mode}
          normalize={params.normalize}
        />
      </section>
    </article>
  );
}
