/**
 * The attestation card.
 *
 * This is the screen where Pramaan's central claim is either true or a lie, so it
 * has one rule above all others:
 *
 *   A check that did not run is shown as "couldn't verify". Never as a pass,
 *   never as a failure, never as "fraud".
 *
 * In the read model every security field is nullable, and `null` is not `false`.
 * Null means Pramaan has no result. `false` means Pramaan checked and the check
 * did not hold. Those are different sentences and this card says different things
 * for them.
 *
 * It matters most for the Play Integrity verdict. Play Integrity only recognises
 * builds installed from a Play internal testing track, and until that track exists
 * there will be no verdicts at all. A card that quietly rendered "no verdict" as a
 * tick would be the single most dishonest pixel in the product.
 */

import {
  type ApprovalEvidence,
  CouldNotVerify,
  type KeySecurityLevel,
  formatIstWithRelative,
} from '@pramaan/shared';
import type { ReactNode } from 'react';

/** How strong a place the signing key lives in. */
const KEY_LEVEL_TEXT: Record<KeySecurityLevel, { label: string; detail: string; tone: string }> = {
  StrongBox: {
    label: 'StrongBox',
    detail: 'A separate tamper-resistant chip. The key cannot leave it.',
    tone: 'green',
  },
  TrustedEnvironment: {
    label: 'Trusted Execution Environment',
    detail: 'A secure area of the main processor. The key cannot leave it.',
    tone: 'blue',
  },
  Software: {
    label: 'Software only',
    detail: 'Not held in secure hardware. This is not acceptable for an approval.',
    tone: 'red',
  },
};

/**
 * One line of evidence.
 *
 * `value` of null is the whole point of this component: it renders
 * "couldn't verify" rather than anything that could be mistaken for a result.
 */
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
        {detail ? <span className="pr-fineprint">{detail}</span> : null}
      </dd>
    </>
  );
}

/**
 * A tri-state check: true passed, false failed, null not run.
 *
 * Deliberately a plain function and not a component. As `<Checked .../>` it would
 * be a React element, which is never nullish, so `value ?? <CouldNotVerify />` in
 * Evidence would never fire and an unrun check would render blank rather than as
 * "couldn't verify". Blank is exactly the silence this card exists to prevent.
 */
function checked(
  value: boolean | null | undefined,
  passed: string,
  failed: string,
): ReactNode | null {
  if (value === true) return <span className="pr-badge pr-badge--green">{passed}</span>;
  if (value === false) return <span className="pr-badge pr-badge--red">{failed}</span>;
  return null; // Evidence renders "couldn't verify".
}

export function AttestationCard({
  approval,
}: {
  approval: ApprovalEvidence | null | undefined;
}): ReactNode {
  if (!approval) {
    return (
      <section className="pr-card pr-stack" aria-labelledby="attestation-heading">
        <h2 id="attestation-heading" className="pr-h2">
          What signed this payment
        </h2>
        <p className="pr-muted">
          Nothing has signed this payment yet. An approval exists only once the
          approver has signed these exact details on their own phone.
        </p>
      </section>
    );
  }

  const signed = formatIstWithRelative(approval.signedAt);
  const level = approval.keySecurityLevel ? KEY_LEVEL_TEXT[approval.keySecurityLevel] : null;

  return (
    <section className="pr-card pr-stack" aria-labelledby="attestation-heading">
      <div className="pr-spread">
        <h2 id="attestation-heading" className="pr-h2">
          What signed this payment
        </h2>
        <DecisionBadge decision={approval.decision} />
      </div>

      <dl className="pr-defs">
        <Evidence label="Signed by" value={approval.approver} />

        <Evidence
          label="Signed at"
          value={signed ? `${signed.absolute} (${signed.relative})` : null}
        />

        <Evidence
          label="Key held in"
          value={
            level ? (
              <span className={`pr-badge pr-badge--${level.tone}`}>{level.label}</span>
            ) : null
          }
          detail={level?.detail}
        />

        <Evidence
          label="Phone"
          value={
            approval.phoneModel ? (
              <>
                {approval.phoneModel}
                {approval.deviceId ? (
                  <span className="pr-fineprint pr-mono">{approval.deviceId}</span>
                ) : null}
              </>
            ) : null
          }
        />

        <Evidence label="Security patch" value={approval.patchLevel} />

        <Evidence
          label="Device integrity"
          value={
            approval.integrityVerdict ? (
              <code className="pr-mono">{approval.integrityVerdict}</code>
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
                <span className="pr-badge pr-badge--grey">{approval.bootState}</span>
                {checked(
                  approval.bootloaderLocked,
                  'Bootloader locked',
                  'Bootloader unlocked',
                )}
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

      <p className="pr-fineprint">
        Pramaan reports only the checks it actually ran. Anything marked
        &ldquo;couldn&rsquo;t verify&rdquo; has no recorded result and must not be
        read as having passed.
      </p>
    </section>
  );
}

function DecisionBadge({ decision }: { decision: ApprovalEvidence['decision'] }): ReactNode {
  if (decision === 'approve') {
    return <span className="pr-badge pr-badge--green">Approved</span>;
  }
  if (decision === 'decline') {
    return <span className="pr-badge pr-badge--red">Declined</span>;
  }
  return <span className="pr-badge pr-badge--red">Reported as fraud</span>;
}
