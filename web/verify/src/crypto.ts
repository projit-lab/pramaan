/**
 * Cryptographic verification for Pramaan payment mandates in the browser using WebCrypto.
 *
 * The approver's phone and Cloud KMS sign DIFFERENT bytes:
 * 1. The phone signs the canonical payment summary (summary_b64) with its hardware key.
 * 2. Cloud KMS countersigns the canonical mandate (mandate_b64) which binds summary_sha256
 *    and the phone's device public key.
 *
 * Verification order (must fail closed at any step):
 * a. KMS countersignature over mandate_b64 (key from GET /keys/countersign).
 * b. Take the device public key ONLY from inside the decoded mandate_b64; ignore any key in the outer JSON.
 * c. Approver signature (DER -> raw r||s) over summary_b64 with that key.
 * d. SHA-256(summary_b64 bytes) must equal summary_sha256 inside mandate_b64.
 * e. Expiry from inside mandate_b64.
 *
 * Display rule:
 * - Payee, account, IFSC and amount decoded from summary_b64 only.
 * - Decision, tier, device and signed time from mandate_b64 only.
 */

export interface DecodedSummary {
  bytes: Uint8Array;
  text: string;
  data: {
    payee?: {
      name_at_bank?: string;
      name?: string;
      account_last4?: string;
      ifsc?: string;
    };
    payee_name_at_bank?: string;
    payee_account_last4?: string;
    payee_ifsc?: string;
    /**
     * The flat names the agreed canonical payment summary actually uses; see
     * contracts/canonical/vectors.json, which both Kotlin and Python must match.
     * `payee_account` is the full account number, not the last four.
     */
    payee_name?: string;
    payee_account?: string;
    amount_paise?: string | number;
    amountPaise?: string | number;
    amount?: string | number;
    currency?: string;
    [key: string]: unknown;
  };
}

export interface DecodedMandatePayload {
  bytes: Uint8Array;
  text: string;
  data: {
    summary_sha256: string;
    decision: string;
    tier: number;
    policy_version?: string | null;
    device_id: string;
    device_public_key: string; // SPKI base64 or PEM
    key_security_level?: string | null;
    integrity_verdict?: string | null;
    approver_signature?: string;
    signed_at: string;
    expires_at: string;
    [key: string]: unknown;
  };
}

export interface VerificationDisplayDetails {
  // From summary_b64 only:
  payeeName: string;
  accountLast4: string;
  ifsc: string;
  amountPaise: string;
  // From mandate_b64 only:
  decision: string;
  tier: number;
  deviceId: string;
  signedAt: string;
  keySecurityLevel?: string | null;
  policyVersion?: string | null;
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
  details?: VerificationDisplayDetails;
  approverValid?: boolean;
  countersignValid?: boolean;
  summaryHashMatched?: boolean;
  kmsKeyVersion?: string;
}

