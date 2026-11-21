// SPDX-License-Identifier: MIT

import React, { useEffect, useRef } from 'react';
import { Chart } from 'chart.js/auto';

export interface LabelCount {
    id: number;
    name: string;
    color: string;
    count: number;
}

interface Props {
    labels: LabelCount[];
}

const BAR_HEIGHT = 24;
const AXIS_HEIGHT = 48;
const FALLBACK_COLOR = '#8c8c8c';

export default function AnnotationCountsChart({ labels }: Readonly<Props>): JSX.Element {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const chartRef = useRef<Chart<'bar', number[]> | null>(null);

    useEffect(() => {
        const textColor = getComputedStyle(canvasRef.current).color;
        const chart = new Chart<'bar', number[]>(canvasRef.current, {
            type: 'bar',
            data: { labels: [], datasets: [{ data: [], backgroundColor: [] }] },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    x: { beginAtZero: true, ticks: { color: textColor, precision: 0 } },
                    y: { ticks: { color: textColor, autoSkip: false } },
                },
                plugins: { legend: { display: false } },
            },
        });
        chartRef.current = chart;

        return () => {
            chart.destroy();
            chartRef.current = null;
        };
    }, []);

    useEffect(() => {
        const chart = chartRef.current;
        chart.data.labels = labels.map((label) => label.name);
        chart.data.datasets[0].data = labels.map((label) => label.count);
        chart.data.datasets[0].backgroundColor = labels.map((label) => label.color || FALLBACK_COLOR);
        chart.update();
    }, [labels]);

    return (
        <div
            className='cvat-annotation-stats-chart'
            style={{ height: labels.length * BAR_HEIGHT + AXIS_HEIGHT }}
        >
            <canvas ref={canvasRef} role='img' aria-label='Annotations per class' />
        </div>
    );
}
