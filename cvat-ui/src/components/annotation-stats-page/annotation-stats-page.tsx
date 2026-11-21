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

const LIVE_BADGE: Record<LiveStatus, { status: 'processing' | 'success' | 'default'; text: string }> = {
    connecting: { status: 'processing', text: 'Connecting' },
    live: { status: 'success', text: 'Live' },
    closed: { status: 'default', text: 'Not live' },
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
    | { status: 'ready'; counts: TaskAnnotationCounts }
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
            const code = (error as { code?: number }).code;
            // A failed refresh keeps the last good chart, except when the server says the user may no
            // longer see this task, which the page must not keep showing.
            if (request === latestRequest.current && [401, 403, 404].includes(code)) {
                setLoaded({ status: 'failed', code });
            }
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
                <Col flex='auto' className='cvat-annotation-stats-live'>
                    <Badge {...LIVE_BADGE[liveStatus]} />
                </Col>
            </Row>
            {content}
        </div>
    );
}
