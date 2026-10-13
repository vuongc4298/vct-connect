import { ClerkProvider } from "@clerk/nextjs";
import { viVN } from "@clerk/localizations";
import type { ReactNode } from "react";
import "./style.css";

export default function Layout({ children }: { children: ReactNode }) {
  return <html lang="vi"><body><ClerkProvider localization={viVN}>{children}</ClerkProvider></body></html>;
}
