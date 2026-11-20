import { describe, expect, it } from 'vitest';
import {
  type MandateInput,
  bytesToBase64,
  computeSha256Hex,
  decodeMandateB64,
  decodeSummaryB64,
  derToRaw,
  verifyMandate,
} from './crypto';

describe('mandate verifier crypto (dual-signature model)', () => {
  it('converts DER ECDSA signature to 64-byte raw format', () => {
    const r = new Uint8Array(32).fill(0x11);
    const s = new Uint8Array(32).fill(0x22);
    const der = new Uint8Array([0x30, 68, 0x02, 32, ...r, 0x02, 32, ...s]);

    const raw = derToRaw(der);
    expect(raw.length).toBe(64);
    expect(raw.subarray(0, 32)).toEqual(r);
    expect(raw.subarray(32, 64)).toEqual(s);
  });

  it('computes correct SHA-256 hex string', async () => {
    const text = new TextEncoder().encode('hello pramaan');
    const hex = await computeSha256Hex(text);
    expect(hex).toBe('0c9d07bf77c33095e960e265a838dc2f70213189c4fe72d104a72983c98137ff');
  });

  async function createValidFixture() {
    // 1. Generate real ECDSA P-256 keys for Approver phone and Cloud KMS HSM
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

    const approverSpki = await crypto.subtle.exportKey('spki', approverKey.publicKey);
    const approverSpkiB64 = bytesToBase64(new Uint8Array(approverSpki));

    const kmsSpki = await crypto.subtle.exportKey('spki', kmsKey.publicKey);
    const kmsSpkiB64 = bytesToBase64(new Uint8Array(kmsSpki));

    // 2. Approver phone signs summary_b64
    const summaryPayload = {
      payee: {
        name_at_bank: 'Authentic Vendor Pvt Ltd',
        account_last4: '4321',
        ifsc: 'HDFC0001234',
      },
      amount_paise: '5000000',
      currency: 'INR',
    };
    const summaryBytes = new TextEncoder().encode(JSON.stringify(summaryPayload));
    const summaryB64 = bytesToBase64(summaryBytes);

    const approverSig = await crypto.subtle.sign(
      { name: 'ECDSA', hash: { name: 'SHA-256' } },
      approverKey.privateKey,
      summaryBytes,
    );
    const approverSigB64 = bytesToBase64(new Uint8Array(approverSig));

    const summarySha256 = await computeSha256Hex(summaryBytes);

    // 3. Cloud KMS HSM countersigns mandate_b64 which binds summary_sha256 and device_public_key
    const mandatePayload = {
      summary_sha256: summarySha256,
      decision: 'approve',
      tier: 2,
      policy_version: '2026.11.1',
      device_id: 'dv_01JD2XCFOPHONE001',
      device_public_key: approverSpkiB64,
      key_security_level: 'StrongBox',
      integrity_verdict: 'MEETS_STRONG_INTEGRITY',
      approver_signature: approverSigB64,
      signed_at: '2026-11-20T14:15:00+05:30',
      expires_at: '2099-12-31T23:59:59Z',
    };
    const mandateBytes = new TextEncoder().encode(JSON.stringify(mandatePayload));
    const mandateB64 = bytesToBase64(mandateBytes);

    const kmsSig = await crypto.subtle.sign(
      { name: 'ECDSA', hash: { name: 'SHA-256' } },
      kmsKey.privateKey,
      mandateBytes,
    );
    const kmsSigB64 = bytesToBase64(new Uint8Array(kmsSig));

    const mandate: MandateInput = {
      mandate_id: 'pm_01JD2XGENUINE0001',
      summary_sha256: summarySha256,
      summary_b64: summaryB64,
      mandate_b64: mandateB64,
      approval: {
        approver: 'cfo@acme.example',
        signature: approverSigB64,
      },
      countersignature: {
        kms_key_version: 'mandate-signer/1',
        signature: kmsSigB64,
        public_key: kmsSpkiB64,
      },
      expires_at: '2099-12-31T23:59:59Z',
    };

    return {
      mandate,
      approverKey,
      kmsKey,
      approverSpkiB64,
      kmsSpkiB64,
      summaryPayload,
      mandatePayload,
    };
  }

  it('verifies valid mandate and populates separated display fields', async () => {
    const { mandate } = await createValidFixture();

    const result = await verifyMandate(mandate);

    expect(result.status).toBe('valid');
    expect(result.approverValid).toBe(true);
    expect(result.countersignValid).toBe(true);
    expect(result.summaryHashMatched).toBe(true);

    // Display fields from summary_b64 only:
    expect(result.details?.payeeName).toBe('Authentic Vendor Pvt Ltd');
    expect(result.details?.accountLast4).toBe('4321');
    expect(result.details?.ifsc).toBe('HDFC0001234');
    expect(result.details?.amountPaise).toBe('5000000');

    // Display fields from mandate_b64 only:
    expect(result.details?.decision).toBe('approve');
    expect(result.details?.tier).toBe(2);
    expect(result.details?.deviceId).toBe('dv_01JD2XCFOPHONE001');
    expect(result.details?.signedAt).toBe('2026-11-20T14:15:00+05:30');
    expect(result.details?.keySecurityLevel).toBe('StrongBox');
  });

  it('fails if an attacker swaps the device public key in outer JSON', async () => {
    const { mandate } = await createValidFixture();

    // Attacker generates rogue key pair
    const rogueKey = await crypto.subtle.generateKey(
      { name: 'ECDSA', namedCurve: 'P-256' },
      true,
      ['sign', 'verify'],
    );
    const rogueSpki = await crypto.subtle.exportKey('spki', rogueKey.publicKey);
    const rogueSpkiB64 = bytesToBase64(new Uint8Array(rogueSpki));

    // Attacker puts rogue key into outer JSON approval.public_key
    mandate.approval = {
      approver: 'cfo@acme.example',
      signature: mandate.approval?.signature,
      public_key: rogueSpkiB64,
    };

    // The verifier must ignore the outer public_key, use device_public_key from mandate_b64,
    // and verify the authentic approver signature against the genuine key
    const resultWithGenuineSig = await verifyMandate(mandate);
    expect(resultWithGenuineSig.status).toBe('valid');

    // If the attacker replaces the signature with one signed by rogueKey:
    const rogueSummarySig = await crypto.subtle.sign(
      { name: 'ECDSA', hash: { name: 'SHA-256' } },
      rogueKey.privateKey,
      decodeSummaryB64(mandate.summary_b64!).bytes as unknown as BufferSource,
    );
    mandate.approval.signature = bytesToBase64(new Uint8Array(rogueSummarySig));

    const resultWithRogueSig = await verifyMandate(mandate);
    // MUST FAIL because device public key is taken ONLY from mandate_b64, not from outer JSON!
    expect(resultWithRogueSig.status).toBe('invalid_signature');
    expect(resultWithRogueSig.message).toContain('Approver signature verification failed');
  });

  it('fails if summary_b64 hash does not match summary_sha256 in mandate_b64', async () => {
    const { mandate, approverKey } = await createValidFixture();

    // Attacker swaps summary with a different amount and signs it with approverKey
    const fraudulentSummary = {
      payee: {
        name_at_bank: 'Authentic Vendor Pvt Ltd',
        account_last4: '4321',
        ifsc: 'HDFC0001234',
      },
      amount_paise: '9999999999', // Fraudulent amount
      currency: 'INR',
    };
    const fraudulentBytes = new TextEncoder().encode(JSON.stringify(fraudulentSummary));
    mandate.summary_b64 = bytesToBase64(fraudulentBytes);

    const fraudulentSig = await crypto.subtle.sign(
      { name: 'ECDSA', hash: { name: 'SHA-256' } },
      approverKey.privateKey,
      fraudulentBytes,
    );
    mandate.approval = {
      ...mandate.approval,
      signature: bytesToBase64(new Uint8Array(fraudulentSig)),
    };

    // Must fail closed because SHA-256(summary_b64) does not match mandate_b64.summary_sha256
    const result = await verifyMandate(mandate);
    expect(result.status).toBe('invalid_signature');
    expect(result.message).toContain('Summary hash mismatch');
  });

  it('fails if mandate_b64 is tampered after KMS countersigning', async () => {
    const { mandate } = await createValidFixture();

    // Attacker tampers with mandate_b64 payload (lowering tier from 2 to 0)
    const decoded = decodeMandateB64(mandate.mandate_b64!);
    decoded.data.tier = 0;
    const tamperedBytes = new TextEncoder().encode(JSON.stringify(decoded.data));
    mandate.mandate_b64 = bytesToBase64(tamperedBytes);

    // Must fail closed because KMS countersignature over mandate_b64 is invalid
    const result = await verifyMandate(mandate);
    expect(result.status).toBe('invalid_signature');
    expect(result.message).toContain('KMS countersignature verification failed');
  });

  it('fails if mandate is expired inside mandate_b64', async () => {
    const { mandate, kmsKey } = await createValidFixture();

    // Build expired mandate_b64
    const decodedMandate = decodeMandateB64(mandate.mandate_b64!);
    decodedMandate.data.expires_at = '2020-01-01T00:00:00Z';
    const expiredBytes = new TextEncoder().encode(JSON.stringify(decodedMandate.data));
    mandate.mandate_b64 = bytesToBase64(expiredBytes);

    // Re-sign with KMS so countersignature is valid, but expiry check triggers
    const kmsSig = await crypto.subtle.sign(
      { name: 'ECDSA', hash: { name: 'SHA-256' } },
      kmsKey.privateKey,
      expiredBytes,
    );
    mandate.countersignature!.signature = bytesToBase64(new Uint8Array(kmsSig));

    const result = await verifyMandate(mandate);
    expect(result.status).toBe('expired');
    expect(result.message).toContain('Mandate expired');
  });

  /**
   * The canonical payment summary that Kotlin and Python both have to produce is
   * fixed by contracts/canonical/vectors.json, and it carries flat keys:
   * payee_name, payee_account, payee_ifsc, amount_paise. A verifier that only
   * knew payee.name_at_bank / payee_account_last4 showed a valid mandate with an
   * empty payee and an empty account, which is worse than refusing to show it.
   */
  it('reads the payee and account from a summary in the agreed canonical form', async () => {
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
    const approverSpkiB64 = bytesToBase64(
      new Uint8Array(await crypto.subtle.exportKey('spki', approverKey.publicKey)),
    );
    const kmsSpkiB64 = bytesToBase64(
      new Uint8Array(await crypto.subtle.exportKey('spki', kmsKey.publicKey)),
    );

    // Keys sorted, no whitespace, every value a string: vectors.json's genuine_payment.
    const canonical =
      '{"amount_paise":"98000000","currency":"INR","expires_at":"2099-12-31T23:59:59+05:30",' +
      '"initiator":"human:clerk@acme.example","intent_id":"pi_01JD2XGENUINE0001",' +
      '"mandate_id":"pm_01JD2XGENUINE0001","payee_account":"000123457781",' +
      '"payee_ifsc":"ABCD0123456","payee_name":"Sri Lakshmi Castings",' +
      '"payer_account":"50100004521","purpose":"INV-2219","v":"1"}';
    const summaryBytes = new TextEncoder().encode(canonical);
    const summarySha256 = await computeSha256Hex(summaryBytes);
    const approverSigB64 = bytesToBase64(
      new Uint8Array(
        await crypto.subtle.sign(
          { name: 'ECDSA', hash: { name: 'SHA-256' } },
          approverKey.privateKey,
          summaryBytes,
        ),
      ),
    );

    const mandateBytes = new TextEncoder().encode(
      JSON.stringify({
        summary_sha256: summarySha256,
        decision: 'approve',
        tier: 1,
        policy_version: '2026.11.1',
        device_id: 'dv_01JD2XCFOPHONE001',
        device_public_key: approverSpkiB64,
        key_security_level: 'StrongBox',
        integrity_verdict: 'MEETS_STRONG_INTEGRITY',
        approver_signature: approverSigB64,
        signed_at: '2026-11-18T15:20:41+05:30',
        expires_at: '2099-12-31T23:59:59Z',
      }),
    );
    const kmsSigB64 = bytesToBase64(
      new Uint8Array(
        await crypto.subtle.sign(
          { name: 'ECDSA', hash: { name: 'SHA-256' } },
          kmsKey.privateKey,
          mandateBytes,
        ),
      ),
    );

    const mandate: MandateInput = {
      mandate_id: 'pm_01JD2XGENUINE0001',
      summary_sha256: summarySha256,
      summary_b64: bytesToBase64(summaryBytes),
      mandate_b64: bytesToBase64(mandateBytes),
      approval: { approver: 'cfo@acme.example', signature: approverSigB64 },
      countersignature: {
        kms_key_version: 'mandate-signer/1',
        signature: kmsSigB64,
        public_key: kmsSpkiB64,
      },
    };

    const result = await verifyMandate(mandate);
    expect(result.status).toBe('valid');
    expect(result.details?.payeeName).toBe('Sri Lakshmi Castings');
    // The signed bytes carry the full account; the screen may only show four,
    // and maskAccount refuses anything that is not exactly four digits.
    expect(result.details?.accountLast4).toBe('7781');
    expect(result.details?.ifsc).toBe('ABCD0123456');
    expect(result.details?.amountPaise).toBe('98000000');
    // Never a dash where the signed bytes carried a value.
    expect(result.details?.payeeName).not.toBe('—');
  });
});
