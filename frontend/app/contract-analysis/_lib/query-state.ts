import type { ReadonlyURLSearchParams } from "next/navigation";

import type { AnalysisMode, ContractAnalysisParams, Normalization } from "./types";

const NORMALIZATIONS = new Set<Normalization>(["raw", "1h", "8h", "1d", "365d"]);

export const DEFAULT_PARAMS: ContractAnalysisParams = {
  c1: null,
  c2: null,
  normalize: "365d",
};

export function parseQueryState(
  searchParams: ReadonlyURLSearchParams,
): ContractAnalysisParams {
  const normalize = searchParams.get("normalize");

  return {
    c1: searchParams.get("c1") || null,
    c2: searchParams.get("c2") || null,
    normalize:
      normalize && NORMALIZATIONS.has(normalize as Normalization)
        ? (normalize as Normalization)
        : DEFAULT_PARAMS.normalize,
  };
}

export function serializeQueryState(params: ContractAnalysisParams) {
  const next = new URLSearchParams();

  if (params.c1) {
    next.set("c1", params.c1);
  }

  if (params.c2) {
    next.set("c2", params.c2);
  }

  if (params.normalize !== DEFAULT_PARAMS.normalize) {
    next.set("normalize", params.normalize);
  }

  return next;
}

export function deriveMode(params: ContractAnalysisParams): AnalysisMode {
  if (params.c1 && params.c2) {
    return "pair";
  }

  if (params.c1 || params.c2) {
    return "single";
  }

  return "empty";
}

export function swapContracts(params: ContractAnalysisParams): ContractAnalysisParams {
  return {
    ...params,
    c1: params.c2,
    c2: params.c1,
  };
}
