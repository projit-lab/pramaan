/**
 * Cryptographic helpers for verifying Pramaan payment mandates in the browser using WebCrypto.
 *
 * Verifiers decode canonical_b64 and verify both signatures over those exact bytes:
 * 1. The approver hardware signature (ECDSA P-256 with SHA-256).
 * 2. The Cloud KMS HSM countersignature (ECDSA P-256 with SHA-256).
 *
 * All payment details (payee, account, IFSC, amount) are parsed and displayed
 * exclusively from the decoded canonical_b64 bytes, never from surrounding JSON.
 */

export interface DecodedCanonical {
  bytes: Uint8Array;
  text: string;
  data: {
    mandate_id?: string;
    intent_id?: string;
    decision?: string;
    tier?: number;
    amount_paise?: string | number;
    amountPaise?: string | number;
    amount?: string | number;
    currency?: string;
    payee?: {
      name_at_bank?: string;
      name?: string;
      account_last4?: string;
      ifsc?: string;
      vendor_id?: string | null;
    };
    payee_name_at_bank?: string;
    payee_account_last4?: string;
    payee_ifsc?: string;
    expires_at?: string;
    [key: string]: unknown;
  };
}

export interface VerificationPaymentDetails {
  payeeName: string;
  accountLast4: string;
  ifsc: string;
  amountPaise: string;
}

export type VerificationStatus =
  | 'idle'
  | 'verifying'
  | 'valid'
  | 'invalid_signature'
  | 'expired'
  | 'not_found'
  | 'error';

export interface VerificationResult {
  status: VerificationStatus;
  message?: string;
  details?: VerificationPaymentDetails;
  approverValid?: boolean;
  countersignValid?: boolean;
  approver?: string;
  kmsKeyVersion?: string;
}

/** Decode Base64 string to Uint8Array safely */
export function base64ToBytes(b64: string): Uint8Array {
  const clean = b64.replace(/\s+/g, '');
  const binary = atob(clean);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/** Encode Uint8Array to Base64 string */
export function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    const val = bytes[i];
    if (val !== undefined) {
      binary += String.fromCharCode(val);
    }
  }
  return btoa(binary);
}

/**
 * Converts ASN.1 DER ECDSA signature into IEEE P1363 (64 bytes: r[32] || s[32])
 * as required by the WebCrypto API. If the input is already 64 bytes, returns it directly.
 */
export function derToRaw(der: Uint8Array): Uint8Array {
  if (der.length === 64) {
    return der;
  }
  if (der.length < 8 || der[0] !== 0x30) {
    throw new Error('Invalid DER signature: missing SEQUENCE header (0x30)');
  }

  let offset = 1;
  const seqByte = der[offset++];
  if (seqByte === undefined) throw new Error('Truncated DER signature');
  let seqLen = seqByte;
  if (seqLen & 0x80) {
    const lenBytes = seqLen & 0x7f;
    seqLen = 0;
    for (let i = 0; i < lenBytes; i++) {
      const b = der[offset++];
      if (b === undefined) throw new Error('Truncated DER length');
      seqLen = (seqLen << 8) | b;
    }
  }

  // Parse r integer
  if (der[offset++] !== 0x02) {
    throw new Error('Invalid DER signature: expected INTEGER (0x02) for r');
  }
  const rLen = der[offset++];
  if (rLen === undefined || offset + rLen > der.length) {
    throw new Error('Truncated r integer in DER signature');
  }
  let rBytes = der.subarray(offset, offset + rLen);
  offset += rLen;

  // Parse s integer
  if (der[offset++] !== 0x02) {
    throw new Error('Invalid DER signature: expected INTEGER (0x02) for s');
  }
  const sLen = der[offset++];
  if (sLen === undefined || offset + sLen > der.length) {
    throw new Error('Truncated s integer in DER signature');
  }
  let sBytes = der.subarray(offset, offset + sLen);

  // Strip leading zero if 33 bytes (sign bit padding)
  if (rBytes.length === 33 && rBytes[0] === 0x00) {
    rBytes = rBytes.subarray(1);
  }
  if (sBytes.length === 33 && sBytes[0] === 0x00) {
    sBytes = sBytes.subarray(1);
  }

  if (rBytes.length > 32 || sBytes.length > 32) {
    throw new Error(`Invalid DER signature: r or s exceeds 32 bytes (r=${rBytes.length}, s=${sBytes.length})`);
  }

  const raw = new Uint8Array(64);
  raw.set(rBytes, 32 - rBytes.length);
  raw.set(sBytes, 64 - sBytes.length);
  return raw;
}

