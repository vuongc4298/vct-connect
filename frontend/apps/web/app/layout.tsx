import { ClerkProvider } from "@clerk/nextjs";
import type { ReactNode } from "react";
import "./style.css";

export default function Layout({ children }: { children: ReactNode }) {
  return <html lang="vi"><body><ClerkProvider>{children}</ClerkProvider></body></html>;
}
