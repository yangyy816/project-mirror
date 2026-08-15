import type { AgeAssuranceResponse } from "../auth/api";
import { BrowserAuthError } from "../auth/errors";
import type { BrowserAuthSession } from "../auth/session";

const AGE_ASSURANCE_MESSAGE_TYPE = "mirror.age-assurance.result.v1";
const STATE_BYTES = 32;
const DEFAULT_TIMEOUT_MS = 5 * 60 * 1000;
const DEFAULT_CLOSE_POLL_MS = 500;

export type AgeAssuranceBridgeErrorCode =
  | "age_provider_unavailable"
  | "popup_blocked"
  | "popup_timed_out"
  | "popup_closed"
  | "popup_cancelled";

export class AgeAssuranceBridgeError extends Error {
  constructor(readonly code: AgeAssuranceBridgeErrorCode) {
    super("年龄核验未完成，请稍后重试。");
    this.name = "AgeAssuranceBridgeError";
  }
}

export type AgeAssuranceBridge = Readonly<{
  start(): Promise<AgeAssuranceResponse>;
  cancel(): void;
}>;

type MessageHandler = (event: MessageEvent<unknown>) => void;

export type PopupWindow = Readonly<{
  closed: boolean;
  close(): void;
}>;

export type BrowserPopupHost = Readonly<{
  open(url?: string, target?: string, features?: string): PopupWindow | null;
  addEventListener(type: "message", listener: MessageHandler): void;
  removeEventListener(type: "message", listener: MessageHandler): void;
  setTimeout(handler: () => void, timeout?: number): number;
  clearTimeout(handle: number): void;
  setInterval(handler: () => void, timeout?: number): number;
  clearInterval(handle: number): void;
}>;

type AgeAssuranceMessage = Readonly<{
  type: typeof AGE_ASSURANCE_MESSAGE_TYPE;
  state: string;
  credential: string;
}>;

type ActiveOperation = Readonly<{
  cancel(): void;
}>;

export type AgeAssurancePopupBridgeOptions = Readonly<{
  timeoutMs?: number;
  closePollMs?: number;
  stateFactory?: () => string;
}>;

type AgeAssuranceSession = Pick<
  BrowserAuthSession,
  "config" | "recordAgeAssurance"
>;

export function createAgeAssuranceState(): string {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi === undefined) {
    throw new BrowserAuthError("crypto_unavailable");
  }
  const bytes = new Uint8Array(STATE_BYTES);
  cryptoApi.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}

function parseMessage(value: unknown): AgeAssuranceMessage | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  const entries = Object.entries(value);
  if (
    entries.length !== 3 ||
    !Object.prototype.hasOwnProperty.call(value, "type") ||
    !Object.prototype.hasOwnProperty.call(value, "state") ||
    !Object.prototype.hasOwnProperty.call(value, "credential")
  ) {
    return null;
  }
  const candidate = value as Partial<AgeAssuranceMessage>;
  if (
    candidate.type !== AGE_ASSURANCE_MESSAGE_TYPE ||
    typeof candidate.state !== "string" ||
    candidate.state.length === 0 ||
    typeof candidate.credential !== "string" ||
    candidate.credential.length === 0
  ) {
    return null;
  }
  return {
    type: candidate.type,
    state: candidate.state,
    credential: candidate.credential,
  };
}

function providerUrl(publicUrl: string, origin: string, state: string): string {
  try {
    const url = new URL(publicUrl);
    if (
      (url.protocol !== "https:" && url.protocol !== "http:") ||
      url.origin !== origin ||
      url.username !== "" ||
      url.password !== "" ||
      url.search !== "" ||
      url.hash !== ""
    ) {
      throw new Error("unsafe provider URL");
    }
    url.searchParams.set("state", state);
    return url.toString();
  } catch {
    throw new AgeAssuranceBridgeError("age_provider_unavailable");
  }
}

/**
 * Receives a provider-neutral, one-shot age credential. The credential is
 * deliberately never stored on this class or returned to UI code.
 */
export class AgeAssurancePopupBridge implements AgeAssuranceBridge {
  private active: ActiveOperation | null = null;

  constructor(
    private readonly session: AgeAssuranceSession,
    private readonly host: BrowserPopupHost,
    private readonly options: AgeAssurancePopupBridgeOptions = {},
  ) {}

  async start(): Promise<AgeAssuranceResponse> {
    this.cancel();
    const provider = this.session.config.ageProvider;
    if (
      provider.status !== "approved" ||
      provider.publicUrl === null ||
      provider.origin === null
    ) {
      throw new AgeAssuranceBridgeError("age_provider_unavailable");
    }

    const state = (this.options.stateFactory ?? createAgeAssuranceState)();
    if (state.length === 0) {
      throw new AgeAssuranceBridgeError("age_provider_unavailable");
    }
    const url = providerUrl(provider.publicUrl, provider.origin, state);
    const popup = this.host.open(
      url,
      "mirror-age-assurance",
      "popup,width=520,height=720",
    );
    if (popup === null) {
      throw new AgeAssuranceBridgeError("popup_blocked");
    }

    return new Promise<AgeAssuranceResponse>((resolve, reject) => {
      let settled = false;
      const timeoutHandle = this.host.setTimeout(
        () =>
          finish(() => {
            popup.close();
            reject(new AgeAssuranceBridgeError("popup_timed_out"));
          }),
        this.options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
      );
      const closeHandle = this.host.setInterval(() => {
        if (popup.closed) {
          finish(() => reject(new AgeAssuranceBridgeError("popup_closed")));
        }
      }, this.options.closePollMs ?? DEFAULT_CLOSE_POLL_MS);

      const removeListeners = () => {
        this.host.removeEventListener("message", onMessage);
        this.host.clearTimeout(timeoutHandle);
        this.host.clearInterval(closeHandle);
        if (this.active === operation) {
          this.active = null;
        }
      };
      const finish = (complete: () => void) => {
        if (settled) {
          return;
        }
        settled = true;
        removeListeners();
        complete();
      };
      const onMessage: MessageHandler = (event) => {
        if (event.origin !== provider.origin || event.source !== popup) {
          return;
        }
        const message = parseMessage(event.data);
        if (message === null || message.state !== state) {
          return;
        }
        finish(() => {
          popup.close();
          void this.recordCredential(message.credential, resolve, reject);
        });
      };
      const operation: ActiveOperation = {
        cancel: () =>
          finish(() => {
            popup.close();
            reject(new AgeAssuranceBridgeError("popup_cancelled"));
          }),
      };
      this.active = operation;
      this.host.addEventListener("message", onMessage);
    });
  }

  cancel(): void {
    this.active?.cancel();
  }

  private async recordCredential(
    credential: string,
    resolve: (response: AgeAssuranceResponse) => void,
    reject: (reason: unknown) => void,
  ): Promise<void> {
    try {
      resolve(
        await this.session.recordAgeAssurance(credential, "age-assurance"),
      );
    } catch (error) {
      reject(error);
    }
  }
}

export { AGE_ASSURANCE_MESSAGE_TYPE };