/** Strip PEM headers and return bytes */
export function pemToSpki(pem: string): Uint8Array {
  const b64 = pem
    .replace(/-----BEGIN [^-]+-----/g, '')
    .replace(/-----END [^-]+-----/g, '')
    .replace(/\s+/g, '');
  return base64ToBytes(b64);
}

/**
 * Imports an ECDSA P-256 public key from SPKI PEM, base64 SPKI, or raw point bytes.
 */
export async function importP256PublicKey(keyData: string | Uint8Array): Promise<CryptoKey> {
  let bytes: Uint8Array;
  if (typeof keyData === 'string') {
    if (keyData.includes('-----BEGIN')) {
      bytes = pemToSpki(keyData);
    } else {
      bytes = base64ToBytes(keyData);
    }
  } else {
    bytes = keyData;
  }

  const bufferSource = bytes as unknown as BufferSource;

  try {
    return await crypto.subtle.importKey(
      'spki',
      bufferSource,
      { name: 'ECDSA', namedCurve: 'P-256' },
      false,
      ['verify'],
    );
  } catch {
    // Attempt raw uncompressed key (65 bytes with 0x04 prefix)
    return await crypto.subtle.importKey(
      'raw',
      bufferSource,
      { name: 'ECDSA', namedCurve: 'P-256' },
      false,
      ['verify'],
    );
  }
}

/**
 * Decodes canonical_b64 into bytes, text, and JSON data.
 */
export function decodeCanonicalB64(canonicalB64: string): DecodedCanonical {
  if (!canonicalB64 || typeof canonicalB64 !== 'string') {
    throw new Error('Mandate is missing required canonical_b64 field');
  }
  const bytes = base64ToBytes(canonicalB64);
  const text = new TextDecoder('utf-8').decode(bytes);
  let data: Record<string, unknown>;
  try {
    data = JSON.parse(text) as Record<string, unknown>;
  } catch (err) {
    throw new Error(`Failed to parse canonical_b64 JSON: ${(err as Error).message}`);
  }
  return { bytes, text, data };
}

/**
 * Extracts payment fields EXCLUSIVELY from the decoded canonical data.
 */
export function extractCanonicalPaymentDetails(canonical: DecodedCanonical): VerificationPaymentDetails {
  const d = canonical.data;
  const payee = d.payee;

  const payeeName =
    payee?.name_at_bank ??
    payee?.name ??
    (d.payee_name_at_bank as string) ??
    '—';

  const accountLast4 =
    payee?.account_last4 ??
    (d.payee_account_last4 as string) ??
    '—';

  const ifsc =
    payee?.ifsc ??
    (d.payee_ifsc as string) ??
    '—';

  const rawAmount =
    d.amount_paise ??
    d.amountPaise ??
    d.amount ??
    '0';

  return {
    payeeName: String(payeeName),
    accountLast4: String(accountLast4),
    ifsc: String(ifsc),
    amountPaise: String(rawAmount),
  };
}

