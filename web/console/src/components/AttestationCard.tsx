/**
 * What signed this payment.
 *
 * The screen where Pramaan's central claim is either true or a lie, so it has
 * one rule above all others:
 *
 *   A check that did not run is shown as "couldn't verify". Never as a pass,
 *   never as a failure, never as "fraud".
 *
 * In the read model every security field is nullable, and `null` is not
 * `false`. Null means Pramaan has no result. `false` means Pramaan checked and
 * the check did not hold. Those are different sentences and this card says
 * different things for them.
 *
 * It matters most for the Play Integrity verdict: that only exists for builds
 * installed from a Play testing track, so until that track exists there will be
 * no verdicts at all.
 */

import {
  type ApprovalEvidence,
  CouldNotVerify,
  Icon,
  type KeySecurityLevel,
  formatIstWithRelative,
} from '@pramaan/shared';
import type { ReactNode } from 'react';

const KEY_LEVEL: Record<
  KeySecurityLevel,
  { label: string; detail: string; tone: 'pass' | 'warn' | 'fail'; icon: string }
> = {
  StrongBox: {
    label: 'StrongBox hardware',
    detail: 'A separate tamper-resistant chip. The key cannot leave it.',
    tone: 'pass',
    icon: 'verified_user',
  },
  TrustedEnvironment: {
    label: 'TEE hardware',
    detail: 'A secure area of the main processor. The key cannot leave it.',
    tone: 'pass',
    icon: 'verified_user',
  },
  Software: {
    label: 'Software only',
    detail: 'Not held in secure hardware. This is not acceptable for an approval.',
    tone: 'warn',
    icon: 'gpp_maybe',
  },
};

/** One line of evidence. A null value renders "couldn't verify". */
function Evidence({
  label,
  value,
  detail,
}: {
  label: string;
  value: ReactNode | null;
  detail?: string;
}): ReactNode {
  return (
    <>
      <dt>{label}</dt>
      <dd>
        {value ?? <CouldNotVerify />}
        {detail ? <span className="pm-hint">{detail}</span> : null}
      </dd>
    </>
  );
}

/**
 * A tri-state check: true passed, false failed, null not run.
 *
 * Deliberately a plain function and not a component. As `<Checked .../>` it
 * would be a React element, which is never nullish, so the `?? <CouldNotVerify />`
 * fallback in Evidence would never fire and an unrun check would render blank.
 * Blank is exactly the silence this card exists to prevent.
 */
function checked(
  value: boolean | null | undefined,
  passed: string,
  failed: string,
): ReactNode | null {
  if (value === true) {
    return (
      <span className="pm-pass">
        <Icon name="check_circle" fill size="sm" />
        {passed}
      </span>
    );
  }
  if (value === false) {
    return (
      <span className="pm-fail">
        <Icon name="cancel" fill size="sm" />
        {failed}
      </span>
    );
  }
  return null;
}

export function AttestationCard({
  approval,
}: {
  approval: ApprovalEvidence | null | undefined;
}): ReactNode {
  if (!approval) {
    return (
      <section className="pm-card pm-stack" aria-labelledby="attestation-heading">
        <h2 id="attestation-heading" className="pm-heading">
          Approver&rsquo;s phone
        </h2>
        <p className="pm-muted" style={{ margin: 0 }}>
          Nothing has signed this payment yet. An approval exists only once the
          approver has signed these exact details on their own phone.
        </p>
      </section>
    );
  }

  const signed = formatIstWithRelative(approval.signedAt);
  const level = approval.keySecurityLevel ? KEY_LEVEL[approval.keySecurityLevel] : null;

  return (
    <section className="pm-card pm-stack" aria-labelledby="attestation-heading">
      <div className="pm-spread">
        <h2 id="attestation-heading" className="pm-heading">
          Approver&rsquo;s phone
        </h2>
        <DecisionChip decision={approval.decision} />
      </div>

      <dl className="pm-attest">
        <Evidence label="Signed by" value={approval.approver} />

        <Evidence
          label="Signed at"
          value={signed ? `${signed.absolute} (${signed.relative})` : null}
        />

        <Evidence
          label="Key"
          value={
            level ? (
              <span className={`pm-${level.tone}`}>
                <Icon name={level.icon} fill size="sm" />
                {level.label}
              </span>
            ) : null
          }
          detail={level?.detail}
        />

        <Evidence
          label="Device"
          value={
            approval.phoneModel ? (
              <>
                {approval.phoneModel}
                {approval.deviceId ? (
                  <span className="pm-mono pm-muted"> {approval.deviceId}</span>
                ) : null}
              </>
            ) : null
          }
        />

        <Evidence label="Patch level" value={approval.patchLevel} />

        <Evidence
          label="Integrity"
          value={
            approval.integrityVerdict ? (
              <span className="pm-pass">
                <Icon name="check_circle" fill size="sm" />
                <span className="pm-mono">{approval.integrityVerdict}</span>
              </span>
            ) : null
          }
          detail={
            approval.integrityVerdict
              ? undefined
              : 'Play Integrity recognises only builds installed from a Play testing track. Pramaan has no verdict for this signature.'
          }
        />

        <Evidence
          label="Attestation root"
          value={approval.attestationRoot}
          detail="The Google root the phone's certificate chain reached."
        />

        <Evidence
          label="Verified boot"
          value={
            approval.bootState ? (
              <>
                <span className="pm-mono">{approval.bootState}</span>
                {checked(approval.bootloaderLocked, 'Bootloader locked', 'Bootloader unlocked')}
              </>
            ) : null
          }
        />

        <Evidence
          label="Signature"
          value={checked(
            approval.signatureVerified,
            'Verified against the enrolled key',
            'Did not verify',
          )}
        />

        <Evidence
          label="Nonce"
          value={checked(approval.nonceFresh, 'Fresh and unused', 'Replayed or expired')}
        />
      </dl>

      <p className="pm-hint" style={{ margin: 0 }}>
        Pramaan reports only the checks it actually ran. Anything marked
        &ldquo;couldn&rsquo;t verify&rdquo; has no recorded result and must not be
        read as having passed.
      </p>
    </section>
  );
}

function DecisionChip({ decision }: { decision: ApprovalEvidence['decision'] }): ReactNode {
  if (decision === 'approve') {
    return (
      <span className="pm-chip pm-chip--approved">
        <Icon name="draw" />
        Approved
      </span>
    );
  }
  if (decision === 'decline') {
    return (
      <span className="pm-chip pm-chip--declined">
        <Icon name="block" />
        Declined
      </span>
    );
  }
  return (
    <span className="pm-chip pm-chip--blocked">
      <Icon name="gpp_bad" />
      Reported as fraud
    </span>
  );
}
