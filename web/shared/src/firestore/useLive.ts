/**
 * Live Firestore listeners for React.
 *
 * Two rules the build plan sets, both enforced here rather than left to each
 * screen: subscribe with a live listener, and unsubscribe when the screen closes.
 *
 * Every hook returns the same shape, so loading, empty and error states are
 * rendered the same way everywhere:
 *
 *   { data, status: 'loading' | 'ready' | 'error', error }
 */

import {
  type DocumentData,
  type Query,
  type QueryConstraint,
  collection,
  doc,
  onSnapshot,
  query,
} from 'firebase/firestore';
import { useEffect, useMemo, useRef, useState } from 'react';
import { firestore } from '../firebase/app';
import type { WithId } from '../types/firestore';

export type LiveStatus = 'loading' | 'ready' | 'error';

export interface LiveResult<T> {
  data: T;
  status: LiveStatus;
  error: Error | null;
}

/**
 * A live collection. `constraints` is re-evaluated only when `constraintsKey`
 * changes, so passing a fresh array of `where(...)` on every render does not tear
 * the listener down and build it again.
 */
export function useLiveCollection<T extends DocumentData>(
  path: string,
  constraints: QueryConstraint[] = [],
  constraintsKey = '',
): LiveResult<Array<WithId<T>>> {
  const [data, setData] = useState<Array<WithId<T>>>([]);
  const [status, setStatus] = useState<LiveStatus>('loading');
  const [error, setError] = useState<Error | null>(null);

  // Keep the latest constraints without making them a dependency.
  const constraintsRef = useRef(constraints);
  constraintsRef.current = constraints;

  useEffect(() => {
    // An empty path means "nothing to watch yet", so no listener is opened at all.
    if (!path) {
      setData([]);
      setStatus('ready');
      setError(null);
      return;
    }

    setStatus('loading');
    setError(null);

    let live = true;
    let unsubscribe: (() => void) | undefined;

    try {
      const base = collection(firestore(), path);
      const built: Query<DocumentData> =
        constraintsRef.current.length > 0 ? query(base, ...constraintsRef.current) : base;

      unsubscribe = onSnapshot(
        built,
        (snapshot) => {
          if (!live) return;
          setData(
            snapshot.docs.map((document) => ({
              id: document.id,
              ...(document.data() as T),
            })),
          );
          setStatus('ready');
        },
        (caught) => {
          if (!live) return;
          setError(caught instanceof Error ? caught : new Error(String(caught)));
          setStatus('error');
        },
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error(String(caught)));
      setStatus('error');
    }

    return () => {
      live = false;
      unsubscribe?.();
    };
  }, [path, constraintsKey]);

  return { data, status, error };
}

/** A live single document. `data` is null while loading and when it does not exist. */
export function useLiveDocument<T extends DocumentData>(
  path: string,
  id: string | null | undefined,
): LiveResult<WithId<T> | null> & { exists: boolean } {
  const [data, setData] = useState<WithId<T> | null>(null);
  const [exists, setExists] = useState(false);
  const [status, setStatus] = useState<LiveStatus>('loading');
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!id) {
      setData(null);
      setExists(false);
      setStatus('ready');
      return;
    }

    setStatus('loading');
    setError(null);

    let live = true;
    let unsubscribe: (() => void) | undefined;

    try {
      unsubscribe = onSnapshot(
        doc(firestore(), path, id),
        (snapshot) => {
          if (!live) return;
          if (snapshot.exists()) {
            setData({ id: snapshot.id, ...(snapshot.data() as T) });
            setExists(true);
          } else {
            setData(null);
            setExists(false);
          }
          setStatus('ready');
        },
        (caught) => {
          if (!live) return;
          setError(caught instanceof Error ? caught : new Error(String(caught)));
          setStatus('error');
        },
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error(String(caught)));
      setStatus('error');
    }

    return () => {
      live = false;
      unsubscribe?.();
    };
  }, [path, id]);

  return { data, exists, status, error };
}

/**
 * A live subcollection, for the payment timeline:
 * useLiveSubcollection('holds', intentId, 'steps')
 */
export function useLiveSubcollection<T extends DocumentData>(
  parentPath: string,
  parentId: string | null | undefined,
  subPath: string,
  constraints: QueryConstraint[] = [],
  constraintsKey = '',
): LiveResult<Array<WithId<T>>> {
  const path = useMemo(
    () => (parentId ? `${parentPath}/${parentId}/${subPath}` : ''),
    [parentPath, parentId, subPath],
  );

  return useLiveCollection<T>(path, constraints, constraintsKey);
}
