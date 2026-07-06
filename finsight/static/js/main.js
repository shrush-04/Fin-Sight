/**
 * FinSight Interactive UI Logic
 */

// Count-up animation for financial KPI values
function animateCountUp() {
    const elements = document.querySelectorAll('.count-up');
    elements.forEach(el => {
        const rawValue = el.getAttribute('data-value');
        const target = parseFloat(rawValue);
        if (isNaN(target)) return;

        const isPercentage = el.classList.contains('animate-pct');
        const duration = 800; // Total animation length in ms
        const frameRate = 1000 / 60; // 60 Frames per second
        const totalFrames = Math.round(duration / frameRate);
        let frame = 0;

        const start = 0;
        const increment = (target - start) / totalFrames;

        const interval = setInterval(() => {
            frame++;
            const current = start + increment * frame;

            if (isPercentage) {
                el.textContent = current.toFixed(1);
            } else {
                // Formatting as regular money values
                el.textContent = current.toLocaleString(undefined, { 
                    minimumFractionDigits: 2, 
                    maximumFractionDigits: 2 
                });
            }

            if (frame >= totalFrames) {
                clearInterval(interval);
                if (isPercentage) {
                    el.textContent = target.toFixed(1);
                } else {
                    el.textContent = target.toLocaleString(undefined, { 
                        minimumFractionDigits: 2, 
                        maximumFractionDigits: 2 
                    });
                }
            }
        }, frameRate);
    });
}

// Fills the progress bars smoothly after load
function animateProgressBars() {
    const progressBars = document.querySelectorAll('.progress-bar');
    setTimeout(() => {
        progressBars.forEach(bar => {
            const widthPct = parseFloat(bar.getAttribute('data-width'));
            if (!isNaN(widthPct)) {
                // Clamp width from 0 to 100
                const displayWidth = Math.min(100, Math.max(0, widthPct));
                bar.style.width = displayWidth + '%';
            }
        });
    }, 150);
}

// Chart.js renderers
function initializeCharts() {
    // 1. Expense Donut/Pie Chart
    const donutCtx = document.getElementById('expenseDonutChart');
    if (donutCtx && typeof Chart !== 'undefined') {
        new Chart(donutCtx, {
            type: 'doughnut',
            data: {
                labels: donutLabels,
                datasets: [{
                    data: donutData,
                    backgroundColor: [
                        '#D97757', // Terracotta
                        '#5F8F66', // Forest Green
                        '#D99543', // Gold Amber
                        '#5082A6', // Slate Blue
                        '#8F6DA6', // Soft Purple
                        '#A39E98'  // Muted Grey
                    ],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false // Minimalist look: no heavy legends
                    },
                    tooltip: {
                        titleFont: { family: 'Inter', size: 12 },
                        bodyFont: { family: 'Inter', size: 12 },
                        padding: 10,
                        cornerRadius: 6
                    }
                },
                cutout: '72%'
            }
        });
    }

    // 2. Trend Line Chart (30 Days Daily Income vs Expense)
    const lineCtx = document.getElementById('trendLineChart');
    if (lineCtx && typeof Chart !== 'undefined') {
        new Chart(lineCtx, {
            type: 'line',
            data: {
                labels: lineLabels,
                datasets: [
                    {
                        label: 'Income',
                        data: lineIncomeData,
                        borderColor: '#5F8F66',
                        backgroundColor: 'rgba(95, 143, 102, 0.04)',
                        fill: true,
                        tension: 0.35,
                        borderWidth: 2,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    },
                    {
                        label: 'Expenses',
                        data: lineExpenseData,
                        borderColor: '#D97757',
                        backgroundColor: 'rgba(217, 119, 87, 0.04)',
                        fill: true,
                        tension: 0.35,
                        borderWidth: 2,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            font: { family: 'Inter', size: 11, weight: '500' },
                            boxWidth: 12
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        titleFont: { family: 'Inter', size: 12 },
                        bodyFont: { family: 'Inter', size: 12 },
                        padding: 10,
                        cornerRadius: 6
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { family: 'Inter', size: 10 } }
                    },
                    y: {
                        grid: { color: '#EAE7E2' },
                        ticks: { font: { family: 'Inter', size: 10 } }
                    }
                }
            }
        });
    }
}

// Global script hooks on DOM loading
document.addEventListener("DOMContentLoaded", () => {
    animateCountUp();
    animateProgressBars();
    initializeCharts();
});
