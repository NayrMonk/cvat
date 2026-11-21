// SPDX-License-Identifier: MIT

import React, { useEffect, useRef } from 'react';
import { Chart } from 'chart.js/auto';

export type Source = 'file' | 'manual' | 'auto' | 'semi-auto' | 'consensus';

export interface LabelCount {
    id: number;
    name: string;
    count: number;
    by_source: Record<Source, number>;
}

interface Props {
    labels: LabelCount[];
}

const BAR_HEIGHT = 24;
const AXIS_HEIGHT = 80;

// Where an annotation came from, in stacking order from the left of each bar.
const SOURCES: { key: Source; title: string; color: string }[] = [
    { key: 'file', title: 'Imported from file', color: '#6c8ebf' },
    { key: 'manual', title: 'Drawn manually', color: '#2f9e6e' },
    { key: 'auto', title: 'Automatic', color: '#e08a1e' },
    { key: 'semi-auto', title: 'Semi-automatic', color: '#9467bd' },
    { key: 'consensus', title: 'Consensus', color: '#c2547a' },
];

export default function AnnotationCountsChart({ labels }: Readonly<Props>): JSX.Element {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const chartRef = useRef<Chart<'bar', number[]> | null>(null);

    useEffect(() => {
        const textColor = getComputedStyle(canvasRef.current).color;
        const chart = new Chart<'bar', number[]>(canvasRef.current, {
            type: 'bar',
            data: {
                labels: [],
                datasets: SOURCES.map(({ title, color }) => ({
                    label: title,
                    data: [],
                    backgroundColor: color,
                })),
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    x: { stacked: true, beginAtZero: true, ticks: { color: textColor, precision: 0 } },
                    y: { stacked: true, ticks: { color: textColor, autoSkip: false } },
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: textColor,
                            // a source that has no annotations in this task is not worth a legend entry
                            filter: (item, data) => data.datasets[item.datasetIndex].data
                                .some((value) => value > 0),
                        },
                    },
                },
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
        SOURCES.forEach(({ key }, index) => {
            chart.data.datasets[index].data = labels.map((label) => label.by_source[key]);
        });
        chart.update();
    }, [labels]);

    return (
        <div
            className='cvat-annotation-stats-chart'
            style={{ height: labels.length * BAR_HEIGHT + AXIS_HEIGHT }}
        >
            <canvas ref={canvasRef} role='img' aria-label='Annotations per class, split by source' />
        </div>
    );
}