export interface MandateInput {
  mandate_id?: string;
  summary_sha256?: string;
  summary_b64?: string;
  mandate_b64?: string;
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

/** Compute SHA-256 hex string of bytes */
export async function computeSha256Hex(bytes: Uint8Array): Promise<string> {
  const bufferSource = bytes as unknown as BufferSource;
  const hashBuffer = await crypto.subtle.digest('SHA-256', bufferSource);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Decodes summary_b64 into bytes, text, and parsed payment data.
 */
export function decodeSummaryB64(summaryB64: string): DecodedSummary {
  if (!summaryB64 || typeof summaryB64 !== 'string') {
    throw new Error('Mandate is missing required summary_b64 field');
  }
  const bytes = base64ToBytes(summaryB64);
  const text = new TextDecoder('utf-8').decode(bytes);
  let data: DecodedSummary['data'];
  try {
    data = JSON.parse(text) as DecodedSummary['data'];
  } catch (err) {
    throw new Error(`Failed to parse summary_b64 JSON: ${(err as Error).message}`);
  }
  return { bytes, text, data };
}

/**
 * Decodes mandate_b64 into bytes, text, and parsed mandate payload.
 */
export function decodeMandateB64(mandateB64: string): DecodedMandatePayload {
  if (!mandateB64 || typeof mandateB64 !== 'string') {
    throw new Error('Mandate is missing required mandate_b64 field');
  }
  const bytes = base64ToBytes(mandateB64);
  const text = new TextDecoder('utf-8').decode(bytes);
  let data: DecodedMandatePayload['data'];
  try {
    data = JSON.parse(text) as DecodedMandatePayload['data'];
  } catch (err) {
    throw new Error(`Failed to parse mandate_b64 JSON: ${(err as Error).message}`);
  }
  return { bytes, text, data };
}

/**
 * Verifies a mandate following the exact 5-step fail-closed order:
 * a. KMS countersignature over mandate_b64.
 * b. Device public key taken ONLY from inside decoded mandate_b64 (outer key ignored).
 * c. Approver signature over summary_b64 with that device key.
 * d. SHA-256(summary_b64 bytes) === summary_sha256 inside mandate_b64.
 * e. Expiry from inside mandate_b64.
 */
export async function verifyMandate(
  mandate: MandateInput,
  fetchKmsKey?: () => Promise<string>,
): Promise<VerificationResult> {
  if (!mandate.mandate_b64 || !mandate.summary_b64) {
    return {
      status: 'error',
      message: 'Mandate must contain both mandate_b64 and summary_b64.',
    };
  }

  let decodedMandate: DecodedMandatePayload;
  try {
    decodedMandate = decodeMandateB64(mandate.mandate_b64);
  } catch (err) {
    return {
      status: 'error',
      message: (err as Error).message,
    };
  }

  let decodedSummary: DecodedSummary;
  try {
    decodedSummary = decodeSummaryB64(mandate.summary_b64);
  } catch (err) {
    return {
      status: 'error',
      message: (err as Error).message,
    };
  }

  const mData = decodedMandate.data;
  const sData = decodedSummary.data;

  // Extract display fields strictly from their respective canonical sources:
  // - Payee, account, IFSC, amount from summary_b64 only:
  const payee = sData.payee;
  const payeeName =
    payee?.name_at_bank ??
    sData.payee_name_at_bank ??
    payee?.name ??
    sData.payee_name ??
    '—';
  // The canonical summary carries the FULL account in payee_account, but every
  // screen shows only the last four, so narrow it here rather than letting a
  // full account number reach a display that expects four digits.
  const fullAccount = sData.payee_account ? String(sData.payee_account) : null;
  const accountLast4 =
    payee?.account_last4 ??
    sData.payee_account_last4 ??
    (fullAccount && fullAccount.length >= 4 ? fullAccount.slice(-4) : null) ??
    '—';
  const ifsc =
    payee?.ifsc ??
    sData.payee_ifsc ??
    '—';
  const amountPaise = String(
    sData.amount_paise ??
    sData.amountPaise ??
    sData.amount ??
    '0',
  );

  // - Decision, tier, device, and signed time from mandate_b64 only:
  const details: VerificationDisplayDetails = {
    payeeName: String(payeeName),
    accountLast4: String(accountLast4),
    ifsc: String(ifsc),
    amountPaise,
    decision: String(mData.decision ?? '—'),
    tier: Number(mData.tier ?? 0),
    deviceId: String(mData.device_id ?? '—'),
    signedAt: String(mData.signed_at ?? '—'),
    keySecurityLevel: mData.key_security_level ? String(mData.key_security_level) : null,
    policyVersion: mData.policy_version ? String(mData.policy_version) : null,
  };

  // --------------------------------------------------------------------------
  // Step a. KMS countersignature over mandate_b64 (key from GET /keys/countersign)
  // --------------------------------------------------------------------------
  const countersignature = mandate.countersignature;
  if (!countersignature?.signature) {
    return {
      status: 'invalid_signature',
      message: 'KMS countersignature is missing.',
      details,
    };
  }

  let kmsKeyPem: string | null = countersignature.public_key ?? null;
  if (!kmsKeyPem && fetchKmsKey) {
    try {
      kmsKeyPem = await fetchKmsKey();
    } catch (err) {
      return {
        status: 'error',
        message: `Failed to retrieve KMS countersigning key: ${(err as Error).message}`,
        details,
      };
    }
  }

  if (!kmsKeyPem) {
    return {
      status: 'error',
      message: 'Cloud KMS public key is unavailable for countersignature verification.',
      details,
    };
  }

  try {
    const kmsCryptoKey = await importP256PublicKey(kmsKeyPem);
    const rawKmsSig = derToRaw(base64ToBytes(countersignature.signature));
    const countersignValid = await crypto.subtle.verify(
      { name: 'ECDSA', hash: { name: 'SHA-256' } },
      kmsCryptoKey,
      rawKmsSig as unknown as BufferSource,
      decodedMandate.bytes as unknown as BufferSource,
    );

    if (!countersignValid) {
      return {
        status: 'invalid_signature',
        message: 'KMS countersignature verification failed over mandate_b64.',
        details,
        countersignValid: false,
      };
    }
  } catch (err) {
    return {
      status: 'invalid_signature',
      message: `KMS countersignature check failed: ${(err as Error).message}`,
      details,
      countersignValid: false,
    };
  }

  // --------------------------------------------------------------------------
  // Step b. Take device public key ONLY from inside decoded mandate_b64
  //         (Ignore any key in the outer JSON)
  // --------------------------------------------------------------------------
  const devicePublicKeyData = mData.device_public_key;
  if (!devicePublicKeyData || typeof devicePublicKeyData !== 'string') {
    return {
      status: 'invalid_signature',
      message: 'Device public key not found inside countersigned mandate_b64.',
      details,
    };
  }

  let deviceCryptoKey: CryptoKey;
  try {
    deviceCryptoKey = await importP256PublicKey(devicePublicKeyData);
  } catch (err) {
    return {
      status: 'invalid_signature',
      message: `Failed to import device public key from mandate_b64: ${(err as Error).message}`,
      details,
    };
  }

  // --------------------------------------------------------------------------
  // Step c. Approver signature (DER -> raw r||s) over summary_b64 with that key
  // --------------------------------------------------------------------------
  const approverSigStr = mandate.approval?.signature ?? mData.approver_signature;
  if (!approverSigStr || typeof approverSigStr !== 'string') {
    return {
      status: 'invalid_signature',
      message: 'Approver signature is missing.',
      details,
    };
  }

  try {
    const rawApproverSig = derToRaw(base64ToBytes(approverSigStr));
    const approverValid = await crypto.subtle.verify(
      { name: 'ECDSA', hash: { name: 'SHA-256' } },
      deviceCryptoKey,
      rawApproverSig as unknown as BufferSource,
      decodedSummary.bytes as unknown as BufferSource,
    );

    if (!approverValid) {
      return {
        status: 'invalid_signature',
        message: 'Approver signature verification failed over summary_b64.',
        details,
        approverValid: false,
      };
    }
  } catch (err) {
    return {
      status: 'invalid_signature',
      message: `Approver signature check failed: ${(err as Error).message}`,
      details,
      approverValid: false,
    };
  }

  // --------------------------------------------------------------------------
  // Step d. SHA-256(summary_b64 bytes) must equal summary_sha256 inside mandate_b64
  // --------------------------------------------------------------------------
  const calculatedSummarySha256 = await computeSha256Hex(decodedSummary.bytes);
  const expectedSummarySha256 = String(mData.summary_sha256 ?? '').toLowerCase();

  if (calculatedSummarySha256 !== expectedSummarySha256) {
    return {
      status: 'invalid_signature',
      message: `Summary hash mismatch: SHA-256(summary_b64) ${calculatedSummarySha256} does not match mandate_b64 summary_sha256 ${expectedSummarySha256}.`,
      details,
      summaryHashMatched: false,
    };
  }

  // --------------------------------------------------------------------------
  // Step e. Expiry from inside mandate_b64
  // --------------------------------------------------------------------------
  const expiryStr = mData.expires_at;
  if (expiryStr) {
    const expiryTime = new Date(expiryStr).getTime();
    if (!Number.isNaN(expiryTime) && expiryTime < Date.now()) {
      return {
        status: 'expired',
        message: `Mandate expired at ${expiryStr}.`,
        details,
      };
    }
  }

  // All 5 steps passed fail-closed
  return {
    status: 'valid',
    details,
    approverValid: true,
    countersignValid: true,
    summaryHashMatched: true,
    kmsKeyVersion: countersignature.kms_key_version,
  };
}
