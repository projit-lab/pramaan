// @vitest-environment node
//
// Node rather than jsdom, so these run against a real WebCrypto implementation
// and the signatures below are genuinely produced and genuinely checked. A
// mocked crypto would prove nothing about the one piece of code whose entire job
// is to not be fooled.

import { describe, expect, it } from 'vitest';
import {
  PublicKeyFormatError,
  SignatureFormatError,
  base64ToBytes,
  bytesToHex,
  derToRawSignature,
  importCountersignKey,
  looksLikeRawSignature,
  pemToSpki,
  sha256Hex,
  verifyCountersignature,
} from './verify';

// --------------------------------------------------------------- helpers

function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

/** Encodes a DER INTEGER, adding the sign byte when the high bit is set. */
function derInteger(value: Uint8Array): Uint8Array {
  let start = 0;
  while (start < value.length - 1 && value[start] === 0x00) start += 1;
  let body = value.slice(start);
  if ((body[0] ?? 0) & 0x80) {
    const padded = new Uint8Array(body.length + 1);
    padded.set(body, 1);
    body = padded;
  }
  const out = new Uint8Array(body.length + 2);
  out[0] = 0x02;
  out[1] = body.length;
  out.set(body, 2);
  return out;
}

/** Turns a raw r||s signature into the DER form Cloud KMS would return. */
function rawToDer(raw: Uint8Array): Uint8Array {
  const r = derInteger(raw.slice(0, 32));
  const s = derInteger(raw.slice(32, 64));
  const body = new Uint8Array(r.length + s.length);
  body.set(r, 0);
  body.set(s, r.length);
  const out = new Uint8Array(body.length + 2);
  out[0] = 0x30;
  out[1] = body.length;
  out.set(body, 2);
  return out;
}

async function generateKeyPair(): Promise<CryptoKeyPair> {
  return (await crypto.subtle.generateKey(
    { name: 'ECDSA', namedCurve: 'P-256' },
    true,
    ['sign', 'verify'],
  )) as CryptoKeyPair;
}

async function exportPem(key: CryptoKey): Promise<string> {
  const spki = new Uint8Array(await crypto.subtle.exportKey('spki', key));
  const body = bytesToBase64(spki).replace(/(.{64})/g, '$1\n');
  return `-----BEGIN PUBLIC KEY-----\n${body}\n-----END PUBLIC KEY-----\n`;
}

/** Signs bytes and returns the signature in DER, as Cloud KMS would. */
async function signDer(privateKey: CryptoKey, data: Uint8Array): Promise<string> {
  const raw = new Uint8Array(
    await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, privateKey, data as BufferSource),
  );
  return bytesToBase64(rawToDer(raw));
}

/** A stand-in for the canonical mandate bytes the API would return. */
const CANONICAL = new TextEncoder().encode(
  '{"amount_paise":"465000000","currency":"INR","intent_id":"pi_01JD2X","payee_name":"Sri Lakshmi Castings","v":"1"}',
);
const CANONICAL_B64 = bytesToBase64(CANONICAL);

// ------------------------------------------------------------------ base64

