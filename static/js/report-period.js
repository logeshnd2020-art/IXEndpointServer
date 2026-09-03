/**
 * Reusable report-period control: Today / Yesterday / This Week / Last
 * Week / This Month / Last Month / Custom Range.
 *
 * Dates are anchored to the SERVER's timezone (Asia/Kolkata, matching
 * ProductivityService/ProductivityReportService's existing local-day
 * convention) rather than the viewing browser's local timezone, so a
 * "Today" click always maps to the same calendar day the server itself
 * uses for its day boundaries.
 */
const IXReportPeriod = (() => {

    const PRESETS = [
        { key: "today", label: "Today" },
        { key: "yesterday", label: "Yesterday" },
        { key: "this_week", label: "This Week" },
        { key: "last_week", label: "Last Week" },
        { key: "this_month", label: "This Month" },
        { key: "last_month", label: "Last Month" },
        { key: "custom", label: "Custom Range" },
    ];

    const SERVER_TZ = "Asia/Kolkata";

    function serverToday() {
        const parts = new Intl.DateTimeFormat("en-CA", {
            timeZone: SERVER_TZ, year: "numeric", month: "2-digit", day: "2-digit",
        }).formatToParts(new Date());
        const map = {};
        parts.forEach(p => { map[p.type] = p.value; });
        // A plain calendar-day value -- only Y/M/D arithmetic is ever done
        // on it below, so the local browser timezone this Date object
        // nominally carries doesn't matter.
        return new Date(`${map.year}-${map.month}-${map.day}T00:00:00`);
    }

    function addDays(d, n) {
        const copy = new Date(d);
        copy.setDate(copy.getDate() + n);
        return copy;
    }

    function startOfWeekMonday(d) {
        const day = d.getDay(); // 0=Sun..6=Sat
        const diff = day === 0 ? 6 : day - 1;
        return addDays(d, -diff);
    }

    function startOfMonth(d) {
        return new Date(d.getFullYear(), d.getMonth(), 1);
    }

    function endOfMonth(d) {
        return new Date(d.getFullYear(), d.getMonth() + 1, 0);
    }

    function rangeFor(presetKey, customStart, customEnd) {
        const today = serverToday();

        switch (presetKey) {
            case "today":
                return { start: today, end: today };
            case "yesterday": {
                const y = addDays(today, -1);
                return { start: y, end: y };
            }
            case "this_week":
                return { start: startOfWeekMonday(today), end: today };
            case "last_week": {
                const thisMon = startOfWeekMonday(today);
                const lastMon = addDays(thisMon, -7);
                const lastSun = addDays(thisMon, -1);
                return { start: lastMon, end: lastSun };
            }
            case "this_month":
                return { start: startOfMonth(today), end: today };
            case "last_month": {
                const prevMonthAnchor = new Date(today.getFullYear(), today.getMonth() - 1, 1);
                return { start: startOfMonth(prevMonthAnchor), end: endOfMonth(prevMonthAnchor) };
            }
            case "custom":
                return {
                    start: customStart ? new Date(customStart + "T00:00:00") : today,
                    end: customEnd ? new Date(customEnd + "T00:00:00") : today,
                };
            default:
                return { start: today, end: today };
        }
    }

    function mount(container, { onChange, defaultPreset = "today" } = {}) {
        let activePreset = defaultPreset;

        container.innerHTML = `
            <div class="ix-report-period" id="ixPeriodButtons"></div>
            <div class="ix-period-custom" id="ixPeriodCustom">
                <span class="ix-form-label mb-0">Start</span>
                <input type="date" id="ixPeriodStart">
                <span class="ix-form-label mb-0">End</span>
                <input type="date" id="ixPeriodEnd">
                <button type="button" class="btn ix-btn-primary btn-sm" id="ixPeriodApply">Apply</button>
            </div>
            <div class="ix-period-label" id="ixPeriodLabel"></div>
        `;

        const buttonsEl = container.querySelector("#ixPeriodButtons");
        const customEl = container.querySelector("#ixPeriodCustom");
        const startInput = container.querySelector("#ixPeriodStart");
        const endInput = container.querySelector("#ixPeriodEnd");
        const applyBtn = container.querySelector("#ixPeriodApply");
        const labelEl = container.querySelector("#ixPeriodLabel");

        PRESETS.forEach(p => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "ix-period-btn";
            btn.textContent = p.label;
            btn.dataset.key = p.key;
            btn.addEventListener("click", () => selectPreset(p.key));
            buttonsEl.appendChild(btn);
        });

        function highlight(key) {
            buttonsEl.querySelectorAll(".ix-period-btn").forEach(b => {
                b.classList.toggle("active", b.dataset.key === key);
            });
            customEl.classList.toggle("show", key === "custom");
        }

        function emit(range) {
            const startStr = IXFormat.isoDate(range.start);
            const endStr = IXFormat.isoDate(range.end);
            const sameDay = startStr === endStr;
            labelEl.textContent = sameDay
                ? `Showing: ${IXFormat.date(range.start)} (Asia/Kolkata)`
                : `Showing: ${IXFormat.date(range.start)} - ${IXFormat.date(range.end)} (Asia/Kolkata)`;

            if (onChange) {
                onChange({ preset: activePreset, start_date: startStr, end_date: endStr });
            }
        }

        function selectPreset(key) {
            activePreset = key;
            highlight(key);

            if (key === "custom") {
                if (!startInput.value) startInput.value = IXFormat.isoDate(serverToday());
                if (!endInput.value) endInput.value = IXFormat.isoDate(serverToday());
                emit(rangeFor("custom", startInput.value, endInput.value));
                return;
            }

            emit(rangeFor(key));
        }

        applyBtn.addEventListener("click", () => {
            if (!startInput.value || !endInput.value) return;
            emit(rangeFor("custom", startInput.value, endInput.value));
        });

        selectPreset(defaultPreset);

        return {
            getActivePreset: () => activePreset,
        };
    }

    return { mount, serverToday, rangeFor };
})();
