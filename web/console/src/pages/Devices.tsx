/**
 * The phones that can sign an approval. Read-only.
 *
 * Revoking arrives in a later release, so the button is disabled and says so.
 * A button that looks live but does nothing is worse than no button.
 *
 * The integrity verdict is the honesty case that matters here: a device with
 * no recorded verdict reads "couldn't verify", never a pass.
 */

import {
  COLLECTIONS,
  CouldNotVerify,
  type Device,
  EmptyState,
  ErrorState,
  Icon,
  LoadingState,
  StateBand,
  formatIstDate,
  useLiveCollection,
} from '@pramaan/shared';
import type { ReactNode } from 'react';

function KeyCell({ level }: { level: Device['keySecurityLevel'] }): ReactNode {
  if (level === 'StrongBox') {
    return (
      <span className="pm-pass">
        <Icon name="verified_user" fill size="sm" />
        StrongBox hardware
      </span>
    );
  }
  if (level === 'TrustedEnvironment') {
    return (
      <span className="pm-pass">
        <Icon name="verified_user" fill size="sm" />
        TEE hardware
      </span>
    );
  }
  return (
    <span className="pm-warn">
      <Icon name="gpp_maybe" fill size="sm" />
      Software key, not hardware
    </span>
  );
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
    return <ErrorState title="We could not load the devices" error={error} />;
  }

  return (
    <>
      <StateBand eyebrow={<span className="pm-label">Devices</span>}>
        <h1 className="pm-display">Approver phones</h1>
        <div className="pm-muted">
          The phones that can sign an approval, and what we know about each one.
        </div>
      </StateBand>

      <div className="pm-stack pm-stack--lg">
        {data.length === 0 ? (
          <EmptyState
            title="No phones enrolled yet"
            detail="A phone appears here once an approver enrols it and every attestation check passes."
            icon="smartphone"
          />
        ) : (
          <div className="pm-table-wrap">
            <table className="pm-table">
              <thead>
                <tr>
                  <th scope="col">Approver</th>
                  <th scope="col">Phone</th>
                  <th scope="col">Key</th>
                  <th scope="col">Security patch</th>
                  <th scope="col">Last integrity verdict</th>
                  <th scope="col">Enrolled</th>
                  <th scope="col">
                    <span className="pm-visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.map((device) => {
                  const stale = patchIsStale(device.patchLevel);
                  return (
                    <tr key={device.id}>
                      <td>
                        <div style={{ fontWeight: 500 }}>{device.approver}</div>
                        {device.revoked ? (
                          <span className="pm-chip pm-chip--blocked">
                            <Icon name="gpp_bad" />
                            Device removed
                          </span>
                        ) : null}
                      </td>
                      <td>
                        {device.phoneModel ?? <span className="pm-muted">Not recorded</span>}
                        <div className="pm-mono pm-muted">{device.deviceId}</div>
                      </td>
                      <td>
                        <KeyCell level={device.keySecurityLevel} />
                      </td>
                      <td>
                        {device.patchLevel ?? <span className="pm-muted">Not recorded</span>}
                        {stale ? (
                          <div className="pm-warn" style={{ fontSize: 13 }}>
                            <Icon name="warning" fill size="sm" />
                            More than 12 months old
                          </div>
                        ) : null}
                      </td>
                      <td>
                        {device.lastIntegrityVerdict ? (
                          <span className="pm-pass">
                            <Icon name="check_circle" fill size="sm" />
                            <span className="pm-mono">{device.lastIntegrityVerdict}</span>
                          </span>
                        ) : (
                          <CouldNotVerify />
                        )}
                      </td>
                      <td className="pm-muted">
                        {formatIstDate(device.enrolledAt) ?? 'Not recorded'}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="pm-btn pm-btn--text"
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
          </div>
        )}

        <p className="pm-hint">
          Revoking a phone arrives in a later release. Until then, an approver who
          loses a phone should be removed from the approval matrix by an administrator.
        </p>
      </div>
    </>
  );
}