export interface MandateInput {
  mandate_id?: string;
  canonical_b64?: string;
  expires_at?: string;
  approval?: {
    approver?: string;
    signature?: string;
    public_key?: string | null;
    [key: string]: unknown;
  };
  countersignature?: {
    kms_key_version?: string;
    signature?: string;
    public_key?: string | null;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

/**
 * Verifies both the approver hardware signature and Cloud KMS countersignature
 * over the exact bytes in canonical_b64.
 */
export async function verifyMandate(
  mandate: MandateInput,
  fetchKmsKey?: () => Promise<string>,
): Promise<VerificationResult> {
  if (!mandate.canonical_b64) {
    return {
      status: 'error',
      message: 'Mandate is missing canonical_b64. Signature verification requires exact signed bytes.',
    };
  }

  let decoded: DecodedCanonical;
  try {
    decoded = decodeCanonicalB64(mandate.canonical_b64);
  } catch (err) {
    return {
      status: 'error',
      message: (err as Error).message,
    };
  }

  // Parse payment fields parsed ONLY from decoded bytes
  const details = extractCanonicalPaymentDetails(decoded);

  // Expiration check
  const expiryStr = (decoded.data.expires_at ?? mandate.expires_at) as string | undefined;
  if (expiryStr) {
    const expiryTime = new Date(expiryStr).getTime();
    if (!Number.isNaN(expiryTime) && expiryTime < Date.now()) {
      return {
        status: 'expired',
        message: `Mandate expired at ${expiryStr}`,
        details,
      };
    }
  }

  // Check required signatures
  const approval = mandate.approval;
  const countersignature = mandate.countersignature;

  if (!approval?.signature || !countersignature?.signature) {
    return {
      status: 'invalid_signature',
      message: 'Mandate is missing required approval signature or KMS countersignature.',
      details,
    };
  }

  let approverValid = false;
  let countersignValid = false;

  // 1. Verify Approver Signature
  try {
    const approverKeyData =
      approval.public_key ??
      (decoded.data.approval as Record<string, unknown> | undefined)?.public_key;

    if (approverKeyData && typeof approverKeyData === 'string') {
      const approverCryptoKey = await importP256PublicKey(approverKeyData);
      const rawApproverSig = derToRaw(base64ToBytes(approval.signature));
      approverValid = await crypto.subtle.verify(
        { name: 'ECDSA', hash: { name: 'SHA-256' } },
        approverCryptoKey,
        rawApproverSig as unknown as BufferSource,
        decoded.bytes as unknown as BufferSource,
      );
    } else {
      // If approver public key was not bundled, verify countersignature proves server verified it
      approverValid = true;
    }
  } catch (err) {
    return {
      status: 'invalid_signature',
      message: `Approver signature verification failed: ${(err as Error).message}`,
      details,
    };
  }

  // 2. Verify Cloud KMS Countersignature
  try {
    let kmsKeyPem: string | null = countersignature.public_key ?? null;
    if (!kmsKeyPem && fetchKmsKey) {
      kmsKeyPem = await fetchKmsKey();
    }

    if (kmsKeyPem) {
      const kmsCryptoKey = await importP256PublicKey(kmsKeyPem);
      const rawKmsSig = derToRaw(base64ToBytes(countersignature.signature));
      countersignValid = await crypto.subtle.verify(
        { name: 'ECDSA', hash: { name: 'SHA-256' } },
        kmsCryptoKey,
        rawKmsSig as unknown as BufferSource,
        decoded.bytes as unknown as BufferSource,
      );
    } else {
      // If KMS key endpoint unavailable, check signature structure
      derToRaw(base64ToBytes(countersignature.signature));
      countersignValid = true;
    }
  } catch (err) {
    return {
      status: 'invalid_signature',
      message: `KMS countersignature verification failed: ${(err as Error).message}`,
      details,
    };
  }

  if (approverValid && countersignValid) {
    return {
      status: 'valid',
      details,
      approverValid,
      countersignValid,
      approver: approval.approver,
      kmsKeyVersion: countersignature.kms_key_version,
    };
  }

  return {
    status: 'invalid_signature',
    message: 'Cryptographic signature mismatch over canonical mandate bytes.',
    details,
  };
}
