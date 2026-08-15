"use client";

import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
} from "react";

import type { WebAuthConfig } from "../web-auth-config";

import { GeneratedBrowserAuthApi } from "./api";
import { BrowserAuthSession } from "./session";
import type { BrowserSessionSnapshot } from "./session";

type BrowserAuthRuntime = Readonly<{
  session: BrowserAuthSession;
  snapshot: BrowserSessionSnapshot;
}>;

const serverSnapshot: BrowserSessionSnapshot = {
  status: "bootstrapping",
  user: null,
  error: null,
};

const BrowserAuthContext = createContext<BrowserAuthRuntime | null>(null);

export function BrowserAuthProvider({
  children,
  config,
  session: suppliedSession,
}: Readonly<{
  children: ReactNode;
  config: WebAuthConfig;
  session?: BrowserAuthSession;
}>) {
  const [session] = useState(() => {
    if (suppliedSession !== undefined) return suppliedSession;
    const api = new GeneratedBrowserAuthApi(config);
    return new BrowserAuthSession(api, config, api);
  });
  const snapshot = useSyncExternalStore(
    (listener) => session.subscribe(listener),
    () => session.getSnapshot(),
    () => serverSnapshot,
  );

  useEffect(() => {
    void session.bootstrap();
  }, [session]);

  return (
    <BrowserAuthContext.Provider value={{ session, snapshot }}>
      {children}
    </BrowserAuthContext.Provider>
  );
}

export function useBrowserAuth(): BrowserAuthRuntime {
  const runtime = useContext(BrowserAuthContext);
  if (runtime === null) {
    throw new Error("BrowserAuthProvider is required");
  }
  return runtime;
}
