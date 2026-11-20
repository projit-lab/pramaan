/**
 * Checking a Pramaan mandate's Cloud KMS countersignature, in the browser.
 *
 * This is the one piece of the web lane that must not take Pramaan's word for
 * anything. An auditor or a payee runs it on their own machine, against bytes we
 * handed them and a public key they can fetch themselves. A breach of our servers
 * cannot forge a countersignature that this code would accept, because the
 * private key never leaves Cloud HSM.
 *
 * Two traps, both called out in the build plan's risk table:
 *
 *   1. **Cloud KMS returns a DER signature; WebCrypto wants raw r||s, 64 bytes.**
 *      Feed DER straight to WebCrypto and every genuine mandate reads as invalid.
 *      derToRawSignature below does the conversion.
 *
 *   2. **The bytes must be the exact bytes that were signed.** We do not rebuild
 *      the canonical form here. Re-implementing "keys sorted by code point, no
 *      whitespace, every value a string, NFC-normalised" in TypeScript, beside
 *      the Kotlin and Python implementations, would drift, and the first symptom
 *      would be this page calling a genuine mandate invalid on stage. So the API
 *      returns canonical_b64 and we hash precisely that.
 *
 * No Firebase, no React, no DOM beyond WebCrypto: this module is deep-imported by
 * the public verifier page, which ships no Firebase SDK at all.
 */

/** Why a mandate did not verify, or that it did. */
export type VerificationOutcome =
  | 'valid'
  | 'invalid_signature'
  | 'expired'
  | 'not_found'
  | 'cannot_check';

export interface VerificationResult {
  outcome: VerificationOutcome;
  /** One sentence for the screen. Never speculates about fraud. */
  detail: string;
  /** SHA-256 of the canonical bytes, hex, when we had bytes to hash. */
  canonicalSha256?: string;
  /** The key version that signed, when the mandate named one. */
  keyVersion?: string;
  /** When the mandate expired, when it carried an expiry. */
  expiresAt?: string;
}

// ---------------------------------------------------------------- base64

/** Decodes standard or URL-safe base64 into bytes. */
export function base64ToBytes(value: string): Uint8Array {
  const normalised = value.replace(/-/g, '+').replace(/_/g, '/').replace(/\s+/g, '');
  const padded = normalised.padEnd(Math.ceil(normalised.length / 4) * 4, '=');
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

export function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

/** SHA-256 of some bytes, as lower-case hex. */
export async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', bytes as BufferSource);
  return bytesToHex(new Uint8Array(digest));
}

// ------------------------------------------------------------------- DER

export class SignatureFormatError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'SignatureFormatError';
  }
}

/**
 * Converts an ECDSA signature from DER to the raw r||s form WebCrypto expects.
 *
 * DER shape: 30 <len> 02 <rlen> <r> 02 <slen> <s>
 *
 * The integers are signed and big-endian, so each may carry a leading 0x00 to
 * keep it positive, or be shorter than 32 bytes when it has leading zero bits.
 * Both are normalised to exactly 32 bytes here, which is where naive
 * implementations go wrong and produce signatures that fail roughly one time in
 * every few hundred.
 */
export function derToRawSignature(der: Uint8Array, componentLength = 32): Uint8Array {
  let offset = 0;

  const byteAt = (index: number): number => {
    const value = der[index];
    if (value === undefined) {
      throw new SignatureFormatError('The DER signature ended early.');
    }
    return value;
  };

  if (byteAt(offset) !== 0x30) {
    throw new SignatureFormatError('Not a DER sequence; this is not a KMS signature.');
  }
  offset += 1;

  // Length, short or long form. A P-256 signature is well under 128 bytes, but
  // handle the long form rather than quietly misreading it.
  let sequenceLength = byteAt(offset);
  offset += 1;
  if (sequenceLength & 0x80) {
    const lengthBytes = sequenceLength & 0x7f;
    if (lengthBytes === 0 || lengthBytes > 2) {
      throw new SignatureFormatError('The DER sequence length is malformed.');
    }
    sequenceLength = 0;
    for (let index = 0; index < lengthBytes; index += 1) {
      sequenceLength = (sequenceLength << 8) | byteAt(offset);
      offset += 1;
    }
  }

  if (offset + sequenceLength !== der.length) {
    throw new SignatureFormatError('The DER sequence length does not match the data.');
  }

  const readInteger = (): Uint8Array => {
    if (byteAt(offset) !== 0x02) {
      throw new SignatureFormatError('Expected a DER integer in the signature.');
    }
    offset += 1;
    const length = byteAt(offset);
    offset += 1;
    if (length === 0 || length & 0x80) {
      throw new SignatureFormatError('The DER integer length is malformed.');
    }
    if (offset + length > der.length) {
      throw new SignatureFormatError('A DER integer runs past the end of the signature.');
    }
    const value = der.slice(offset, offset + length);
    offset += length;
    return value;
  };

  const r = readInteger();
  const s = readInteger();

  const pad = (value: Uint8Array): Uint8Array => {
    // Drop the sign byte DER adds to keep a high-bit-set integer positive.
    let start = 0;
    while (start < value.length - 1 && value[start] === 0x00) start += 1;
    const trimmed = value.slice(start);
    if (trimmed.length > componentLength) {
      throw new SignatureFormatError('A signature component is larger than the curve allows.');
    }
    const out = new Uint8Array(componentLength);
    out.set(trimmed, componentLength - trimmed.length);
    return out;
  };

  const raw = new Uint8Array(componentLength * 2);
  raw.set(pad(r), 0);
  raw.set(pad(s), componentLength);
  return raw;
}

