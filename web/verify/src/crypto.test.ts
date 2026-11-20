import { describe, expect, it } from 'vitest';
import {
  bytesToBase64,
  decodeCanonicalB64,
  derToRaw,
  extractCanonicalPaymentDetails,
  verifyMandate,
} from './crypto';

describe('mandate verifier crypto', () => {
  it('converts DER ECDSA signature to 64-byte raw format', () => {
    // A synthetic ASN.1 DER ECDSA signature
    const r = new Uint8Array(32).fill(0x11);
    const s = new Uint8Array(32).fill(0x22);
    const der = new Uint8Array([
      0x30, 68,
      0x02, 32, ...r,
      0x02, 32, ...s,
    ]);

    const raw = derToRaw(der);
    expect(raw.length).toBe(64);
    expect(raw.subarray(0, 32)).toEqual(r);
    expect(raw.subarray(32, 64)).toEqual(s);
  });

  it('passes 64-byte raw signature through directly', () => {
    const rawIn = new Uint8Array(64).fill(0x42);
    const rawOut = derToRaw(rawIn);
    expect(rawOut).toEqual(rawIn);
  });

  it('decodes canonical_b64 and extracts payment fields ONLY from decoded bytes', () => {
    const canonicalPayload = {
      mandate_id: 'pm_01JD2XCANONICAL001',
      payee: {
        name_at_bank: 'Authentic Vendor Pvt Ltd',
        account_last4: '4321',
        ifsc: 'HDFC0001234',
      },
      amount_paise: '5000000',
    };

    const canonicalBytes = new TextEncoder().encode(JSON.stringify(canonicalPayload));
    const canonicalB64 = bytesToBase64(canonicalBytes);

    const decoded = decodeCanonicalB64(canonicalB64);
    expect(decoded.data.mandate_id).toBe('pm_01JD2XCANONICAL001');

    const details = extractCanonicalPaymentDetails(decoded);
    expect(details.payeeName).toBe('Authentic Vendor Pvt Ltd');
    expect(details.accountLast4).toBe('4321');
    expect(details.ifsc).toBe('HDFC0001234');
    expect(details.amountPaise).toBe('5000000');
  });

  it('verifies both signatures over canonical bytes and ignores outer JSON tampering', async () => {
    // 1. Generate real ECDSA P-256 keys for Approver and KMS
    const approverKey = await crypto.subtle.generateKey(
      { name: 'ECDSA', namedCurve: 'P-256' },
      true,
      ['sign', 'verify'],
    );
    const kmsKey = await crypto.subtle.generateKey(
      { name: 'ECDSA', namedCurve: 'P-256' },
      true,
      ['sign', 'verify'],
    );

    // Export public keys as SPKI base64
    const approverSpki = await crypto.subtle.exportKey('spki', approverKey.publicKey);
    const approverSpkiB64 = bytesToBase64(new Uint8Array(approverSpki));

    const kmsSpki = await crypto.subtle.exportKey('spki', kmsKey.publicKey);
    const kmsSpkiB64 = bytesToBase64(new Uint8Array(kmsSpki));

    // 2. Canonical payload signed by both
    const canonicalPayload = {
      mandate_id: 'pm_01JD2XGENUINE',
      decision: 'approve',
      amount_paise: '12500000',
      payee: {
        name_at_bank: 'True Payee Services',
        account_last4: '9988',
        ifsc: 'ICIC0000104',
      },
      expires_at: '2099-12-31T23:59:59Z',
    };

    const canonicalBytes = new TextEncoder().encode(JSON.stringify(canonicalPayload));
    const canonicalB64 = bytesToBase64(canonicalBytes);

    // Sign canonicalBytes with approver key (WebCrypto produces raw 64 bytes)
    const approverSig = await crypto.subtle.sign(
      { name: 'ECDSA', hash: { name: 'SHA-256' } },
      approverKey.privateKey,
      canonicalBytes,
    );

    // Sign canonicalBytes with KMS key
    const kmsSig = await crypto.subtle.sign(
      { name: 'ECDSA', hash: { name: 'SHA-256' } },
      kmsKey.privateKey,
      canonicalBytes,
    );

    // 3. Assemble Mandate with outer JSON TAMPERING (fraudulent payee & amount)
    const mandate = {
      mandate_id: 'pm_01JD2XGENUINE',
      canonical_b64: canonicalB64,
      // Attacker modified outer JSON fields:
      payee: {
        name: 'FRAUDULENT PAYEE ATTACKER',
        account_last4: '0000',
        ifsc: 'HACK0000000',
      },
      amount_paise: '999999999',
      approval: {
        approver: 'cfo@acme.example',
        signature: bytesToBase64(new Uint8Array(approverSig)),
        public_key: approverSpkiB64,
      },
      countersignature: {
        kms_key_version: 'mandate-signer/1',
        signature: bytesToBase64(new Uint8Array(kmsSig)),
        public_key: kmsSpkiB64,
      },
      expires_at: '2099-12-31T23:59:59Z',
    };

    const result = await verifyMandate(mandate);

    // Assert that verification succeeds and fields displayed are from CANONICAL ONLY
    expect(result.status).toBe('valid');
    expect(result.details?.payeeName).toBe('True Payee Services');
    expect(result.details?.accountLast4).toBe('9988');
    expect(result.details?.ifsc).toBe('ICIC0000104');
    expect(result.details?.amountPaise).toBe('12500000');
    expect(result.approverValid).toBe(true);
    expect(result.countersignValid).toBe(true);
  });

  it('rejects verification if canonical_b64 has been tampered with', async () => {
    const keyPair = await crypto.subtle.generateKey(
      { name: 'ECDSA', namedCurve: 'P-256' },
      true,
      ['sign', 'verify'],
    );
    const spki = await crypto.subtle.exportKey('spki', keyPair.publicKey);
    const spkiB64 = bytesToBase64(new Uint8Array(spki));

    const originalBytes = new TextEncoder().encode(JSON.stringify({ amount_paise: '1000' }));
    const signature = await crypto.subtle.sign(
      { name: 'ECDSA', hash: { name: 'SHA-256' } },
      keyPair.privateKey,
      originalBytes,
    );

    // Tampered canonical payload
    const tamperedBytes = new TextEncoder().encode(JSON.stringify({ amount_paise: '9999' }));
    const tamperedB64 = bytesToBase64(tamperedBytes);

    const mandate = {
      mandate_id: 'pm_tampered',
      canonical_b64: tamperedB64,
      approval: {
        approver: 'cfo@acme.example',
        signature: bytesToBase64(new Uint8Array(signature)),
        public_key: spkiB64,
      },
      countersignature: {
        kms_key_version: 'mandate-signer/1',
        signature: bytesToBase64(new Uint8Array(signature)),
        public_key: spkiB64,
      },
    };

    const result = await verifyMandate(mandate);
    expect(result.status).toBe('invalid_signature');
  });

  it('detects expired mandate', async () => {
    const canonicalPayload = {
      mandate_id: 'pm_expired',
      amount_paise: '5000',
      expires_at: '2020-01-01T00:00:00Z',
    };
    const canonicalB64 = bytesToBase64(new TextEncoder().encode(JSON.stringify(canonicalPayload)));

    const mandate = {
      mandate_id: 'pm_expired',
      canonical_b64: canonicalB64,
      expires_at: '2020-01-01T00:00:00Z',
      approval: { signature: 'AAAA' },
      countersignature: { signature: 'BBBB' },
    };

    const result = await verifyMandate(mandate);
    expect(result.status).toBe('expired');
  });
});
