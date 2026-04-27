import styles from "./PortfolioBanner.module.css";

const personalLinks = [
  {
    href: "https://github.com/NikitaPirate",
    label: "GitHub",
  },
  {
    href: "https://x.com/NikitaPirate",
    label: "X",
  },
  {
    href: "https://t.me/nikita_ko",
    label: "Telegram",
  },
];

export function PortfolioBanner() {
  return (
    <aside className={styles.banner} aria-label="Portfolio notice">
      <div className={styles.inner}>
        <p className={styles.copy}>
          <span className={styles.author}>Built by Nikita-K</span>
          <span className={styles.message}>open to Python backend / data engineering roles</span>
        </p>

        <nav className={styles.links} aria-label="Personal links">
          {personalLinks.map((link) => (
            <a className={styles.link} href={link.href} key={link.href} rel="noreferrer" target="_blank">
              {link.label}
            </a>
          ))}
        </nav>
      </div>
    </aside>
  );
}
