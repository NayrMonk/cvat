// SPDX-License-Identifier: MIT

import './styles.scss';

import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router';
import Title from 'antd/lib/typography/Title';
import { Row, Col } from 'antd/lib/grid';

import { getCore } from 'cvat-core-wrapper';
import GoBackButton from 'components/common/go-back-button';
import CVATLoadingSpinner from 'components/common/loading-spinner';
import AnnotationCountsChart, { LabelCount } from './annotation-counts-chart';

const core = getCore();

interface TaskAnnotationCounts {
    task_id: number;
    total: number;
    labels: LabelCount[];
}

type Loaded =
    | { status: 'loading' }
    | { status: 'ready'; counts: TaskAnnotationCounts }
    | { status: 'failed'; code?: number };

export default function AnnotationStatsPage(): JSX.Element {
    const taskId = +useParams<{ tid: string }>().tid;
    const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' });

    const load = useCallback(async () => {
        setLoaded({ status: 'loading' });
        try {
            const response = await core.server.request(
                `${core.config.backendAPI}/annotation-stats/tasks/${taskId}`,
                { method: 'GET' },
            );
            setLoaded({ status: 'ready', counts: response.data });
        } catch (error: unknown) {
            const code = (error as { code?: number }).code;
            setLoaded({ status: 'failed', code });
        }
    }, [taskId]);

    useEffect(() => {
        load();
    }, [load]);

    let content: JSX.Element | null = null;
    if (loaded.status === 'loading') {
        content = <CVATLoadingSpinner />;
    } else if (loaded.status === 'ready') {
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
            </Row>
            {content}
        </div>
    );
}
