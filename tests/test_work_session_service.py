from datetime import datetime, timedelta, timezone

from app.services.work_session_service import (
    OFF_SESSION_CEILING_SECONDS,
    SUSTAINED_RUN_SECONDS,
    WorkSessionClassifier,
)

from tests.conftest import utc


def _run(start, end, monitored):
    return (start, end, monitored)


def test_has_confirmed_sleep_evidence_is_always_false_today():
    """
    No current agent version sends any sleep/power-state signal (verified
    against AgentHeartbeatRequest and every other agent-facing schema).
    Duration alone must never be treated as proof of sleep -- so this must
    return False regardless of how short, long, or overnight the gap is.
    """
    cases = [
        (utc(2026, 1, 1, 0, 0, 0), utc(2026, 1, 1, 0, 0, 5)),  # 5 seconds
        (utc(2026, 1, 1, 0, 0, 0), utc(2026, 1, 1, 0, 5, 0)),  # 5 minutes
        (utc(2026, 1, 1, 19, 0, 0), utc(2026, 1, 2, 10, 0, 0)),  # 15 hours, overnight
        (utc(2026, 1, 1, 2, 0, 0), utc(2026, 1, 1, 2, 5, 0)),  # 2 AM, short
    ]
    for start, end in cases:
        assert WorkSessionClassifier.has_confirmed_sleep_evidence(start, end) is False


def test_confirmed_monitored_run_passes_through_unchanged():
    start = utc(2026, 1, 1, 9, 0, 0)
    end = start + timedelta(seconds=SUSTAINED_RUN_SECONDS)  # exactly at the bar

    result = WorkSessionClassifier.classify([_run(start, end, True)])

    assert result == [{"start": start, "end": end, "monitored": True, "gap_type": None}]


def test_unconfirmed_monitored_run_is_absorbed_into_surrounding_gap():
    """
    A monitored run shorter than SUSTAINED_RUN_SECONDS is a stutter, not
    reliable evidence -- it must never stand alone as ACTIVE/IDLE-eligible,
    and any gap it's adjacent to must not be classified as if real
    evidence flanked it.
    """
    gap_start = utc(2026, 1, 1, 9, 0, 0)
    stutter_start = gap_start + timedelta(hours=5)
    stutter_end = stutter_start + timedelta(seconds=20)  # well under 180s
    gap2_end = stutter_end + timedelta(hours=5)

    raw = [
        _run(gap_start, stutter_start, False),
        _run(stutter_start, stutter_end, True),
        _run(stutter_end, gap2_end, False),
    ]

    result = WorkSessionClassifier.classify(raw)

    # The stutter must not appear as its own monitored segment; both gaps
    # (and the stutter between them) coalesce into one OFF_SESSION span.
    assert len(result) == 1
    assert result[0]["monitored"] is False
    assert result[0]["gap_type"] == "OFF_SESSION"
    assert result[0]["start"] == gap_start
    assert result[0]["end"] == gap2_end


def test_gap_confirmed_both_sides_within_ceiling_is_monitoring_gap():
    before_start = utc(2026, 1, 1, 9, 0, 0)
    before_end = before_start + timedelta(seconds=SUSTAINED_RUN_SECONDS + 60)
    gap_end = before_end + timedelta(seconds=OFF_SESSION_CEILING_SECONDS - 1)
    after_end = gap_end + timedelta(seconds=SUSTAINED_RUN_SECONDS + 60)

    raw = [
        _run(before_start, before_end, True),
        _run(before_end, gap_end, False),
        _run(gap_end, after_end, True),
    ]

    result = WorkSessionClassifier.classify(raw)
    gap = next(s for s in result if not s["monitored"])

    assert gap["gap_type"] == "MONITORING_GAP"
    assert gap["gap_type"] != "SLEEP_CONFIRMED"


def test_gap_confirmed_both_sides_exceeding_ceiling_is_off_session():
    before_start = utc(2026, 1, 1, 9, 0, 0)
    before_end = before_start + timedelta(seconds=SUSTAINED_RUN_SECONDS + 60)
    gap_end = before_end + timedelta(seconds=OFF_SESSION_CEILING_SECONDS + 1)
    after_end = gap_end + timedelta(seconds=SUSTAINED_RUN_SECONDS + 60)

    raw = [
        _run(before_start, before_end, True),
        _run(before_end, gap_end, False),
        _run(gap_end, after_end, True),
    ]

    result = WorkSessionClassifier.classify(raw)
    gap = next(s for s in result if not s["monitored"])

    assert gap["gap_type"] == "OFF_SESSION"


