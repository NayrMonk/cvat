// SPDX-License-Identifier: MIT

import './styles.scss';

import React, {
    useCallback, useEffect, useRef, useState,
} from 'react';
import { useParams } from 'react-router';
import Badge from 'antd/lib/badge';
import Button from 'antd/lib/button';
import Empty from 'antd/lib/empty';
import Result from 'antd/lib/result';
import Text from 'antd/lib/typography/Text';
import Title from 'antd/lib/typography/Title';
import { Row, Col } from 'antd/lib/grid';

import { getCore } from 'cvat-core-wrapper';
import GoBackButton from 'components/common/go-back-button';
import CVATLoadingSpinner from 'components/common/loading-spinner';
import AnnotationCountsChart, { LabelCount } from './annotation-counts-chart';
import useLiveUpdates, { LiveStatus } from './use-live-updates';

const core = getCore();

interface TaskAnnotationCounts {
    task_id: number;
    total: number;
    labels: LabelCount[];
}

interface FailureText {
    title: string;
    subTitle: string;
    // retrying only helps when the failure may be temporary
    retryable: boolean;
}

function describeFailure(code: number | undefined): FailureText {
    switch (code) {
        case 401:
            return { title: 'You are not logged in', subTitle: 'Log in and open this page again.', retryable: false };
        case 403:
            return {
                title: 'You do not have access to this task',
                subTitle: 'Ask the task owner or an organization maintainer for access.',
                retryable: false,
            };
        case 404:
            return { title: 'Task not found', subTitle: 'Check the task id in the address.', retryable: false };
        default:
            return {
                title: 'Could not load annotation statistics',
                subTitle: 'The server did not answer as expected. Check your connection and try again.',
                retryable: true,
            };
    }
}

const LIVE_BADGE: Record<LiveStatus, { status: 'processing' | 'success' | 'warning' | 'default'; text: string }> = {
    connecting: { status: 'processing', text: 'Connecting' },
    live: { status: 'success', text: 'Live' },
    reconnecting: { status: 'warning', text: 'Reconnecting' },
    stopped: { status: 'default', text: 'Live updates off' },
};

async function fetchCounts(taskId: number): Promise<TaskAnnotationCounts> {
    const response = await core.server.request(
        `${core.config.backendAPI}/annotation-stats/tasks/${taskId}`,
        { method: 'GET' },
    );
    return response.data;
}

type Loaded =
    | { status: 'loading' }
    // stale: the last refresh failed, so the numbers shown may be out of date
    | { status: 'ready'; counts: TaskAnnotationCounts; stale?: boolean }
    | { status: 'failed'; code?: number };

export default function AnnotationStatsPage(): JSX.Element {
    const taskId = +useParams<{ tid: string }>().tid;
    const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' });

    // Responses can arrive out of order; only the newest request may change what is on screen.
    const latestRequest = useRef(0);

    const load = useCallback(async () => {
        const request = ++latestRequest.current;
        setLoaded({ status: 'loading' });
        try {
            const counts = await fetchCounts(taskId);
            if (request === latestRequest.current) setLoaded({ status: 'ready', counts });
        } catch (error: unknown) {
            const code = (error as { code?: number }).code;
            if (request === latestRequest.current) setLoaded({ status: 'failed', code });
        }
    }, [taskId]);

    // A live update replaces the numbers in place, without the loading spinner.
    const refresh = useCallback(async () => {
        const request = ++latestRequest.current;
        try {
            const counts = await fetchCounts(taskId);
            if (request === latestRequest.current) setLoaded({ status: 'ready', counts });
        } catch (error: unknown) {
            if (request !== latestRequest.current) return;

            // A failed refresh keeps a chart that is already on screen, but marks it stale so the page
            // does not claim to be live while showing old numbers; the one exception is when the
            // server says the user may no longer see this task, which the page must not keep
            // showing. Without a chart there is nothing to keep, and this request may have replaced
            // the initial load, so the failure has to be shown or the page would wait on its
            // spinner for ever.
            const code = (error as { code?: number }).code;
            setLoaded((current) => (
                current.status === 'ready' && ![401, 403, 404].includes(code) ?
                    { ...current, stale: true } : { status: 'failed', code }
            ));
        }
    }, [taskId]);

    useEffect(() => {
        load();
    }, [load]);

    const liveStatus = useLiveUpdates(taskId, refresh);

    let content: JSX.Element;
    if (loaded.status === 'loading') {
        content = <CVATLoadingSpinner />;
    } else if (loaded.status === 'failed') {
        const { retryable, ...text } = describeFailure(loaded.code);
        content = (
            <Result
                className='cvat-annotation-stats-error'
                status='error'
                extra={retryable ? <Button type='primary' onClick={load}>Retry</Button> : null}
                {...text}
            />
        );
    } else if (loaded.counts.total === 0) {
        content = (
            <Empty
                className='cvat-annotation-stats-empty'
                description='No annotations in this task yet'
            />
        );
    } else {
        content = <AnnotationCountsChart labels={loaded.counts.labels} />;
    }

    return (
        <div className='cvat-annotation-stats-page'>
            <Row align='middle' className='cvat-annotation-stats-header'>
                <Col>
                    <GoBackButton />
                </Col>
                <Col offset={1}>
                    <Title level={4} className='cvat-text-color'>
                        {`Annotations per class, task #${taskId}`}
                    </Title>
                </Col>
                {loaded.status === 'ready' && (
                    <Col offset={1}>
                        <Text className='cvat-annotation-stats-total' type='secondary'>
                            {`${loaded.counts.total.toLocaleString()} annotations`}
                        </Text>
                    </Col>
                )}
                {loaded.status === 'ready' && loaded.stale && (
                    <Col offset={1} className='cvat-annotation-stats-stale'>
                        <Text type='warning'>Could not refresh, these numbers may be out of date.</Text>
                        <Button type='link' size='small' onClick={refresh}>Refresh</Button>
                    </Col>
                )}
                <Col flex='auto' className='cvat-annotation-stats-live'>
                    <span role='status' aria-live='polite'>
                        <Badge {...LIVE_BADGE[liveStatus]} />
                    </span>
                </Col>
            </Row>
            {content}
        </div>
    );
}
