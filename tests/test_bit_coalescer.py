from inovonics_echostream_processor.bit_coalescer import (
    BitStateCoalescer,
    BitStateCoalescerConfig,
    BitStateUpdate,
    security_event_to_bit_state_updates,
)
from inovonics_echostream_processor.events import SecurityMessageEvent


def test_coalescer_emits_only_after_quiet_period() -> None:
    coalescer = BitStateCoalescer(
        BitStateCoalescerConfig(
            enabled=True,
            quiet_period_ms=500,
            max_hold_ms=2000,
            idle_ttl_ms=10000,
        ),
        now_ms=lambda: 0,
        diff_ms=lambda later, earlier: later - earlier,
    )

    update = BitStateUpdate("B2010203", 1, 1, True)

    assert coalescer.ingest([update], now_ms=0) == []
    ready_updates = coalescer.flush_due(now_ms=500)

    assert len(ready_updates) == 1
    assert ready_updates[0].device_uid_hex == "B2010203"
    assert ready_updates[0].stat_group == 1
    assert ready_updates[0].bit == 1
    assert ready_updates[0].value is True


def test_coalescer_suppresses_rapid_toggle_bursts_after_baseline_emit() -> None:
    coalescer = BitStateCoalescer(
        BitStateCoalescerConfig(
            enabled=True,
            quiet_period_ms=500,
            max_hold_ms=2000,
            idle_ttl_ms=10000,
        ),
        now_ms=lambda: 0,
        diff_ms=lambda later, earlier: later - earlier,
    )

    assert coalescer.ingest([BitStateUpdate("B2010203", 1, 1, False)], now_ms=0) == []
    baseline_updates = coalescer.flush_due(now_ms=500)
    assert len(baseline_updates) == 1

    assert coalescer.ingest([BitStateUpdate("B2010203", 1, 1, True)], now_ms=600) == []
    assert coalescer.ingest([BitStateUpdate("B2010203", 1, 1, False)], now_ms=700) == []

    ready_updates = coalescer.flush_due(now_ms=1200)

    assert ready_updates == []


def test_coalescer_eventually_emits_chatty_bits_by_max_hold() -> None:
    coalescer = BitStateCoalescer(
        BitStateCoalescerConfig(
            enabled=True,
            quiet_period_ms=500,
            max_hold_ms=1000,
            idle_ttl_ms=10000,
        ),
        now_ms=lambda: 0,
        diff_ms=lambda later, earlier: later - earlier,
    )

    assert coalescer.ingest([BitStateUpdate("B2010203", 1, 1, False)], now_ms=0) == []
    assert coalescer.ingest([BitStateUpdate("B2010203", 1, 1, True)], now_ms=400) == []
    assert coalescer.ingest([BitStateUpdate("B2010203", 1, 1, False)], now_ms=900) == []

    ready_updates = coalescer.flush_due(now_ms=1000)

    assert len(ready_updates) == 1
    assert ready_updates[0].value is False
    assert ready_updates[0].toggles_suppressed == 2


def test_coalescer_evicts_idle_entries() -> None:
    coalescer = BitStateCoalescer(
        BitStateCoalescerConfig(
            enabled=True,
            quiet_period_ms=0,
            max_hold_ms=1000,
            idle_ttl_ms=100,
        ),
        now_ms=lambda: 0,
        diff_ms=lambda later, earlier: later - earlier,
    )

    ready_updates = coalescer.ingest([BitStateUpdate("B2010203", 0, 4, True)], now_ms=0)
    assert len(ready_updates) == 1
    assert coalescer.entry_count == 1

    coalescer.flush_due(now_ms=100)

    assert coalescer.entry_count == 0


def test_coalescer_can_requeue_failed_publish_attempts() -> None:
    coalescer = BitStateCoalescer(
        BitStateCoalescerConfig(
            enabled=True,
            quiet_period_ms=500,
            max_hold_ms=2000,
            idle_ttl_ms=10000,
        ),
        now_ms=lambda: 0,
        diff_ms=lambda later, earlier: later - earlier,
    )

    ready_updates = coalescer.ingest([BitStateUpdate("B2010203", 1, 1, True)], now_ms=0)
    assert ready_updates == []

    ready_updates = coalescer.flush_due(now_ms=500)
    assert len(ready_updates) == 1

    coalescer.requeue(ready_updates, now_ms=600)
    retried_updates = coalescer.flush_due(now_ms=1100)

    assert len(retried_updates) == 1
    assert retried_updates[0].device_uid_hex == "B2010203"
    assert retried_updates[0].value is True


def test_security_event_bit_state_conversion() -> None:
    event = SecurityMessageEvent(
        raw_message=b"\x72",
        device_uid_hex="B2010203",
        device_serial_number=66051,
        first_hop_hex="11223344",
        trace_count=0,
        hop_count=1,
        mid=178,
        pti=4,
        device_category="SECURITY",
        device_model="EN1210SK",
        signal_level=100,
        signal_margin=50,
        stat1_flags=(True, False, False, True, False, False, False, False),
        stat0_flags=(False, False, False, True, False, True, False, False),
    )

    updates = security_event_to_bit_state_updates(event)

    assert len(updates) == 16
    assert updates[0].stat_group == 1
    assert updates[0].bit == 1
    assert updates[0].value is True
    assert updates[11].stat_group == 0
    assert updates[11].bit == 4
    assert updates[11].value is True


def test_security_event_supported_bits_follow_documented_product_capabilities() -> None:
    from inovonics_echostream_processor import security_event_to_supported_bit_state_updates

    event = SecurityMessageEvent(
        raw_message=b"\x72",
        device_uid_hex="B2010203",
        device_serial_number=66051,
        first_hop_hex="11223344",
        trace_count=0,
        hop_count=1,
        mid=178,
        pti=4,
        device_category="SECURITY",
        device_model="EN1210SK",
        signal_level=100,
        signal_margin=50,
        stat1_flags=(True, False, True, False, True, True, True, True),
        stat0_flags=(True, True, True, True, True, True, True, True),
    )

    updates = security_event_to_supported_bit_state_updates(event)

    assert {(update.stat_group, update.protocol_bit) for update in updates} == {
        (1, 0),
        (0, 3),
        (0, 4),
        (0, 5),
        (0, 6),
    }
    assert all(update.supported is True for update in updates)


def test_unknown_security_model_keeps_all_raw_bits_when_filtering() -> None:
    from inovonics_echostream_processor import security_event_to_supported_bit_state_updates

    event = SecurityMessageEvent(
        raw_message=b"\x72",
        device_uid_hex="B2010203",
        device_model="UNLISTED_MODEL",
        stat1_flags=(False,) * 8,
        stat0_flags=(False,) * 8,
    )

    updates = security_event_to_supported_bit_state_updates(event)

    assert len(updates) == 16
    assert all(update.supported is None for update in updates)
