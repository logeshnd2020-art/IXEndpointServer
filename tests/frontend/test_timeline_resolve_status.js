/**
 * Focused, dependency-free tests for IXTimeline.resolveStatus() -- the
 * management-facing status resolution layer (7.8.0 evidence layer).
 *
 * Uses only Node's built-in `assert` and `vm` modules -- no package.json,
 * no npm install, nothing new added to this repo's build/test tooling.
 * Run with: node tests/frontend/test_timeline_resolve_status.js
 *
 * NOTE (production-safety / honesty disclosure): this script was written
 * and reviewed but could NOT be executed in the environment this change
 * was implemented in -- no JavaScript runtime (node, npm, or macOS's
 * JavaScriptCore `jsc`) is installed there. It is correct and complete
 * and will run wherever Node.js is available (any normal dev machine or
 * CI runner); the results below were NOT observed in this session and
 * must be re-run and confirmed on a machine with Node before this is
 * treated as verified. See the implementation report for the full
 * disclosure and the static/source-code checks performed instead.
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const SOURCE_PATH = path.join(__dirname, "..", "..", "static", "js", "timeline.js");
const source = fs.readFileSync(SOURCE_PATH, "utf8");

// timeline.js declares `const IXTimeline = (() => {...})();` at top level
// and has no module.exports -- evaluate it in a fresh VM context and
// capture the binding via the script's completion value, without
// modifying the shipped file itself.
const IXTimeline = vm.runInNewContext(source + "\nIXTimeline;", {});

let passed = 0;
let failed = 0;

function test(name, fn) {
    try {
        fn();
        passed++;
        console.log(`  ok  - ${name}`);
    } catch (err) {
        failed++;
        console.error(`FAIL - ${name}`);
        console.error(`       ${err.message}`);
    }
}

function seg(overrides) {
    return Object.assign(
        {
            start: "2026-09-01T09:00:00Z",
            end: "2026-09-01T09:30:00Z",
            type: "MONITORING_GAP",
            duration_seconds: 1800,
            reason: null,
        },
        overrides
    );
}

// --- Each supported reason resolves to its exact management-facing status ---

test("SLEEP resolves to 'Sleep'", () => {
    assert.strictEqual(IXTimeline.resolveStatus(seg({ reason: "SLEEP" })), "Sleep");
});

test("SHUTDOWN (Confirmed Shutdown) resolves to 'Confirmed Shutdown'", () => {
    assert.strictEqual(IXTimeline.resolveStatus(seg({ reason: "SHUTDOWN" })), "Confirmed Shutdown");
});

test("RESTART (Confirmed Restart) resolves to 'Confirmed Restart'", () => {
    assert.strictEqual(IXTimeline.resolveStatus(seg({ reason: "RESTART" })), "Confirmed Restart");
});

test("RESTART_UNPLANNED also resolves to 'Confirmed Restart'", () => {
    assert.strictEqual(IXTimeline.resolveStatus(seg({ reason: "RESTART_UNPLANNED" })), "Confirmed Restart");
});

test("AGENT_STOPPED resolves to 'Agent Stopped'", () => {
    assert.strictEqual(IXTimeline.resolveStatus(seg({ reason: "AGENT_STOPPED" })), "Agent Stopped");
});

test("AGENT_RESTART (Agent Restarted) resolves to 'Agent Restarted'", () => {
    assert.strictEqual(IXTimeline.resolveStatus(seg({ reason: "AGENT_RESTART" })), "Agent Restarted");
});

test("UNEXPECTED_AGENT_RECOVERY also resolves to 'Agent Restarted'", () => {
    assert.strictEqual(IXTimeline.resolveStatus(seg({ reason: "UNEXPECTED_AGENT_RECOVERY" })), "Agent Restarted");
});

test("NETWORK_UNAVAILABLE resolves to 'Network Unavailable'", () => {
    assert.strictEqual(IXTimeline.resolveStatus(seg({ reason: "NETWORK_UNAVAILABLE" })), "Network Unavailable");
});

test("SERVER_UNAVAILABLE resolves to 'Server Unavailable'", () => {
    assert.strictEqual(IXTimeline.resolveStatus(seg({ reason: "SERVER_UNAVAILABLE" })), "Server Unavailable");
});

test("SHUTDOWN_OR_RESTART_PENDING resolves to 'Monitoring Interrupted'", () => {
    assert.strictEqual(
        IXTimeline.resolveStatus(seg({ reason: "SHUTDOWN_OR_RESTART_PENDING" })),
        "Monitoring Interrupted"
    );
});

test("literal MONITORING_INTERRUPTED alias resolves to 'Monitoring Interrupted'", () => {
    assert.strictEqual(IXTimeline.resolveStatus(seg({ reason: "MONITORING_INTERRUPTED" })), "Monitoring Interrupted");
});

test("literal UNKNOWN alias resolves to 'Unknown'", () => {
    assert.strictEqual(IXTimeline.resolveStatus(seg({ reason: "UNKNOWN" })), "Unknown");
});

// --- Fallbacks ---

test("MONITORING_GAP with no reason falls back to 'Monitoring Gap'", () => {
    assert.strictEqual(IXTimeline.resolveStatus(seg({ type: "MONITORING_GAP", reason: null })), "Monitoring Gap");
});

test("NO_SESSION is unaffected and still resolves to 'No Session'", () => {
    assert.strictEqual(
        IXTimeline.resolveStatus(seg({ type: "NO_SESSION", reason: null, duration_seconds: 120 })),
        "No Session"
    );
});

test("an unrecognized reason string falls back to the type label rather than throwing", () => {
    assert.strictEqual(
        IXTimeline.resolveStatus(seg({ type: "MONITORING_GAP", reason: "SOME_FUTURE_REASON_NOT_YET_MAPPED" })),
        "Monitoring Gap"
    );
});

// --- The specific defect this change fixes: a supported reason must
//     NEVER still render as "Monitoring Gap". ---

test("a segment with ANY supported reason never renders as 'Monitoring Gap'", () => {
    const supportedReasons = [
        "SLEEP", "RESTART", "RESTART_UNPLANNED", "SHUTDOWN", "AGENT_STOPPED",
        "AGENT_RESTART", "UNEXPECTED_AGENT_RECOVERY", "NETWORK_UNAVAILABLE",
        "SERVER_UNAVAILABLE", "SHUTDOWN_OR_RESTART_PENDING",
    ];
    for (const reason of supportedReasons) {
        const status = IXTimeline.resolveStatus(seg({ reason }));
        assert.notStrictEqual(status, "Monitoring Gap", `reason=${reason} incorrectly rendered as Monitoring Gap`);
    }
});

// --- resolveStatus() is read-only: never mutates the segment it's given ---

test("resolveStatus does not modify seg.type, duration_seconds, start, or end", () => {
    const original = seg({ reason: "SLEEP" });
    const snapshot = JSON.parse(JSON.stringify(original));

    IXTimeline.resolveStatus(original);

    assert.deepStrictEqual(original, snapshot);
    assert.strictEqual(original.type, snapshot.type);
    assert.strictEqual(original.duration_seconds, snapshot.duration_seconds);
    assert.strictEqual(original.start, snapshot.start);
    assert.strictEqual(original.end, snapshot.end);
});

// --- Static proof that the Activity Details table actually calls
//     resolveStatus() rather than the old typeLabel-only rendering. ---

test("templates/device.html's Status column calls IXTimeline.resolveStatus(seg)", () => {
    const templatePath = path.join(__dirname, "..", "..", "templates", "device.html");
    const templateSource = fs.readFileSync(templatePath, "utf8");

    assert.ok(
        templateSource.includes("IXTimeline.resolveStatus(seg)"),
        "device.html's Activity Details row template must call IXTimeline.resolveStatus(seg)"
    );
    assert.ok(
        !templateSource.includes("IXTimeline.typeLabel(seg.type)"),
        "device.html's Status column must no longer call typeLabel(seg.type) directly " +
        "(it should have been replaced by resolveStatus(seg))"
    );
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exitCode = failed > 0 ? 1 : 0;
