import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  meta?: ReactNode;
  tone?: "default" | "safety" | "info";
  children: ReactNode;
}

export function Card({ title, meta, tone = "default", children }: CardProps) {
  const toneClass = tone === "default" ? "" : ` card--${tone}`;
  return (
    <section className={`card${toneClass}`}>
      {title ? (
        <h2 className="card__title">
          {title}
          {meta ? <span className="card__meta"> — {meta}</span> : null}
        </h2>
      ) : null}
      {children}
    </section>
  );
}
