import type { ReactNode } from "react";

export function Unknown({ children }: { children?: ReactNode }) {
  if (children === undefined || children === null || children === "") {
    return <span className="unknown">Unknown</span>;
  }
  return <>{children}</>;
}

export function NotAvailable() {
  return <span className="unknown">Not available</span>;
}
