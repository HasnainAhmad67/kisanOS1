import type { ReactNode } from "react";

interface AlertProps {
  tone?: "error" | "info" | "success";
  children: ReactNode;
}

/** Inline message strip; errors announce via role="alert". */
export function Alert({ tone = "error", children }: AlertProps) {
  return (
    <div
      className={`alert alert--${tone}`}
      role={tone === "error" ? "alert" : "status"}
    >
      {children}
    </div>
  );
}
