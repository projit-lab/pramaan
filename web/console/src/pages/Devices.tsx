/**
 * Devices, read-only.
 *
 * The Revoke button is disabled and says when it arrives, because revocation is
 * M5 and a button that looks live but does nothing is worse than no button.
 *
 * The integrity verdict is the honesty case that matters here: a device with no
 * recorded verdict reads "couldn't verify", never a pass. Play Integrity only
 * recognises builds installed from a Play internal testing track, so until that
 * track exists there will be no verdicts at all, and this page must not imply
 * otherwise.
 */

import {
  COLLECTIONS,
  CouldNotVerify,
  type Device,
  EmptyState,
  ErrorState,
  LoadingState,
  formatIstWithRelative,
  useLiveCollection,
} from '@pramaan/shared';
import type { ReactNode } from 'react';

function SecurityLevelBadge({ level }: { level: Device['keySecurityLevel'] }): ReactNode {
  // StrongBox is the strongest, TEE is honest and common, Software is not
  // acceptable for an approval and is shown as a problem.
  const tone = level === 'StrongBox' ? 'green' : level === 'TrustedEnvironment' ? 'blue' : 'red';
  return <span className={`pr-badge pr-badge--${tone}`}>{level}</span>;
}

/** Warns when the OS patch level is older than the policy window of 12 months. */
function patchIsStale(patchLevel: string | null | undefined): boolean {
  if (!patchLevel) return false;
  const parsed = new Date(patchLevel);
  if (Number.isNaN(parsed.getTime())) return false;
  const twelveMonthsAgo = new Date();
  twelveMonthsAgo.setMonth(twelveMonthsAgo.getMonth() - 12);
  return parsed < twelveMonthsAgo;
}

export function Devices(): ReactNode {
  const { data, status, error } = useLiveCollection<Device>(COLLECTIONS.devices);

  if (status === 'loading') return <LoadingState label="Loading approver phones" />;
  if (status === 'error') {
    return <ErrorState title="Could not load the devices" error={error} />;
  }

  return (
    <div className="pr-stack">
      <div>
        <h1 className="pr-h1">Approver phones</h1>
        <p className="pr-muted">
          The phones that can sign an approval. Read-only for now.
        </p>
      </div>

      {data.length === 0 ? (
        <EmptyState
          title="No phones enrolled yet"
          detail="A phone appears here once an approver enrols it and every attestation check passes."
        />
      ) : (
        <table className="pr-table">
          <thead>
            <tr>
              <th scope="col">Approver</th>
              <th scope="col">Phone</th>
              <th scope="col">Key held in</th>
              <th scope="col">Security patch</th>
              <th scope="col">Last integrity verdict</th>
              <th scope="col">Enrolled</th>
              <th scope="col">
                <span className="pr-visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((device) => {
              const enrolled = formatIstWithRelative(device.enrolledAt);
              const stale = patchIsStale(device.patchLevel);
              return (
                <tr key={device.id}>
                  <td>
                    {device.approver}
                    {device.revoked ? (
                      <span className="pr-badge pr-badge--red">Revoked</span>
                    ) : null}
                  </td>
                  <td>{device.phoneModel ?? <span className="pr-muted">Not recorded</span>}</td>
                  <td>
                    <SecurityLevelBadge level={device.keySecurityLevel} />
                  </td>
                  <td>
                    {device.patchLevel ?? <span className="pr-muted">Not recorded</span>}
                    {stale ? (
                      <div className="pr-badge pr-badge--amber">More than 12 months old</div>
                    ) : null}
                  </td>
                  <td>
                    {device.lastIntegrityVerdict ? (
                      <code className="pr-mono">{device.lastIntegrityVerdict}</code>
                    ) : (
                      <CouldNotVerify />
                    )}
                  </td>
                  <td>
                    {enrolled ? enrolled.absolute : <span className="pr-muted">Not recorded</span>}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="pr-button pr-button--small"
                      disabled
                      title="Revoking a phone arrives in a later release."
                    >
                      Revoke
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <p className="pr-fineprint">
        Revoking a phone arrives in a later release. Until then, an approver who loses
        a phone should be removed from the approval matrix by an administrator.
      </p>
    </div>
  );
}
