import time

from inovonics_echostream_processor.device_types import security_status_bit_definition, security_status_capabilities


DEFAULT_QUIET_PERIOD_MS = 500
DEFAULT_MAX_HOLD_MS = 2000
DEFAULT_IDLE_TTL_MS = 900000


class BitStateUpdate(object):
    def __init__(
        self,
        device_uid_hex,
        stat_group,
        bit,
        value,
        source_event_type=None,
        toggles_suppressed=0,
        protocol_bit=None,
        status_name=None,
        status_label=None,
        supported=None,
        reserved=False,
    ):
        self.device_uid_hex = device_uid_hex
        self.stat_group = stat_group
        self.bit = bit
        self.value = bool(value)
        self.source_event_type = source_event_type
        self.toggles_suppressed = toggles_suppressed
        # Keep the historical one-based ``bit`` field while exposing the actual
        # zero-based wire bit used by the EchoStream specification.
        self.protocol_bit = int(protocol_bit) if protocol_bit is not None else max(int(bit) - 1, 0)
        self.status_name = status_name
        self.status_label = status_label
        self.supported = supported
        self.reserved = bool(reserved)

    @property
    def key(self):
        return (self.device_uid_hex, self.stat_group, self.bit)


class BitStateCoalescerConfig(object):
    def __init__(
        self,
        enabled=True,
        quiet_period_ms=DEFAULT_QUIET_PERIOD_MS,
        max_hold_ms=DEFAULT_MAX_HOLD_MS,
        idle_ttl_ms=DEFAULT_IDLE_TTL_MS,
    ):
        self.enabled = bool(enabled)
        self.quiet_period_ms = int(quiet_period_ms)
        self.max_hold_ms = int(max_hold_ms)
        self.idle_ttl_ms = int(idle_ttl_ms)

        if self.quiet_period_ms < 0:
            raise ValueError("quiet_period_ms must be >= 0")
        if self.max_hold_ms <= 0:
            raise ValueError("max_hold_ms must be > 0")
        if self.idle_ttl_ms < 0:
            raise ValueError("idle_ttl_ms must be >= 0")


class _BitStateEntry(object):
    def __init__(self, update, now_ms):
        self.device_uid_hex = update.device_uid_hex
        self.stat_group = update.stat_group
        self.bit = update.bit
        self.update = update
        self.last_emitted_value = None
        self.has_emitted_value = False
        self.pending_value = update.value
        self.pending_started_ms = now_ms
        self.last_changed_ms = now_ms
        self.last_activity_ms = now_ms
        self.source_event_type = update.source_event_type
        self.toggles_suppressed = 0
        self.force_emit_pending = False


