// lib/radar/verify.ts
// HMAC-SHA256 verification of the raw request body from Opportunity Radar.
// Radar signs HMAC_SHA256(LEARNFORGE_WEBHOOK_SECRET, rawBodyBytes) as lowercase
// hex. Verify over the exact bytes received (req.text()) — never re-serialize.

import crypto from "crypto";

export function computeSignature(secret: string, rawBody: string): string {
  return crypto
    .createHmac("sha256", secret)
    .update(rawBody, "utf8")
    .digest("hex");
}

/**
 * Non-reversible fingerprint of the shared secret: sha256(secret) hex prefix.
 * Safe to return in a 401 body so Radar can show an exact MATCH/MISMATCH
 * against its own signing fingerprint. NEVER return the secret value itself.
 * Must match Radar's computation: sha256(secret).hexdigest()[:8].
 */
export function secretFingerprint(secret: string | undefined): string {
  if (!secret) return "unset";
  return crypto.createHash("sha256").update(secret, "utf8").digest("hex").slice(0, 8);
}

/** Constant-time compare of the received signature against the expected one. */
export function verifyRadarSignature(
  rawBody: string,
  receivedSignature: string | null,
  secret: string | undefined
): boolean {
  if (!secret) {
    // Fail closed: never accept unsigned briefs when a secret is expected.
    return false;
  }
  if (!receivedSignature) return false;

  const expected = computeSignature(secret, rawBody);
  const a = Buffer.from(expected, "utf8");
  const b = Buffer.from(receivedSignature.trim().toLowerCase(), "utf8");
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}