describe('base64ToBytes', () => {
  it('decodes standard base64', () => {
    expect(new TextDecoder().decode(base64ToBytes('aGVsbG8='))).toBe('hello');
  });

  it('decodes URL-safe base64 and tolerates missing padding', () => {
    expect(new TextDecoder().decode(base64ToBytes('aGVsbG8'))).toBe('hello');
    const urlSafe = bytesToBase64(new Uint8Array([251, 255, 190]))
      .replace(/\+/g, '-')
      .replace(/\//g, '_');
    expect(Array.from(base64ToBytes(urlSafe))).toEqual([251, 255, 190]);
  });

  it('ignores the line breaks a pasted mandate carries', () => {
    expect(new TextDecoder().decode(base64ToBytes('aGVs\nbG8='))).toBe('hello');
  });
});

describe('sha256Hex', () => {
  it('matches the known digest of an empty input', async () => {
    expect(await sha256Hex(new Uint8Array())).toBe(
      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    );
  });

  it('is 64 hex characters', async () => {
    expect(await sha256Hex(CANONICAL)).toMatch(/^[0-9a-f]{64}$/);
  });
});

// --------------------------------------------------------------------- DER

describe('derToRawSignature', () => {
  it('converts a well-formed signature to 64 bytes', () => {
    const r = new Uint8Array(32).fill(0x11);
    const s = new Uint8Array(32).fill(0x22);
    const raw = new Uint8Array(64);
    raw.set(r, 0);
    raw.set(s, 32);
    expect(Array.from(derToRawSignature(rawToDer(raw)))).toEqual(Array.from(raw));
  });

  it('strips the sign byte DER adds when the high bit is set', () => {
    // r begins 0xFF, so DER carries a leading 0x00 to keep it positive.
    const raw = new Uint8Array(64);
    raw.fill(0xff, 0, 32);
    raw.fill(0x01, 32, 64);
    const der = rawToDer(raw);
    // Layout: 30 <len> 02 <rlen> <r...>. So rlen is at [3] and r starts at [4].
    expect(der[2]).toBe(0x02); // INTEGER tag for r
    expect(der[3]).toBe(33); // 32 bytes plus the sign byte
    expect(der[4]).toBe(0x00); // the sign byte is really there
    expect(Array.from(derToRawSignature(der))).toEqual(Array.from(raw));
  });

  it('left-pads a short component back to 32 bytes', () => {
    // s has leading zero bits, so DER encodes it in fewer than 32 bytes. This is
    // the case that fails roughly one signature in a few hundred when a naive
    // implementation just concatenates whatever DER gave it.
    const raw = new Uint8Array(64);
    raw.fill(0x05, 0, 32);
    raw[32] = 0x00;
    raw[33] = 0x00;
    raw[34] = 0x7a;
    raw.fill(0x09, 35, 64);
    const der = rawToDer(raw);
    const converted = derToRawSignature(der);
    expect(converted.length).toBe(64);
    expect(Array.from(converted)).toEqual(Array.from(raw));
  });

  it('handles a long-form length header', () => {
    const raw = new Uint8Array(64).fill(0x33);
    const short = rawToDer(raw);
    // Re-encode the same body with a 0x81 long-form length.
    const body = short.slice(2);
    const long = new Uint8Array(body.length + 3);
    long[0] = 0x30;
    long[1] = 0x81;
    long[2] = body.length;
    long.set(body, 3);
    expect(Array.from(derToRawSignature(long))).toEqual(Array.from(raw));
  });

  it('rejects anything that is not a DER sequence', () => {
    expect(() => derToRawSignature(new Uint8Array([0x31, 0x02, 0x02, 0x00]))).toThrow(
      SignatureFormatError,
    );
    expect(() => derToRawSignature(new Uint8Array())).toThrow(SignatureFormatError);
  });

  it('rejects a sequence whose length does not match the data', () => {
    const raw = new Uint8Array(64).fill(0x44);
    const der = rawToDer(raw);
    const truncated = der.slice(0, der.length - 2);
    expect(() => derToRawSignature(truncated)).toThrow(SignatureFormatError);
  });
});

describe('looksLikeRawSignature', () => {
  it('spots a 64-byte signature that is not DER', () => {
    expect(looksLikeRawSignature(new Uint8Array(64).fill(0x01))).toBe(true);
  });

  it('does not mistake DER for raw', () => {
    expect(looksLikeRawSignature(rawToDer(new Uint8Array(64).fill(0x01)))).toBe(false);
  });
});

// --------------------------------------------------------------------- PEM

describe('pemToSpki', () => {
  it('reads a real exported key', async () => {
    const { publicKey } = await generateKeyPair();
    const pem = await exportPem(publicKey);
    expect(pemToSpki(pem).length).toBeGreaterThan(50);
  });

  it('rejects something that is not a PEM public key', () => {
    expect(() => pemToSpki('not a key')).toThrow(PublicKeyFormatError);
    expect(() => pemToSpki('-----BEGIN PUBLIC KEY-----\n!!!!\n-----END PUBLIC KEY-----')).toThrow(
      PublicKeyFormatError,
    );
  });
});

describe('importCountersignKey', () => {
  it('imports a P-256 key', async () => {
    const { publicKey } = await generateKeyPair();
    const key = await importCountersignKey(await exportPem(publicKey));
    expect(key.type).toBe('public');
  });

  it('rejects a key on the wrong curve', async () => {
    const pair = (await crypto.subtle.generateKey(
      { name: 'ECDSA', namedCurve: 'P-384' },
      true,
      ['sign', 'verify'],
    )) as CryptoKeyPair;
    await expect(importCountersignKey(await exportPem(pair.publicKey))).rejects.toThrow(
      PublicKeyFormatError,
    );
  });
});

// ------------------------------------------------------------------ verify

describe('verifyCountersignature', () => {
  it('accepts a genuine DER countersignature, the way Cloud KMS returns it', async () => {
    const { privateKey, publicKey } = await generateKeyPair();
    const result = await verifyCountersignature({
      canonicalB64: CANONICAL_B64,
      signatureB64: await signDer(privateKey, CANONICAL),
      publicKeyPem: await exportPem(publicKey),
      keyVersion: 'mandate-signer/3',
    });

    expect(result.outcome).toBe('valid');
    expect(result.detail).toContain('countersigned exactly these payment details');
    expect(result.canonicalSha256).toBe(bytesToHex(new Uint8Array(await crypto.subtle.digest('SHA-256', CANONICAL))));
    expect(result.keyVersion).toBe('mandate-signer/3');
  });

  it('accepts a raw r||s signature too, so either shape checks', async () => {
    const { privateKey, publicKey } = await generateKeyPair();
    const raw = new Uint8Array(
      await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, privateKey, CANONICAL),
    );
    const result = await verifyCountersignature({
      canonicalB64: CANONICAL_B64,
      signatureB64: bytesToBase64(raw),
      publicKeyPem: await exportPem(publicKey),
    });
    expect(result.outcome).toBe('valid');
  });

  it('rejects a mandate whose bytes were changed after signing', async () => {
    const { privateKey, publicKey } = await generateKeyPair();
    const signature = await signDer(privateKey, CANONICAL);

    // One digit of the account changes. This is the tamper test, in one assertion.
    const tampered = new TextEncoder().encode(
      '{"amount_paise":"465000000","currency":"INR","intent_id":"pi_01JD2X","payee_name":"Sri Lakshmi Castings","v":"2"}',
    );

    const result = await verifyCountersignature({
      canonicalB64: bytesToBase64(tampered),
      signatureB64: signature,
      publicKeyPem: await exportPem(publicKey),
    });

    expect(result.outcome).toBe('invalid_signature');
    expect(result.detail).toContain('did not sign these details');
    expect(result.detail.toLowerCase()).not.toContain('fraud');
  });

  it('rejects a signature made by a different key', async () => {
    const signer = await generateKeyPair();
    const impostor = await generateKeyPair();
    const result = await verifyCountersignature({
      canonicalB64: CANONICAL_B64,
      signatureB64: await signDer(signer.privateKey, CANONICAL),
      publicKeyPem: await exportPem(impostor.publicKey),
    });
    expect(result.outcome).toBe('invalid_signature');
  });

  it('reports an expired mandate separately from a bad one', async () => {
    const { privateKey, publicKey } = await generateKeyPair();
    const result = await verifyCountersignature({
      canonicalB64: CANONICAL_B64,
      signatureB64: await signDer(privateKey, CANONICAL),
      publicKeyPem: await exportPem(publicKey),
      expiresAt: '2026-11-20T11:42:07+05:30',
      now: new Date('2026-11-20T12:00:00+05:30'),
    });

    expect(result.outcome).toBe('expired');
    // The distinction that matters to an auditor: the signature was genuine.
    expect(result.detail).toContain('genuine');
  });

  it('is valid while the mandate is still live', async () => {
    const { privateKey, publicKey } = await generateKeyPair();
    const result = await verifyCountersignature({
      canonicalB64: CANONICAL_B64,
      signatureB64: await signDer(privateKey, CANONICAL),
      publicKeyPem: await exportPem(publicKey),
      expiresAt: '2026-11-20T12:42:07+05:30',
      now: new Date('2026-11-20T12:00:00+05:30'),
    });
    expect(result.outcome).toBe('valid');
  });

  it('checks the signature before the expiry, so a forged expired mandate reads as forged', async () => {
    const signer = await generateKeyPair();
    const impostor = await generateKeyPair();
    const result = await verifyCountersignature({
      canonicalB64: CANONICAL_B64,
      signatureB64: await signDer(signer.privateKey, CANONICAL),
      publicKeyPem: await exportPem(impostor.publicKey),
      expiresAt: '2020-01-01T00:00:00+05:30',
      now: new Date('2026-11-20T12:00:00+05:30'),
    });
    expect(result.outcome).toBe('invalid_signature');
  });

  it('says it cannot check when the signed bytes are missing', async () => {
    const { publicKey } = await generateKeyPair();
    const result = await verifyCountersignature({
      canonicalB64: '',
      signatureB64: 'MEUCIQ',
      publicKeyPem: await exportPem(publicKey),
    });
    expect(result.outcome).toBe('cannot_check');
    expect(result.detail).toContain('did not come with the bytes that were signed');
  });

  it('says it cannot check when the public key is unreadable', async () => {
    const { privateKey } = await generateKeyPair();
    const result = await verifyCountersignature({
      canonicalB64: CANONICAL_B64,
      signatureB64: await signDer(privateKey, CANONICAL),
      publicKeyPem: 'not a key at all',
    });
    expect(result.outcome).toBe('cannot_check');
    expect(result.canonicalSha256).toMatch(/^[0-9a-f]{64}$/);
  });

  it('calls a malformed signature invalid, not unverifiable', async () => {
    const { publicKey } = await generateKeyPair();
    const result = await verifyCountersignature({
      canonicalB64: CANONICAL_B64,
      signatureB64: bytesToBase64(new Uint8Array([0x01, 0x02, 0x03])),
      publicKeyPem: await exportPem(publicKey),
    });
    expect(result.outcome).toBe('invalid_signature');
  });

  it('never says the word fraud, whatever the outcome', async () => {
    const signer = await generateKeyPair();
    const impostor = await generateKeyPair();
    for (const pem of [await exportPem(signer.publicKey), await exportPem(impostor.publicKey)]) {
      const result = await verifyCountersignature({
        canonicalB64: CANONICAL_B64,
        signatureB64: await signDer(signer.privateKey, CANONICAL),
        publicKeyPem: pem,
      });
      expect(result.detail.toLowerCase()).not.toContain('fraud');
    }
  });

  it('survives a hundred real signatures, including awkward r and s values', async () => {
    // The short-component bug is intermittent by nature: it only shows when r or
    // s happens to have leading zero bits. A hundred genuine signatures makes it
    // very likely at least one awkward pair is covered.
    const { privateKey, publicKey } = await generateKeyPair();
    const pem = await exportPem(publicKey);

    for (let index = 0; index < 100; index += 1) {
      const message = new TextEncoder().encode(`{"intent_id":"pi_${index}","v":"1"}`);
      const result = await verifyCountersignature({
        canonicalB64: bytesToBase64(message),
        signatureB64: await signDer(privateKey, message),
        publicKeyPem: pem,
      });
      expect(result.outcome).toBe('valid');
    }
  });
});
