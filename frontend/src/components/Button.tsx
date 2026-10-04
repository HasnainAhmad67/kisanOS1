import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router-dom";

type Variant = "primary" | "secondary" | "danger";

function classNames(variant: Variant, block: boolean, extra?: string): string {
  return ["btn", `btn--${variant}`, block ? "btn--block" : "", extra ?? ""]
    .filter(Boolean)
    .join(" ");
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  block?: boolean;
}

/** Touch target ≥ 44×44px (see --touch-min in tokens.css). */
export function Button({
  variant = "primary",
  block = false,
  className,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={classNames(variant, block, className)}
      {...rest}
    />
  );
}

interface LinkButtonProps {
  to: string;
  variant?: Variant;
  block?: boolean;
  children: ReactNode;
}

/** Same visual style as Button, but a real link (keyboard/screen-reader nav). */
export function LinkButton({
  to,
  variant = "primary",
  block = false,
  children,
}: LinkButtonProps) {
  return (
    <Link to={to} className={classNames(variant, block)}>
      {children}
    </Link>
  );
}
