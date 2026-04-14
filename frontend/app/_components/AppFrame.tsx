import type { ReactNode } from "react";

import { TopNavigation } from "./TopNavigation";
import styles from "./AppFrame.module.css";

type AppFrameProps = {
  children: ReactNode;
};

export function AppFrame({ children }: AppFrameProps) {
  return (
    <div className={styles.shell}>
      <TopNavigation />
      <main className={styles.main} id="main-content">
        <div className={styles.mainInner}>{children}</div>
      </main>
    </div>
  );
}
