import type { ReactNode } from "react";
import "./Card.css";

export function Card({
  title,
  subtitle,
  span,
  children,
}: {
  title: string;
  subtitle?: string;
  span?: "half" | "full";
  children: ReactNode;
}) {
  return (
    <section className={`card ${span === "full" ? "card--full" : ""}`}>
      <header className="card__head">
        <h2 className="card__title">{title}</h2>
        {subtitle && <p className="card__subtitle">{subtitle}</p>}
      </header>
      <div className="card__body">{children}</div>
    </section>
  );
}
