/**
 * Tests for the attestation card.
 *
 * These pin the claim the whole product rests on: Pramaan reports only the checks
 * it actually ran. A check with no result must read "couldn't verify", and must
 * never be rendered in a way that could be mistaken for a pass.
 */

import type { ApprovalEvidence } from '@pramaan/shared';
import { render, screen } from '@testing-library/react';
import { Timestamp } from 'firebase/firestore';
import { describe, expect, it } from 'vitest';
import { AttestationCard } from './AttestationCard';

const SIGNED_AT = Timestamp.fromDate(new Date('2026-11-18T15:20:41+05:30'));

/** The strong case: a StrongBox phone, every check run and passed. */
const fullEvidence: ApprovalEvidence = {
  approver: 'cfo@acme.example',
  decision: 'approve',
  signedAt: SIGNED_AT,
  verifiedAt: SIGNED_AT,
  deviceId: 'dv_01JD2XCFOPHONE001',
  phoneModel: 'Pixel 9 Pro',
  keySecurityLevel: 'StrongBox',
  patchLevel: '2026-10-01',
  integrityVerdict: 'MEETS_STRONG_INTEGRITY',
  attestationRoot: 'google-ecdsa-p384',
  bootState: 'Verified',
  bootloaderLocked: true,
  signatureVerified: true,
  nonceFresh: true,
};

describe('with nothing signed yet', () => {
  it('says so, and claims nothing', () => {
    render(<AttestationCard approval={null} />);
    expect(screen.getByText(/Nothing has signed this payment yet/)).toBeInTheDocument();
    expect(screen.queryByText(/Verified against the enrolled key/)).not.toBeInTheDocument();
  });
});

describe('with every check run', () => {
  it('shows where the key lives and what it means', () => {
    render(<AttestationCard approval={fullEvidence} />);
    expect(screen.getByText('StrongBox')).toBeInTheDocument();
    expect(screen.getByText(/separate tamper-resistant chip/)).toBeInTheDocument();
  });

  it('shows the signature, nonce and boot state as passed', () => {
    render(<AttestationCard approval={fullEvidence} />);
    expect(screen.getByText('Verified against the enrolled key')).toBeInTheDocument();
    expect(screen.getByText('Fresh and unused')).toBeInTheDocument();
    expect(screen.getByText('Bootloader locked')).toBeInTheDocument();
    expect(screen.getByText('MEETS_STRONG_INTEGRITY')).toBeInTheDocument();
  });

  it('names who signed and when, in IST', () => {
    render(<AttestationCard approval={fullEvidence} />);
    expect(screen.getByText('cfo@acme.example')).toBeInTheDocument();
    expect(screen.getByText(/18 Nov 2026.*IST/)).toBeInTheDocument();
  });

  it('claims nothing it was not given', () => {
    render(<AttestationCard approval={fullEvidence} />);
    expect(screen.queryByText(/Couldn/)).not.toBeInTheDocument();
  });
});

describe('null is not false', () => {
  it('says "couldn’t verify" for a missing Play Integrity verdict, never a pass', () => {
    render(<AttestationCard approval={{ ...fullEvidence, integrityVerdict: null }} />);
    expect(screen.getByText(/Couldn/)).toBeInTheDocument();
    expect(
      screen.getByText(/Play Integrity recognises only builds installed from a Play testing track/),
    ).toBeInTheDocument();
  });

  it('says "couldn’t verify" for an unchecked signature rather than a failure', () => {
    render(<AttestationCard approval={{ ...fullEvidence, signatureVerified: null }} />);
    expect(screen.getByText(/Couldn/)).toBeInTheDocument();
    expect(screen.queryByText('Did not verify')).not.toBeInTheDocument();
    expect(screen.queryByText('Verified against the enrolled key')).not.toBeInTheDocument();
  });

  it('distinguishes a failed check from an absent one', () => {
    render(<AttestationCard approval={{ ...fullEvidence, signatureVerified: false }} />);
    expect(screen.getByText('Did not verify')).toBeInTheDocument();
    expect(screen.queryByText('Verified against the enrolled key')).not.toBeInTheDocument();
  });

  it('says "couldn’t verify" for every absent field at once', () => {
    render(
      <AttestationCard
        approval={{
          approver: 'cfo@acme.example',
          decision: 'approve',
          signedAt: SIGNED_AT,
          keySecurityLevel: null,
          patchLevel: null,
          integrityVerdict: null,
          attestationRoot: null,
          bootState: null,
          bootloaderLocked: null,
          signatureVerified: null,
          nonceFresh: null,
          phoneModel: null,
          deviceId: null,
        }}
      />,
    );
    // Key level, phone, patch, integrity, root, boot, signature, nonce.
    expect(screen.getAllByText(/Couldn/)).toHaveLength(8);
  });

  it('never uses the word fraud for a check that did not run', () => {
    const { container } = render(
      <AttestationCard approval={{ ...fullEvidence, signatureVerified: null, nonceFresh: null }} />,
    );
    expect(container.textContent?.toLowerCase()).not.toContain('fraud');
  });
});

describe('a software-only key', () => {
  it('is shown as not acceptable for an approval', () => {
    render(<AttestationCard approval={{ ...fullEvidence, keySecurityLevel: 'Software' }} />);
    expect(screen.getByText('Software only')).toBeInTheDocument();
    expect(screen.getByText(/not acceptable for an approval/)).toBeInTheDocument();
  });
});

describe('the decision', () => {
  it('shows a decline as declined', () => {
    render(<AttestationCard approval={{ ...fullEvidence, decision: 'decline' }} />);
    expect(screen.getByText('Declined')).toBeInTheDocument();
  });

  it('says "reported as fraud" only when the approver chose that', () => {
    render(<AttestationCard approval={{ ...fullEvidence, decision: 'report_fraud' }} />);
    expect(screen.getByText('Reported as fraud')).toBeInTheDocument();
  });

  it('shows an approval as approved', () => {
    render(<AttestationCard approval={fullEvidence} />);
    expect(screen.getByText('Approved')).toBeInTheDocument();
  });
});