def test_gap_missing_evidence_on_one_side_is_off_session_regardless_of_duration():
    """
    Evidence quality, not duration, is the primary gate: even a SHORT gap
    must be OFF_SESSION if it isn't flanked by confirmed evidence on both
    sides -- duration alone can never override a missing-evidence verdict.
    """
    before_start = utc(2026, 1, 1, 9, 0, 0)
    before_end = before_start + timedelta(seconds=SUSTAINED_RUN_SECONDS + 60)
    gap_end = before_end + timedelta(seconds=30)  # tiny gap, far below the ceiling
    stutter_end = gap_end + timedelta(seconds=20)  # unconfirmed run after it

    raw = [
        _run(before_start, before_end, True),
        _run(before_end, gap_end, False),
        _run(gap_end, stutter_end, True),  # unconfirmed
    ]

    result = WorkSessionClassifier.classify(raw)

    assert len(result) == 2
    assert result[0]["monitored"] is True
    assert result[1]["monitored"] is False
    assert result[1]["gap_type"] == "OFF_SESSION"


def test_no_clock_hour_dependency():
    """
    The identical shape (confirmed run, gap, confirmed run) must classify
    identically regardless of what hour of day it occurs at -- 2 AM and
    2 PM must produce the same verdict for the same durations.
    """

    def _shape(base):
        before_end = base + timedelta(seconds=SUSTAINED_RUN_SECONDS + 60)
        gap_end = before_end + timedelta(seconds=5000)  # > ceiling
        after_end = gap_end + timedelta(seconds=SUSTAINED_RUN_SECONDS + 60)
        return [
            _run(base, before_end, True),
            _run(before_end, gap_end, False),
            _run(gap_end, after_end, True),
        ]

    result_2am = WorkSessionClassifier.classify(_shape(utc(2026, 1, 1, 2, 0, 0)))
    result_2pm = WorkSessionClassifier.classify(_shape(utc(2026, 1, 1, 14, 0, 0)))

    gap_2am = next(s for s in result_2am if not s["monitored"])
    gap_2pm = next(s for s in result_2pm if not s["monitored"])

    assert gap_2am["gap_type"] == gap_2pm["gap_type"] == "OFF_SESSION"


def test_no_weekday_weekend_dependency():
    """
    2026-01-03 is a Saturday, 2026-01-06 is a Tuesday. Identical shape,
    identical duration -- identical verdict.
    """

    def _shape(base):
        before_end = base + timedelta(seconds=SUSTAINED_RUN_SECONDS + 60)
        gap_end = before_end + timedelta(seconds=1000)  # < ceiling
        after_end = gap_end + timedelta(seconds=SUSTAINED_RUN_SECONDS + 60)
        return [
            _run(base, before_end, True),
            _run(before_end, gap_end, False),
            _run(gap_end, after_end, True),
        ]

    saturday = WorkSessionClassifier.classify(_shape(utc(2026, 1, 3, 10, 0, 0)))
    tuesday = WorkSessionClassifier.classify(_shape(utc(2026, 1, 6, 10, 0, 0)))

    gap_sat = next(s for s in saturday if not s["monitored"])
    gap_tue = next(s for s in tuesday if not s["monitored"])

    assert gap_sat["gap_type"] == gap_tue["gap_type"] == "MONITORING_GAP"


def test_no_midnight_classification_dependency():
    """
    A confirmed monitored run spanning midnight must pass through as ONE
    unsplit, unmisclassified segment -- classify() never inspects a
    timestamp's calendar date.
    """
    start = utc(2026, 1, 1, 21, 0, 0)  # 9 PM
    end = utc(2026, 1, 2, 0, 30, 0)  # 12:30 AM next day

    result = WorkSessionClassifier.classify([_run(start, end, True)])

    assert result == [{"start": start, "end": end, "monitored": True, "gap_type": None}]


