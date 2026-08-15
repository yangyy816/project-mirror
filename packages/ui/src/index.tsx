import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary";
}) {
  const colors =
    variant === "primary"
      ? "bg-plum text-white hover:bg-plum/90"
      : "border border-black/15 bg-white/70 text-ink hover:bg-white";
  return (
    <button
      className={`rounded-full px-5 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${colors} ${className}`}
      {...props}
    />
  );
}

export function Badge({
  children,
  tone,
}: {
  children: ReactNode;
  tone: "success" | "warning";
}) {
  const colors =
    tone === "success"
      ? "bg-emerald-100 text-emerald-800"
      : "bg-amber-100 text-amber-800";
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${colors}`}>
      {children}
    </span>
  );
}
