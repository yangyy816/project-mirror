import { describe, expect, it, vi } from "vitest";

import type { AgeAssuranceResponse } from "../auth/api";
import type { WebAuthConfig } from "../web-auth-config";

import {
  AGE_ASSURANCE_MESSAGE_TYPE,
  AgeAssuranceBridgeError,
  AgeAssurancePopupBridge,
  type BrowserPopupHost,
  type PopupWindow,
} from "./age-assurance-bridge";

const config: WebAuthConfig = {
  appEnv: "test",
  apiBaseUrl: "http://api.test",
  appOrigin: "http://app.test",
  policyManifest: [],
  ageProvider: {
    status: "approved",
    publicUrl: "https://age.test/verify",
    origin: "https://age.test",
  },
};

const response: AgeAssuranceResponse = {
  record_id: "age-record",
  result: "verified",
  activated: false,
};

class FakePopup implements PopupWindow {
  closed = false;
  readonly close = vi.fn(() => {
    this.closed = true;
  });
}

class FakePopupHost implements BrowserPopupHost {
  readonly popup = new FakePopup();
  readonly open = vi.fn((): PopupWindow | null => this.popup);
  private messageHandler: ((event: MessageEvent<unknown>) => void) | null =
    null;
  private timeoutHandler: (() => void) | null = null;
  private intervalHandler: (() => void) | null = null;

  addEventListener(
    _type: "message",
    listener: (event: MessageEvent<unknown>) => void,
  ): void {
    this.messageHandler = listener;
  }

  removeEventListener(
    _type: "message",
    listener: (event: MessageEvent<unknown>) => void,
  ): void {
    if (this.messageHandler === listener) this.messageHandler = null;
  }

  setTimeout(handler: () => void): number {
    this.timeoutHandler = handler;
    return 1;
  }

  clearTimeout(): void {
    this.timeoutHandler = null;
  }

  setInterval(handler: () => void): number {
    this.intervalHandler = handler;
    return 2;
  }

  clearInterval(): void {
    this.intervalHandler = null;
  }

  emit(
    data: unknown,
    origin = "https://age.test",
    source: unknown = this.popup,
  ) {
    this.messageHandler?.({ data, origin, source } as MessageEvent<unknown>);
  }

  timeout(): void {
    this.timeoutHandler?.();
  }

  pollClosed(): void {
    this.intervalHandler?.();
  }
}

function createSession() {
  return {
    config,
    recordAgeAssurance: vi.fn(async () => response),
  };
}

function message(state: string, credential = "one-shot-credential") {
  return {
    type: AGE_ASSURANCE_MESSAGE_TYPE,
    state,
    credential,
  };
}

describe("AgeAssurancePopupBridge", () => {
  it("accepts only the exact origin, popup, state, and message schema", async () => {
    const host = new FakePopupHost();
    const session = createSession();
    const bridge = new AgeAssurancePopupBridge(session, host, {
      stateFactory: () => "expected-state",
    });
    const result = bridge.start();

    host.emit(message("expected-state"), "https://wrong.test");
    host.emit(message("expected-state"), "https://age.test", {});
    host.emit(message("wrong-state"));
    host.emit({ ...message("expected-state"), extra: true });
    expect(session.recordAgeAssurance).not.toHaveBeenCalled();

    host.emit(message("expected-state"));
    await expect(result).resolves.toEqual(response);
    expect(session.recordAgeAssurance).toHaveBeenCalledOnce();
    expect(session.recordAgeAssurance).toHaveBeenCalledWith(
      "one-shot-credential",
      "age-assurance",
    );
    expect(host.popup.close).toHaveBeenCalledOnce();

    host.emit(message("expected-state", "late-credential"));
    expect(session.recordAgeAssurance).toHaveBeenCalledOnce();
    expect(JSON.stringify(bridge)).not.toContain("one-shot-credential");
  });

  it("fails explicitly when the popup is blocked", async () => {
    const host = new FakePopupHost();
    host.open.mockReturnValueOnce(null);
    const bridge = new AgeAssurancePopupBridge(createSession(), host, {
      stateFactory: () => "expected-state",
    });

    await expect(bridge.start()).rejects.toMatchObject({
      code: "popup_blocked",
    } satisfies Partial<AgeAssuranceBridgeError>);
  });

  it("closes and rejects a timed-out popup", async () => {
    const host = new FakePopupHost();
    const bridge = new AgeAssurancePopupBridge(createSession(), host, {
      stateFactory: () => "expected-state",
    });
    const result = bridge.start();

    host.timeout();

    await expect(result).rejects.toMatchObject({ code: "popup_timed_out" });
    expect(host.popup.close).toHaveBeenCalledOnce();
  });

  it("rejects popup close and explicit cancellation without accepting a credential", async () => {
    const closedHost = new FakePopupHost();
    const closedSession = createSession();
    const closedBridge = new AgeAssurancePopupBridge(
      closedSession,
      closedHost,
      {
        stateFactory: () => "expected-state",
      },
    );
    const closedResult = closedBridge.start();
    closedHost.popup.closed = true;
    closedHost.pollClosed();
    await expect(closedResult).rejects.toMatchObject({ code: "popup_closed" });
    expect(closedSession.recordAgeAssurance).not.toHaveBeenCalled();

    const cancelledHost = new FakePopupHost();
    const cancelledSession = createSession();
    const cancelledBridge = new AgeAssurancePopupBridge(
      cancelledSession,
      cancelledHost,
      { stateFactory: () => "expected-state" },
    );
    const cancelledResult = cancelledBridge.start();
    cancelledBridge.cancel();
    await expect(cancelledResult).rejects.toMatchObject({
      code: "popup_cancelled",
    });
    expect(cancelledHost.popup.close).toHaveBeenCalledOnce();
    expect(cancelledSession.recordAgeAssurance).not.toHaveBeenCalled();
  });

  it("rejects an unsafe or unapproved provider configuration", async () => {
    const host = new FakePopupHost();
    const unavailable = {
      ...createSession(),
      config: {
        ...config,
        ageProvider: {
          status: "unconfigured" as const,
          publicUrl: null,
          origin: null,
        },
      },
    };
    await expect(
      new AgeAssurancePopupBridge(unavailable, host).start(),
    ).rejects.toMatchObject({ code: "age_provider_unavailable" });

    const unsafe = {
      ...createSession(),
      config: {
        ...config,
        ageProvider: {
          status: "approved" as const,
          publicUrl: "https://age.test/verify?credential=leak",
          origin: "https://age.test",
        },
      },
    };
    await expect(
      new AgeAssurancePopupBridge(unsafe, host).start(),
    ).rejects.toMatchObject({ code: "age_provider_unavailable" });
  });
});