def test_monitoring_gap_is_never_sleep_confirmed():
    """
    MONITORING_GAP must never be indistinguishable from SLEEP_CONFIRMED in
    the type system's output -- they are always distinct string values,
    and given no sleep-evidence signal exists, only MONITORING_GAP/
    OFF_SESSION are ever actually produced.
    """
    before_start = utc(2026, 1, 1, 9, 0, 0)
    before_end = before_start + timedelta(seconds=SUSTAINED_RUN_SECONDS + 60)
    gap_end = before_end + timedelta(seconds=500)
    after_end = gap_end + timedelta(seconds=SUSTAINED_RUN_SECONDS + 60)

    raw = [
        _run(before_start, before_end, True),
        _run(before_end, gap_end, False),
        _run(gap_end, after_end, True),
    ]

    result = WorkSessionClassifier.classify(raw)
    gap = next(s for s in result if not s["monitored"])

    assert gap["gap_type"] == "MONITORING_GAP"
    assert gap["gap_type"] != "SLEEP_CONFIRMED"


def test_wfh_flexible_hours_scenario():
    """
    10:00-16:00 work, 16:00-21:00 absence, 21:00-00:30 work (crossing
    midnight), 07:00-09:00 work (the next day). None of the gaps must be
    classified using clock time -- 16:00-21:00 (afternoon/evening) and
    the implicit 00:30-07:00 overnight gap must both resolve via the same
    evidence-based rule, and neither work block (including the one
    crossing midnight) may be affected by its own clock hours.
    """
    day1 = utc(2026, 1, 1, 0, 0, 0)

    block1_start = day1 + timedelta(hours=10)
    block1_end = day1 + timedelta(hours=16)

    block2_start = day1 + timedelta(hours=21)
    block2_end = day1 + timedelta(hours=24, minutes=30)  # 00:30 next day

    block3_start = day1 + timedelta(days=1, hours=7)
    block3_end = day1 + timedelta(days=1, hours=9)

    raw = [
        _run(block1_start, block1_end, True),
        _run(block1_end, block2_start, False),  # 16:00-21:00, 5h absence
        _run(block2_start, block2_end, True),  # 21:00-00:30, crosses midnight
        _run(block2_end, block3_start, False),  # 00:30-07:00, 6.5h absence
        _run(block3_start, block3_end, True),
    ]

    result = WorkSessionClassifier.classify(raw)

    assert [s["monitored"] for s in result] == [True, False, True, False, True]
    assert result[0]["start"] == block1_start and result[0]["end"] == block1_end
    assert result[1]["gap_type"] == "OFF_SESSION"
    assert result[2]["start"] == block2_start and result[2]["end"] == block2_end  # unsplit across midnight
    assert result[3]["gap_type"] == "OFF_SESSION"
    assert result[4]["start"] == block3_start and result[4]["end"] == block3_end


def test_ixmac007_real_overnight_stutter_shape():
    """
    Direct reproduction of the real IXMAC007 shape: confirmed evening
    activity ending 2026-09-03 18:46:39, silence until an isolated 20s
    heartbeat pair at 10:29:01-10:29:21 the next morning, another 230s
    gap, then genuine sustained resumption from 10:33:11. The isolated
    pair must never be accepted as evidence of resumption -- the whole
    span from the evening through 10:33:11 must be ONE OFF_SESSION
    segment, never SLEEP_CONFIRMED, never split into a spurious ACTIVE
    sliver at the stutter.
    """
    evening_start = datetime(2026, 9, 3, 17, 0, 0, tzinfo=timezone.utc)
    evening_end = datetime(2026, 9, 3, 18, 46, 39, tzinfo=timezone.utc)
    stutter_start = datetime(2026, 9, 4, 10, 29, 1, tzinfo=timezone.utc)
    stutter_end = datetime(2026, 9, 4, 10, 29, 21, tzinfo=timezone.utc)  # 20s -- unconfirmed
    resume_start = datetime(2026, 9, 4, 10, 33, 11, tzinfo=timezone.utc)
    resume_end = datetime(2026, 9, 4, 11, 33, 11, tzinfo=timezone.utc)

    raw = [
        _run(evening_start, evening_end, True),
        _run(evening_end, stutter_start, False),
        _run(stutter_start, stutter_end, True),  # unconfirmed
        _run(stutter_end, resume_start, False),
        _run(resume_start, resume_end, True),
    ]

    result = WorkSessionClassifier.classify(raw)

    assert len(result) == 3
    assert result[0] == {"start": evening_start, "end": evening_end, "monitored": True, "gap_type": None}
    assert result[1]["monitored"] is False
    assert result[1]["gap_type"] == "OFF_SESSION"
    assert result[1]["gap_type"] != "SLEEP_CONFIRMED"
    assert result[1]["start"] == evening_end
    assert result[1]["end"] == resume_start  # the stutter is fully absorbed
    assert result[2]["monitored"] is True
    assert result[2]["start"] == resume_start
