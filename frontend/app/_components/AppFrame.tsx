import type { ReactNode } from "react";

import { PortfolioBanner } from "./PortfolioBanner";
import { SiteFooter } from "./SiteFooter";
import { TopNavigation } from "./TopNavigation";
import styles from "./AppFrame.module.css";

type AppFrameProps = {
  children: ReactNode;
};

export function AppFrame({ children }: AppFrameProps) {
  return (
    <div className={styles.shell}>
      <div className={styles.chrome}>
        <PortfolioBanner />
        <TopNavigation />
      </div>
      <main className={styles.main} id="main-content">
        <div className={styles.mainInner}>{children}</div>
      </main>
      <SiteFooter />
    </div>
  );
}
