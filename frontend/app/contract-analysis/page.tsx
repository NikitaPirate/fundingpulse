import { Suspense } from "react";

import { ContractAnalysisClient } from "./_components/ContractAnalysisClient";
import styles from "./page.module.css";

function ContractAnalysisFallback() {
  return (
    <article className={styles.page}>
      <section className={styles.messagePanel}>Loading contract analysis...</section>
    </article>
  );
}

export default function ContractAnalysisPage() {
  return (
    <Suspense fallback={<ContractAnalysisFallback />}>
      <ContractAnalysisClient />
    </Suspense>
  );
}
