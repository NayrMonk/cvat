// SPDX-License-Identifier: MIT

import { useEffect, useRef, useState } from 'react';

import { getCore } from 'cvat-core-wrapper';

const core = getCore();

export type LiveStatus = 'connecting' | 'live' | 'closed';

// Several saves in a row (an import, or someone drawing quickly) make several messages;
// one refetch after they settle is enough.
const REFRESH_DELAY_MS = 300;

/**
 * Keeps a WebSocket open for a task and calls onChange when the server says something in the task
 * changed. The socket carries no data: the page refetches the counts over REST, so there is one
 * source of truth and one place where access to the task is checked.
 */
export default function useLiveUpdates(taskId: number, onChange: () => void): LiveStatus {
    const [status, setStatus] = useState<LiveStatus>('connecting');
    const onChangeRef = useRef(onChange);
    onChangeRef.current = onChange;

    useEffect(() => {
        let socket: WebSocket | null = null;
        let refreshTimer: number | undefined;
        let cancelled = false;

        const open = async (): Promise<void> => {
            setStatus('connecting');
            let ticket: string;
            try {
                const response = await core.server.request(
                    `${core.config.backendAPI}/annotation-stats/tasks/${taskId}/ticket`,
                    { method: 'GET' },
                );
                ticket = response.data.ticket;
            } catch {
                if (!cancelled) setStatus('closed');
                return;
            }
            if (cancelled) return;

            const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
            const url = `${scheme}://${window.location.host}${core.config.backendAPI}` +
                `/annotation-stats/ws/tasks/${taskId}?ticket=${encodeURIComponent(ticket)}`;
            socket = new WebSocket(url);
            socket.onopen = () => setStatus('live');
            socket.onmessage = (event: MessageEvent<string>) => {
                if (JSON.parse(event.data).type === 'changed') {
                    window.clearTimeout(refreshTimer);
                    refreshTimer = window.setTimeout(() => onChangeRef.current(), REFRESH_DELAY_MS);
                }
            };
            socket.onclose = () => {
                if (!cancelled) setStatus('closed');
            };
        };

        open();

        return () => {
            cancelled = true;
            window.clearTimeout(refreshTimer);
            socket?.close();
        };
    }, [taskId]);

    return status;
}
