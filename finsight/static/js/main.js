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
    initializeLandingPage();
});

/**
 * Landing Page Interactive UI Logic
 */
function initializeLandingPage() {
    // 1. Sticky Navbar Scroll State
    const navbar = document.getElementById('landingNavbar');
    if (navbar) {
        const toggleScrolled = () => {
            if (window.scrollY > 20) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        };
        window.addEventListener('scroll', toggleScrolled);
        toggleScrolled(); // Initial check on load
    }

    // 2. Hamburger Mobile Navigation Toggle
    const hamburger = document.getElementById('hamburgerToggle');
    const navLinks = document.getElementById('navLinks');
    if (hamburger && navLinks) {
        hamburger.addEventListener('click', () => {
            hamburger.classList.toggle('active');
            navLinks.classList.toggle('active');
            
            const spans = hamburger.querySelectorAll('span');
            if (hamburger.classList.contains('active')) {
                spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
                spans[1].style.opacity = '0';
                spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
            } else {
                spans[0].style.transform = 'none';
                spans[1].style.opacity = '1';
                spans[2].style.transform = 'none';
            }
        });

        // Auto-close menu when clicking a link
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                hamburger.classList.remove('active');
                navLinks.classList.remove('active');
                
                const spans = hamburger.querySelectorAll('span');
                spans[0].style.transform = 'none';
                spans[1].style.opacity = '1';
                spans[2].style.transform = 'none';
            });
        });
    }

    // 3. Scroll Reveal (Fade-in + Slide-up)
    const revealElements = document.querySelectorAll('.scroll-reveal');
    if (revealElements.length > 0) {
        const revealObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('active');
                    revealObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
        revealElements.forEach(el => revealObserver.observe(el));
    }

    // 4. Stats Counter Intersection Trigger
    const statsSection = document.querySelector('.stats-bar-section');
    if (statsSection) {
        const observer = new IntersectionObserver((entries, obs) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateLandingStats();
                    obs.unobserve(entry.target);
                }
            });
        }, { threshold: 0.15 });
        observer.observe(statsSection);
    }

    // 5. Active Navbar Links Highlighting on Scroll
    const sections = document.querySelectorAll('header[id], section[id], footer[id]');
    const navItems = document.querySelectorAll('.nav-link');
    if (sections.length > 0 && navItems.length > 0) {
        window.addEventListener('scroll', () => {
            let currentSectionId = '';
            sections.forEach(sec => {
                const sectionTop = sec.offsetTop;
                if (window.scrollY >= sectionTop - 160) {
                    currentSectionId = sec.getAttribute('id');
                }
            });

            if (currentSectionId) {
                navItems.forEach(item => {
                    item.classList.remove('active');
                    const href = item.getAttribute('href');
                    if (href === '#' && currentSectionId === 'hero') {
                        item.classList.add('active');
                    } else if (href === '#' + currentSectionId) {
                        item.classList.add('active');
                    }
                });
            }
        });
    }
}

/**
 * Animates integer and decimal values for the stats numbers
 */
function animateLandingStats() {
    const stats = document.querySelectorAll('.stat-number');
    stats.forEach(el => {
        const target = parseFloat(el.getAttribute('data-target'));
        const prefix = el.getAttribute('data-prefix') || '';
        const suffix = el.getAttribute('data-suffix') || '';
        const decimals = parseInt(el.getAttribute('data-decimals') || '0', 10);
        if (isNaN(target)) return;

        const duration = 1200; // Animation length in ms
        const frameRate = 1000 / 60; // 60 Frames per second
        const totalFrames = Math.round(duration / frameRate);
        let frame = 0;
        const increment = target / totalFrames;

        const interval = setInterval(() => {
            frame++;
            const current = increment * frame;
            el.textContent = prefix + current.toFixed(decimals) + suffix;

            if (frame >= totalFrames) {
                clearInterval(interval);
                el.textContent = prefix + target.toFixed(decimals) + suffix;
            }
        }, frameRate);
    });
}
