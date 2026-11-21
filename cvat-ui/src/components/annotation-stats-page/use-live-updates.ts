// SPDX-License-Identifier: MIT

import { useEffect, useRef, useState } from 'react';

import { getCore } from 'cvat-core-wrapper';

const core = getCore();

export type LiveStatus = 'connecting' | 'live' | 'reconnecting' | 'stopped';

// Several saves in a row (an import, or someone drawing quickly) make several messages;
// one refetch after they settle is enough.
const REFRESH_DELAY_MS = 300;

const RETRY_FIRST_MS = 1000;
const RETRY_MAX_MS = 30000;

// A connection that opens and is closed again at once must not reset the backoff, or a server in
// that state would be retried every second for ever. Only a connection that has stayed open this
// long counts as healthy.
const STABLE_AFTER_MS = 10000;

// Retrying cannot help with these: the user is not logged in, may not see the task, or it is gone.
const FATAL_CODES = [401, 403, 404];

/**
 * Keeps a WebSocket open for a task and calls onChange when the server says something in the task
 * changed, and again every time the connection is (re)established, because changes made while it
 * was down never produced a message. The socket carries no data: the page refetches the counts
 * over REST, so there is one source of truth and one place where access to the task is checked.
 */
export default function useLiveUpdates(taskId: number, onChange: () => void): LiveStatus {
    const [status, setStatus] = useState<LiveStatus>('connecting');
    const onChangeRef = useRef(onChange);
    onChangeRef.current = onChange;

    useEffect(() => {
        let socket: WebSocket | null = null;
        let refreshTimer: number | undefined;
        let retryTimer: number | undefined;
        let stableTimer: number | undefined;
        let retryPending = false;
        let attempt = 0;
        let cancelled = false;

        setStatus('connecting');

        function retryLater(): void {
            if (cancelled) return;

            setStatus('reconnecting');
            const delay = Math.min(RETRY_MAX_MS, RETRY_FIRST_MS * 2 ** attempt);
            attempt += 1;
            retryPending = true;
            // Jitter keeps every open page from reconnecting in the same instant after a restart.
            retryTimer = window.setTimeout(open, delay * (0.5 + Math.random() / 2));
        }

        async function open(): Promise<void> {
            retryPending = false;

            let ticket: string;
            try {
                const response = await core.server.request(
                    `${core.config.backendAPI}/annotation-stats/tasks/${taskId}/ticket`,
                    { method: 'GET' },
                );
                ticket = response.data.ticket;
            } catch (error: unknown) {
                if (cancelled) return;

                if (FATAL_CODES.includes((error as { code?: number }).code)) {
                    setStatus('stopped');
                    // let the page show why, through the same path as any other refresh
                    onChangeRef.current();
                } else {
                    retryLater();
                }
                return;
            }
            if (cancelled) return;

            const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
            const url = `${scheme}://${window.location.host}${core.config.backendAPI}` +
                `/annotation-stats/ws/tasks/${taskId}?ticket=${encodeURIComponent(ticket)}`;
            socket = new WebSocket(url);

            socket.onopen = () => {
                setStatus('live');
                stableTimer = window.setTimeout(() => { attempt = 0; }, STABLE_AFTER_MS);
                onChangeRef.current();
            };
            socket.onmessage = (event: MessageEvent<string>) => {
                if (JSON.parse(event.data).type === 'changed') {
                    window.clearTimeout(refreshTimer);
                    refreshTimer = window.setTimeout(() => onChangeRef.current(), REFRESH_DELAY_MS);
                }
            };
            socket.onclose = () => {
                window.clearTimeout(stableTimer);
                socket = null;
                retryLater();
            };
        }

        // When the network comes back there is no reason to sit out the rest of the wait.
        const onOnline = (): void => {
            if (retryPending) {
                window.clearTimeout(retryTimer);
                open();
            }
        };
        window.addEventListener('online', onOnline);

        open();

        return () => {
            cancelled = true;
            window.removeEventListener('online', onOnline);
            window.clearTimeout(refreshTimer);
            window.clearTimeout(retryTimer);
            window.clearTimeout(stableTimer);
            socket?.close();
        };
    }, [taskId]);

    return status;
}
