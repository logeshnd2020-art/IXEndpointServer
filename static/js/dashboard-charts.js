/**
 * Small chart renderers with no external chart library / CDN dependency:
 * a donut/ring (Active/Idle/Sleep composition) and a per-day stacked
 * trend bar chart for week/month reports. All values must come from the
 * caller's real API data -- these renderers never invent numbers.
 */
const IXCharts = (() => {

    function renderDonut(container, { activeSeconds, idleSeconds, sleepSeconds, productivityPercent }) {
        const total = Math.max(activeSeconds + idleSeconds + sleepSeconds, 1);
        const activePct = (activeSeconds / total) * 100;
        const idlePct = (idleSeconds / total) * 100;
        const sleepPct = 100 - activePct - idlePct;

        const a1 = activePct;
        const a2 = a1 + idlePct;

        container.innerHTML = `
            <div class="d-flex align-items-center gap-3">
                <div class="ix-donut" style="background: conic-gradient(
                    var(--ix-online) 0% ${a1}%,
                    var(--ix-idle) ${a1}% ${a2}%,
                    var(--ix-sleep) ${a2}% 100%
                );">
                    <div class="ix-donut-label">
                        <div class="ix-donut-pct">${IXFormat.pct(productivityPercent)}</div>
                        <div class="ix-donut-caption">Productive</div>
                    </div>
                </div>
                <div class="ix-donut-legend">
                    <div class="row-label">
                        <span class="ix-legend-swatch" style="background: var(--ix-online);"></span>Active
                        <span class="row-value">${IXFormat.duration(activeSeconds)}</span>
                    </div>
                    <div class="row-label">
                        <span class="ix-legend-swatch" style="background: var(--ix-idle);"></span>Idle
                        <span class="row-value">${IXFormat.duration(idleSeconds)}</span>
                    </div>
                    <div class="row-label">
                        <span class="ix-legend-swatch" style="background: var(--ix-sleep);"></span>Sleep / Gap
                        <span class="row-value">${IXFormat.duration(sleepSeconds)}</span>
                    </div>
                    <div class="ix-excluded-note">Sleep / Gap is excluded from monitored time</div>
                </div>
            </div>
        `;
    }

    function renderTrend(container, dailyRows) {
        if (!dailyRows || !dailyRows.length) {
            container.innerHTML = `<div class="text-muted small">No data available for this period.</div>`;
            return;
        }

        const DAY_SECONDS = 86400;

        const bars = dailyRows.map(row => {
            const activePct = (row.active_seconds / DAY_SECONDS) * 100;
            const idlePct = (row.idle_seconds / DAY_SECONDS) * 100;
            const sleepPct = (row.sleep_seconds / DAY_SECONDS) * 100;
            return `
                <div class="ix-trend-bar" title="${IXFormat.date(row.period_start)}: Active ${IXFormat.duration(row.active_seconds)}, Idle ${IXFormat.duration(row.idle_seconds)}, Sleep ${IXFormat.duration(row.sleep_seconds)}">
                    <div class="ix-trend-bar-seg sleep" style="height: ${sleepPct}%;"></div>
                    <div class="ix-trend-bar-seg idle" style="height: ${idlePct}%;"></div>
                    <div class="ix-trend-bar-seg active" style="height: ${activePct}%;"></div>
                </div>
            `;
        }).join("");

        const labels = dailyRows.map(row => `<span>${IXFormat.dayLabel(row.period_start)}</span>`).join("");

        container.innerHTML = `
            <div class="ix-trend-chart">${bars}</div>
            <div class="ix-trend-labels">${labels}</div>
        `;
    }

    return { renderDonut, renderTrend };
})();
