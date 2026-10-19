import { ClerkProvider } from "@clerk/nextjs";
import { viVN } from "@clerk/localizations";
import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./style.css";

export const metadata: Metadata = {
  title: "VCT Connect",
  icons: { icon: { url: "/vct-icon.ico", type: "image/x-icon", sizes: "56x56" } },
};

export const viewport: Viewport = { themeColor: "#09234c" };

export default function Layout({ children }: { children: ReactNode }) {
  return <html lang="vi"><body><ClerkProvider localization={viVN}>{children}</ClerkProvider></body></html>;
}
