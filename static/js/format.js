/**
 * Shared formatting helpers used across the dashboard pages.
 */
const IXFormat = (() => {

    // Activity Timeline / Activity Details render every timestamp
    // explicitly in Asia/Kolkata, regardless of the viewing browser's own
    // system timezone -- previously `time()` relied on the browser's
    // local setting via toLocaleTimeString() with no timeZone override,
    // which only happened to show IST because this dev machine is itself
    // IST-configured. A viewer on a differently-configured machine would
    // have silently seen the wrong wall-clock time for the same instant.
    const DISPLAY_TIMEZONE = "Asia/Kolkata";

    function duration(totalSeconds) {
        if (totalSeconds === null || totalSeconds === undefined) return "-";
        totalSeconds = Math.max(0, Math.round(totalSeconds));
        const h = Math.floor(totalSeconds / 3600);
        const m = Math.floor((totalSeconds % 3600) / 60);
        const s = Math.floor(totalSeconds % 60);
        if (h > 0) return `${h}h ${m}m`;
        if (m > 0) return `${m}m ${s}s`;
        return `${s}s`;
    }

    // Used by Activity Details only: "20m" / "1h 20m" / "14h 35m" --
    // minute-level precision, no seconds component, matching that
    // table's requested format. Distinct from duration() above (which
    // keeps seconds precision for KPI cards/app usage/etc, unchanged).
    function durationShort(totalSeconds) {
        if (totalSeconds === null || totalSeconds === undefined) return "-";
        totalSeconds = Math.max(0, Math.round(totalSeconds));
        const h = Math.floor(totalSeconds / 3600);
        const m = Math.floor((totalSeconds % 3600) / 60);
        const s = Math.floor(totalSeconds % 60);
        if (h > 0) return `${h}h ${m}m`;
        if (m > 0) return `${m}m`;
        return `${s}s`;
    }

    // "03 Sep 2026"
    function date(isoOrDate) {
        if (!isoOrDate) return "-";
        const d = typeof isoOrDate === "string" ? new Date(isoOrDate) : isoOrDate;
        const day = String(d.getDate()).padStart(2, "0");
        const month = d.toLocaleString(undefined, { month: "short" });
        return `${day} ${month} ${d.getFullYear()}`;
    }

    // "03 Sep"
    function dayLabel(isoOrDate) {
        if (!isoOrDate) return "-";
        const d = typeof isoOrDate === "string" ? new Date(isoOrDate) : isoOrDate;
        const day = String(d.getDate()).padStart(2, "0");
        const month = d.toLocaleString(undefined, { month: "short" });
        return `${day} ${month}`;
    }

    function dateTime(iso) {
        if (!iso) return "-";
        return new Date(iso).toLocaleString();
    }

    // Used by the Activity Timeline (segment tooltips) and Activity
    // Details (Start Time/End Time columns) -- always Asia/Kolkata,
    // explicitly, independent of the viewing browser's own timezone
    // setting. hour12/hour:"numeric" guarantees "10:00 AM" / "3:33 PM"
    // style output (no leading zero on the hour) regardless of the
    // browser's own locale defaults.
    function time(iso) {
        if (!iso) return "-";
        return new Date(iso).toLocaleTimeString([], {
            hour: "numeric",
            minute: "2-digit",
            hour12: true,
            timeZone: DISPLAY_TIMEZONE,
        });
    }

    // Local YYYY-MM-DD (not UTC) -- used for <input type="date"> values
    // and report-period query params.
    function isoDate(d) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        return `${y}-${m}-${day}`;
    }

    function pct(value) {
        if (value === null || value === undefined) return "-";
        return `${Math.max(0, Math.min(100, value)).toFixed(2)}%`;
    }

    // Device system uptime (agent-reported seconds since boot), formatted
    // as "3 days 7 hours 24 minutes" / "7 hours 24 minutes" / "24 minutes".
    // Not the same thing as `duration()` above (session/activity time) --
    // kept separate since the semantics and expected phrasing differ.
    function uptime(totalSeconds) {
        if (totalSeconds === null || totalSeconds === undefined) return null;
        totalSeconds = Math.max(0, Math.round(totalSeconds));

        const days = Math.floor(totalSeconds / 86400);
        const hours = Math.floor((totalSeconds % 86400) / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);

        const parts = [];
        if (days > 0) parts.push(`${days} day${days === 1 ? "" : "s"}`);
        if (days > 0 || hours > 0) parts.push(`${hours} hour${hours === 1 ? "" : "s"}`);
        parts.push(`${minutes} minute${minutes === 1 ? "" : "s"}`);

        return parts.join(" ");
    }

    // Normalizes an agent-reported MAC address string to
    // "XX:XX:XX:XX:XX:XX" (uppercase, colon-separated) for display.
    // Purely cosmetic -- the server stores whatever raw string the agent
    // sent, unmodified; this never invents a value, it only reformats
    // one that's actually present.
    function macAddress(raw) {
        if (!raw) return null;
        const hex = raw.replace(/[^0-9a-fA-F]/g, "");
        if (hex.length !== 12) return raw; // unexpected shape -- show as-is rather than mangle it
        return hex.toUpperCase().match(/.{1,2}/g).join(":");
    }

    return { duration, durationShort, date, dayLabel, dateTime, time, isoDate, pct, uptime, macAddress };
})();