class BitStateCoalescer(object):
    def __init__(self, config=None, now_ms=None, diff_ms=None):
        self.config = config or BitStateCoalescerConfig()
        self._entries = {}
        self._now_ms = now_ms or _default_now_ms
        self._diff_ms = diff_ms or _default_diff_ms

    @property
    def entry_count(self):
        return len(self._entries)

    def ingest(self, updates, now_ms=None):
        normalized_updates = _normalize_updates(updates)
        if not normalized_updates:
            return []

        if not self.config.enabled:
            return normalized_updates

        now_ms = self._resolve_now_ms(now_ms)

        for update in normalized_updates:
            self._ingest_update(update, now_ms)

        return self.flush_due(now_ms=now_ms)

    def flush_due(self, now_ms=None):
        if not self.config.enabled:
            return []

        now_ms = self._resolve_now_ms(now_ms)
        ready_updates = []

        for key, entry in list(self._entries.items()):
            if entry.pending_value is not None and self._is_ready_to_emit(entry, now_ms):
                emitted_update = self._emit_entry(entry)
                if emitted_update is not None:
                    ready_updates.append(emitted_update)

            if self._is_idle(entry, now_ms):
                del self._entries[key]

        return ready_updates

    def flush_all(self, now_ms=None):
        if not self.config.enabled:
            return []

        now_ms = self._resolve_now_ms(now_ms)
        ready_updates = []

        for key, entry in list(self._entries.items()):
            if entry.pending_value is not None:
                emitted_update = self._emit_entry(entry)
                if emitted_update is not None:
                    ready_updates.append(emitted_update)

            if self._is_idle(entry, now_ms):
                del self._entries[key]

        return ready_updates

    def requeue(self, updates, now_ms=None):
        normalized_updates = _normalize_updates(updates)
        if not normalized_updates:
            return

        if not self.config.enabled:
            return

        now_ms = self._resolve_now_ms(now_ms)

        for update in normalized_updates:
            self._requeue_update(update, now_ms)

    def clear(self):
        self._entries.clear()

    def _ingest_update(self, update, now_ms):
        entry = self._entries.get(update.key)
        if entry is None:
            self._entries[update.key] = _BitStateEntry(update, now_ms)
            return

        entry.last_activity_ms = now_ms
        entry.update = update
        entry.source_event_type = update.source_event_type or entry.source_event_type

        if entry.pending_value is None:
            if entry.has_emitted_value and entry.last_emitted_value == update.value:
                return

            entry.pending_value = update.value
            entry.pending_started_ms = now_ms
            entry.last_changed_ms = now_ms
            entry.toggles_suppressed = 0
            entry.force_emit_pending = False
            return

        if entry.pending_value != update.value:
            entry.pending_value = update.value
            entry.last_changed_ms = now_ms
            entry.toggles_suppressed += 1
            entry.force_emit_pending = False

    def _requeue_update(self, update, now_ms):
        entry = self._entries.get(update.key)
        if entry is None:
            entry = _BitStateEntry(update, now_ms)
            self._entries[update.key] = entry

        entry.last_activity_ms = now_ms
        entry.source_event_type = update.source_event_type or entry.source_event_type
        entry.pending_value = update.value
        entry.pending_started_ms = now_ms
        entry.last_changed_ms = now_ms
        entry.toggles_suppressed = max(
            int(getattr(update, "toggles_suppressed", 0)),
            entry.toggles_suppressed,
        )
        entry.force_emit_pending = True

    def _emit_entry(self, entry):
        if (
            not entry.force_emit_pending
            and entry.has_emitted_value
            and entry.last_emitted_value == entry.pending_value
        ):
            entry.pending_value = None
            entry.pending_started_ms = None
            entry.last_changed_ms = None
            entry.toggles_suppressed = 0
            entry.force_emit_pending = False
            return None

        update = BitStateUpdate(
            device_uid_hex=entry.device_uid_hex,
            stat_group=entry.stat_group,
            bit=entry.bit,
            value=entry.pending_value,
            source_event_type=entry.source_event_type,
            toggles_suppressed=entry.toggles_suppressed,
            protocol_bit=entry.update.protocol_bit,
            status_name=entry.update.status_name,
            status_label=entry.update.status_label,
            supported=entry.update.supported,
            reserved=entry.update.reserved,
        )
        entry.last_emitted_value = entry.pending_value
        entry.has_emitted_value = True
        entry.pending_value = None
        entry.pending_started_ms = None
        entry.last_changed_ms = None
        entry.toggles_suppressed = 0
        entry.force_emit_pending = False
        return update

    def _is_ready_to_emit(self, entry, now_ms):
        quiet_elapsed_ms = self._diff_ms(now_ms, entry.last_changed_ms)
        hold_elapsed_ms = self._diff_ms(now_ms, entry.pending_started_ms)
        return (
            quiet_elapsed_ms >= self.config.quiet_period_ms
            or hold_elapsed_ms >= self.config.max_hold_ms
        )

    def _is_idle(self, entry, now_ms):
        if entry.pending_value is not None:
            return False

        if self.config.idle_ttl_ms == 0:
            return True

        return self._diff_ms(now_ms, entry.last_activity_ms) >= self.config.idle_ttl_ms

    def _resolve_now_ms(self, now_ms):
        if now_ms is not None:
            return int(now_ms)
        return int(self._now_ms())


def security_event_to_bit_state_updates(event, supported_only=False):
    """Convert both status bytes, optionally excluding documented reserved bits.

    Unknown product models intentionally keep all raw bits. Dropping data for a
    model that is missing from the capability table would hide useful evidence.
    """
    updates = []
    source_event_type = getattr(event, "event_type", None)
    device_model = getattr(event, "device_model", None)
    supported_bits = security_status_capabilities(device_model)

    for stat_group, flags in ((1, getattr(event, "stat1_flags", ())), (0, getattr(event, "stat0_flags", ()))):
        for protocol_bit, value in enumerate(flags):
            supported = None if supported_bits is None else (stat_group, protocol_bit) in supported_bits
            if supported_only and supported is False:
                continue
            definition = security_status_bit_definition(stat_group, protocol_bit, device_model)
            updates.append(
                BitStateUpdate(
                    device_uid_hex=event.device_uid_hex,
                    stat_group=stat_group,
                    bit=protocol_bit + 1,
                    value=value,
                    source_event_type=source_event_type,
                    protocol_bit=protocol_bit,
                    status_name=definition["name"] if definition else None,
                    status_label=definition["label"] if definition else None,
                    supported=supported,
                    reserved=definition is None,
                )
            )

    return updates


def security_event_to_supported_bit_state_updates(event):
    """Return only supported status bits for a known product model."""
    return security_event_to_bit_state_updates(event, supported_only=True)


def _normalize_updates(updates):
    if updates is None:
        return []

    if isinstance(updates, BitStateUpdate):
        return [updates]

    return list(updates)


def _default_now_ms():
    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return int(ticks_ms())
    return int(time.monotonic() * 1000)


def _default_diff_ms(later_ms, earlier_ms):
    ticks_diff = getattr(time, "ticks_diff", None)
    if ticks_diff is not None:
        return int(ticks_diff(later_ms, earlier_ms))
    return int(later_ms - earlier_ms)
