import type { Metadata } from "next";
import type { ReactNode } from "react";

import { BrowserAuthProvider } from "../lib/auth";
import { getWebAuthConfig } from "../lib/web-auth-config";

import "./globals.css";

export const metadata: Metadata = {
  title: "Project Mirror",
  description: "长期个人审美记忆驱动的 AI 修图助手",
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  const authConfig = getWebAuthConfig();
  return (
    <html lang="zh-CN">
      <body>
        <BrowserAuthProvider config={authConfig}>
          {children}
        </BrowserAuthProvider>
      </body>
    </html>
  );
}
