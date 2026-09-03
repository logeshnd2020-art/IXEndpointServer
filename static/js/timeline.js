/**
 * Reusable 24-hour activity timeline renderer.
 *
 * Renders segments (ACTIVE / IDLE / SLEEP_GAP / NO_SESSION, from the
 * /api/device/{id}/timeline?date=... endpoint) positioned on a fixed
 * 24-hour axis anchored to the day's own start (window_start). Any
 * uncovered time is left as empty track background -- this only happens
 * for "today", where the server truncates the window at "now" rather
 * than fabricating data for the future.
 */
const IXTimeline = (() => {

    const LEGEND = [
        { type: "ACTIVE", label: "Active", swatchClass: "ix-timeline-seg-ACTIVE" },
        { type: "IDLE", label: "Idle", swatchClass: "ix-timeline-seg-IDLE" },
        { type: "SLEEP_GAP", label: "Sleep / Gap", swatchClass: "ix-timeline-seg-SLEEP_GAP" },
    ];

    // Human-readable label per raw segment type, shared by the timeline
    // bar's tooltip and the Activity Details list so both always agree.
    const TYPE_LABEL = {
        ACTIVE: "Active",
        IDLE: "Idle",
        SLEEP_GAP: "Sleep",
        NO_SESSION: "No Session",
    };

    /**
     * Coalesces chronologically-adjacent segments of the same type into
     * one. Purely presentational -- concatenates contiguous spans and
     * sums their duration_seconds, so the total time per type is
     * unchanged (sum(merged) === sum(raw) for every type). Two segments
     * are only merged when the first's `end` exactly equals the second's
     * `start` (i.e. truly adjacent, not just same-type elsewhere in the
     * day) so a real intervening segment (e.g. a NO_SESSION gap between
     * two sessions) is never silently absorbed.
     */
    function mergeSegments(segments) {
        if (!segments || !segments.length) return [];

        const merged = [];

        for (const seg of segments) {
            const last = merged[merged.length - 1];
            if (last && last.type === seg.type && last.end === seg.start) {
                last.end = seg.end;
                last.duration_seconds += seg.duration_seconds;
            } else {
                merged.push(Object.assign({}, seg));
            }
        }

        return merged;
    }

    function typeLabel(type) {
        return TYPE_LABEL[type] || type;
    }

    function render(container, timelineData, options = {}) {
        container.innerHTML = "";

        if (!timelineData || !timelineData.window_start) {
            container.innerHTML = `<div class="text-muted small p-2">No timeline data available.</div>`;
            return;
        }

        const dayStart = new Date(timelineData.window_start);
        const dayEnd = new Date(dayStart.getTime() + 24 * 3600 * 1000);
        const dayMs = dayEnd.getTime() - dayStart.getTime();

        // Hour axis labels every 2 hours: 12 AM, 02 AM, ... 10 PM.
        const hoursRow = document.createElement("div");
        hoursRow.className = "ix-timeline-hours";
        for (let h = 0; h < 24; h += 2) {
            const label = h === 0 ? "12 AM" : h < 12 ? `${h} AM` : h === 12 ? "12 PM" : `${h - 12} PM`;
            const span = document.createElement("span");
            span.textContent = label;
            hoursRow.appendChild(span);
        }
        container.appendChild(hoursRow);

        const track = document.createElement("div");
        track.className = "ix-timeline-track";

        // The bar and the Activity Details list are both built from this
        // same merged array (same indices), so a click on segment N in
        // the bar always corresponds to row N in the details list.
        const merged = mergeSegments(timelineData.segments || []);

        if (!merged.length) {
            track.innerHTML = `<div class="text-muted small p-2">No monitoring data for this day.</div>`;
        } else {
            merged.forEach((seg, index) => {
                const start = new Date(seg.start).getTime();
                const end = new Date(seg.end).getTime();
                const leftPct = Math.max(0, ((start - dayStart.getTime()) / dayMs) * 100);
                const widthPct = Math.max(0.15, ((end - start) / dayMs) * 100);

                const el = document.createElement("div");
                el.className = `ix-timeline-seg ix-timeline-seg-${seg.type}`;
                el.style.left = `${leftPct}%`;
                el.style.width = `${widthPct}%`;
                el.dataset.segIndex = index;
                el.title = `${typeLabel(seg.type)} (${IXFormat.duration(seg.duration_seconds)}): `
                    + `${IXFormat.time(seg.start)} - ${IXFormat.time(seg.end)}`;

                if (options.onSegmentClick) {
                    el.classList.add("ix-timeline-seg-clickable");
                    el.addEventListener("click", () => options.onSegmentClick(index, seg));
                }

                track.appendChild(el);
            });
        }

        container.appendChild(track);

        const legend = document.createElement("div");
        legend.className = "ix-timeline-legend";
        legend.innerHTML = LEGEND.map(l => `
            <span><span class="ix-legend-swatch ${l.swatchClass}"></span>${l.label}</span>
        `).join("") + `<span><span class="ix-legend-swatch" style="background: transparent; border: 1px dashed var(--ix-text-faint);"></span>No Session</span>`;
        container.appendChild(legend);
    }

    return { render, mergeSegments, typeLabel };
})();