/** True when the bytes already look like a raw r||s signature rather than DER. */
export function looksLikeRawSignature(bytes: Uint8Array): boolean {
  return bytes.length === 64 && bytes[0] !== 0x30;
}

// ------------------------------------------------------------------- PEM

export class PublicKeyFormatError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'PublicKeyFormatError';
  }
}

/** Strips the PEM armour and returns the SubjectPublicKeyInfo bytes. */
export function pemToSpki(pem: string): Uint8Array {
  const match = /-----BEGIN PUBLIC KEY-----([\s\S]*?)-----END PUBLIC KEY-----/.exec(pem);
  if (!match || !match[1]) {
    throw new PublicKeyFormatError('That is not a PEM-encoded public key.');
  }
  try {
    return base64ToBytes(match[1]);
  } catch {
    throw new PublicKeyFormatError('The PEM body is not valid base64.');
  }
}

/** Imports the KMS countersigning key for ECDSA P-256 verification. */
export async function importCountersignKey(pem: string): Promise<CryptoKey> {
  const spki = pemToSpki(pem);
  try {
    return await crypto.subtle.importKey(
      'spki',
      spki as BufferSource,
      { name: 'ECDSA', namedCurve: 'P-256' },
      false,
      ['verify'],
    );
  } catch {
    throw new PublicKeyFormatError('That key is not an ECDSA P-256 public key.');
  }
}

// ---------------------------------------------------------------- verify

export interface VerifyInput {
  /** The exact bytes that were countersigned, base64. From canonical_b64. */
  canonicalB64: string;
  /** The countersignature, base64 of DER as Cloud KMS returns it. */
  signatureB64: string;
  /** The KMS public key, PEM. From GET /keys/countersign. */
  publicKeyPem: string;
  /** The mandate's expiry, if it carried one. */
  expiresAt?: string | null;
  keyVersion?: string | null;
  /** Overridable so tests do not depend on the clock. */
  now?: Date;
}

/**
 * Verifies a countersignature.
 *
 * Expiry is reported separately from the signature, and the signature is checked
 * first: an expired mandate whose signature is genuine is a different fact from
 * one that never verified, and an auditor needs to be told which.
 */
export async function verifyCountersignature(input: VerifyInput): Promise<VerificationResult> {
  let canonicalBytes: Uint8Array;
  let signatureBytes: Uint8Array;

  try {
    canonicalBytes = base64ToBytes(input.canonicalB64);
  } catch {
    return {
      outcome: 'cannot_check',
      detail: 'The signed bytes are not valid base64, so there is nothing to check.',
    };
  }

  if (canonicalBytes.length === 0) {
    return {
      outcome: 'cannot_check',
      detail: 'This mandate did not come with the bytes that were signed, so it cannot be checked here.',
    };
  }

  try {
    signatureBytes = base64ToBytes(input.signatureB64);
  } catch {
    return {
      outcome: 'cannot_check',
      detail: 'The countersignature is not valid base64.',
    };
  }

  const canonicalSha256 = await sha256Hex(canonicalBytes);

  let key: CryptoKey;
  try {
    key = await importCountersignKey(input.publicKeyPem);
  } catch (error) {
    return {
      outcome: 'cannot_check',
      detail:
        error instanceof Error
          ? `Could not read Pramaan's public key. ${error.message}`
          : "Could not read Pramaan's public key.",
      canonicalSha256,
    };
  }

  let raw: Uint8Array;
  try {
    // Cloud KMS returns DER. Accept an already-raw signature too, so a mandate
    // handed over in either shape still checks.
    raw = looksLikeRawSignature(signatureBytes)
      ? signatureBytes
      : derToRawSignature(signatureBytes);
  } catch (error) {
    return {
      outcome: 'invalid_signature',
      detail:
        error instanceof Error
          ? `The countersignature is malformed. ${error.message}`
          : 'The countersignature is malformed.',
      canonicalSha256,
    };
  }

  let signatureOk: boolean;
  try {
    signatureOk = await crypto.subtle.verify(
      { name: 'ECDSA', hash: 'SHA-256' },
      key,
      raw as BufferSource,
      canonicalBytes as BufferSource,
    );
  } catch {
    return {
      outcome: 'cannot_check',
      detail: 'This browser could not run the signature check.',
      canonicalSha256,
    };
  }

  const common = {
    canonicalSha256,
    ...(input.keyVersion ? { keyVersion: input.keyVersion } : {}),
    ...(input.expiresAt ? { expiresAt: input.expiresAt } : {}),
  };

  if (!signatureOk) {
    return {
      outcome: 'invalid_signature',
      detail:
        'Pramaan did not sign these details. The mandate does not match its countersignature.',
      ...common,
    };
  }

  if (input.expiresAt) {
    const expiry = new Date(input.expiresAt);
    const now = input.now ?? new Date();
    if (!Number.isNaN(expiry.getTime()) && expiry.getTime() <= now.getTime()) {
      return {
        outcome: 'expired',
        detail:
          'The countersignature is genuine, but this mandate has expired and can no longer release a payment.',
        ...common,
      };
    }
  }

  return {
    outcome: 'valid',
    detail: 'Pramaan countersigned exactly these payment details.',
    ...common,
  };
}
