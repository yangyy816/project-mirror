import { BrowserAuthError } from "./errors";

export async function createIdempotencyKey(): Promise<string> {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi === undefined) {
    throw new BrowserAuthError("crypto_unavailable");
  }
  const bytes = new Uint8Array(16);
  cryptoApi.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}

export class IdempotencyKeyPool {
  private readonly keys = new Map<string, string>();

  async retain(logicalSubmission: string): Promise<string> {
    const existing = this.keys.get(logicalSubmission);
    if (existing !== undefined) {
      return existing;
    }
    const generated = await createIdempotencyKey();
    this.keys.set(logicalSubmission, generated);
    return generated;
  }

  restart(logicalSubmission: string): void {
    this.keys.delete(logicalSubmission);
  }
}
