from __future__ import annotations

SECURITY_DEVICE_MODELS = {
    0: "EN1210",
    1: "EN1212",
    2: "EN1210_60",
    3: "EN1210W",
    4: "EN1210SK",
    5: "EN1210EOL",
    6: "EN1210_240",
    7: "EN1252",
    8: "EE1215",
    9: "EN1216",
    10: "EN1212_60",
    11: "EE1215W",
    12: "EN1941",
    13: "EN1215EOL",
    14: "EN1215WEOL",
    15: "EN1941_60",
    16: "EN1235S",
    17: "EN1235D",
    18: "EN1235SF",
    19: "EN1235DF",
    20: "EN1233S",
    21: "EN1233D",
    22: "EN1224",
    23: "EN1224_ON",
    24: "EN1223S",
    25: "EN1223D",
    26: "EN1223S_60",
    29: "EN1221S_60NW",
    30: "EN1223SK",
    32: "EN1210W_60",
    33: "EN1244",
    35: "EN1751",
    37: "EN1752",
    40: "EN1260",
    41: "EN1262",
    42: "EN1265",
    43: "EN1261",
    44: "EN1243",
    45: "EN1241_60",
    46: "EN1245_60",
    48: "EN1249",
    50: "EN1247",
    57: "EN1236D",
    58: "EN1238D",
}

REPEATER_MODELS = {
    0: "EN5040_B",
    1: "EN5040_D",
}

DEVICE_CATEGORIES = {
    178: "SECURITY",
    192: "ENVIRONMENTAL",
    160: "SUBMETERING",
    1: "REPEATERS",
    0: "COORDINATORS",
}


# These names and wire-bit positions come from the EchoStream security status
# definitions. The protocol counts bits from 0 through 7; the capability table
# below decides which non-reserved bits each documented product supports.
SECURITY_STATUS_BIT_DEFINITIONS = (
    (1, 7, "eol_tamper", "EOL tamper"),
    (1, 6, "clean_me", "Clean Me"),
    (1, 3, "alarm_bit_3", "Alarm bit 3"),
    (1, 2, "alarm_bit_2", "Alarm bit 2"),
    (1, 1, "alarm_bit_1", "Alarm bit 1"),
    (1, 0, "primary_alarm", "Primary alarm"),
    (0, 6, "low_battery", "Low battery"),
    (0, 5, "case_wall_tamper", "Case/wall tamper"),
    (0, 4, "supervision", "Supervision"),
    (0, 3, "reset", "Reset"),
)


def _security_status_bits(alarm_bits=(0,), tamper=True, clean_me=False, eol_tamper=False):
    """Build the supported wire-bit set for one documented product shape."""
    bits = [(1, bit) for bit in alarm_bits]
    if clean_me:
        bits.append((1, 6))
    if eol_tamper:
        bits.append((1, 7))
    bits.extend(((0, 6), (0, 4), (0, 3)))
    if tamper:
        bits.append((0, 5))
    return tuple(sorted(bits))


# The table on guide page 24 is represented by capability groups instead of
# filtering by a product-name prefix. That prevents a similar-looking model
# from inheriting alarm bits that its transmitter does not send.
SECURITY_STATUS_MODEL_CAPABILITIES = {}


def _register_security_status_models(models, alarm_bits=(0,), tamper=True, clean_me=False, eol_tamper=False):
    supported = _security_status_bits(
        alarm_bits=alarm_bits,
        tamper=tamper,
        clean_me=clean_me,
        eol_tamper=eol_tamper,
    )
    for model in models:
        SECURITY_STATUS_MODEL_CAPABILITIES[model] = supported


_register_security_status_models(
    (
        "EN1210",
        "EN1210SK",
        "EN1215EOL",
        "EE1215",
        "EN1235DF",
        "EN1235SF",
        "EN1247",
        "EN1249",
        "EN1260",
        "EN1261",
        "EN1261HT",
        "EN1262",
        "EN1265",
    )
)
_register_security_status_models(("EN1210EOL",), eol_tamper=True)
_register_security_status_models(
    ("EN1210W", "EN1210W_60", "EN1212", "EE1215W", "EN1215WEOL", "EN1216", "EN1252"),
    alarm_bits=(0, 1),
)
_register_security_status_models(("EN1215WEOL",), alarm_bits=(0, 1), eol_tamper=True)
_register_security_status_models(
    ("EN1223D", "EN1223S", "EN1223SK", "EN1233D", "EN1233S", "EN1235D", "EN1235S"),
    tamper=False,
)
_register_security_status_models(("EN1224", "EN1224_ON"), alarm_bits=(0, 1, 2, 3), tamper=False)
_register_security_status_models(("EN1236D",), alarm_bits=(0, 1, 2), tamper=False)
_register_security_status_models(("EN1238D",), alarm_bits=(0, 1), tamper=False)
_register_security_status_models(("EN1242", "EN1243", "EN1244"), tamper=False, clean_me=True)

_register_security_status_models(("EN1245", "EN1245_60"), tamper=False)
_register_security_status_models(("EN1941", "EN1941_60", "EN1941_7"), alarm_bits=(0, 1))

_MODEL_STATUS_LABEL_OVERRIDES = {
    "EN1210W": {
        (1, 0): "Wired contact input",
        (1, 1): "Door/window reed switch",
    },
    "EN1215WEOL": {
        (1, 0): "Wired contact input",
        (1, 1): "Door/window reed switch",
    },
    "EN1223D": {(1, 0): "Pendant buttons"},
    "EN1223S": {(1, 0): "Pendant button"},
    "EN1224": {
        (1, 0): "Button 1",
        (1, 1): "Button 2",
        (1, 2): "Button 3",
        (1, 3): "Button 4",
    },
    "EN1224_ON": {
        (1, 0): "Button 1",
        (1, 1): "Button 2",
        (1, 2): "Button 3",
        (1, 3): "Button 4",
    },
    "EN1233D": {(1, 0): "Necklace pendant buttons"},
    "EN1233S": {(1, 0): "Necklace pendant button"},
    "EN1235D": {(1, 0): "Belt-clip pendant buttons"},
    "EN1235DF": {(1, 0): "Hold-up buttons"},
    "EN1235S": {(1, 0): "Belt-clip pendant button"},
    "EN1235SF": {(1, 0): "Hold-up button"},
    "EN1236D": {
        (1, 0): "Condition 1",
        (1, 1): "Condition 2",
        (1, 2): "Condition 3",
    },
    "EN1238D": {
        (1, 0): "Condition 1",
        (1, 1): "Condition 2",
    },
    "EN1242": {(1, 0): "Smoke alarm"},
    "EN1243": {(1, 0): "Smoke/heat alarm"},
    "EN1244": {(1, 0): "Smoke alarm"},
    "EN1245": {(1, 0): "CO alarm"},
    "EN1245_60": {(1, 0): "CO alarm"},
    "EN1247": {(1, 0): "Glassbreak alarm"},
    "EN1249": {(1, 0): "Billtrap alarm"},
    "EN1260": {(1, 0): "Motion alarm"},
    "EN1261": {(1, 0): "Motion alarm"},
    "EN1261HT": {(1, 0): "Motion alarm"},
    "EN1262": {(1, 0): "Motion alarm"},
    "EN1265": {(1, 0): "Motion alarm"},
}


# This selectable variant shares the EN1210W point layout and labels.
_MODEL_STATUS_LABEL_OVERRIDES["EN1210W_60"] = dict(_MODEL_STATUS_LABEL_OVERRIDES["EN1210W"])


_MODEL_ALIASES = {
    "EN1224-ON": "EN1224_ON",
    "E*1210SK": "EN1210SK",
    "E*1216": "EN1216",
    "E*1223D": "EN1223D",
    "E*1223S": "EN1223S",
    "E*1223SK": "EN1223SK",
    "E*1233D": "EN1233D",
    "E*1233S": "EN1233S",
    "E*1235D": "EN1235D",
    "E*1235S": "EN1235S",
    "E*1236D": "EN1236D",
    "E*1242": "EN1242",
    "E*1243": "EN1243",
    "E*1247": "EN1247",
    "E*1265": "EN1265",
}



def _normalize_model(device_model):
    model = str(device_model).strip().upper()
    return _MODEL_ALIASES.get(model, model)


def security_status_capabilities(device_model):
    """Return supported ``(STAT group, wire bit)`` pairs or ``None`` if unknown."""
    if device_model is None:
        return None
    return SECURITY_STATUS_MODEL_CAPABILITIES.get(_normalize_model(device_model))


def security_status_bit_definition(stat_group, protocol_bit, device_model=None):
    """Return the stable name and label for a defined bit, if one exists."""
    for group, bit, name, label in SECURITY_STATUS_BIT_DEFINITIONS:
        if group == stat_group and bit == protocol_bit:
            labels = _MODEL_STATUS_LABEL_OVERRIDES.get(_normalize_model(device_model), {})
            return {"stat_group": group, "protocol_bit": bit, "name": name, "label": labels.get((group, bit), label)}
    return None


# Maps the transmitted three-bit pattern to the ICN 3000 Rev. 2.0 Table 2 number.
ICN3000_ALARM_NUMBERS = (None, 1, 2, 4, 3, 5, 6, 7)


def decode_icn3000_7(stat1_flags, stat0_flags):
    """Return an alarm number, 0 for reset, or None for a zero-input report."""
    if stat0_flags[3]:
        return 0
    pattern = int(stat1_flags[0]) | (int(stat1_flags[1]) << 1) | (int(stat0_flags[5]) << 2)
    return ICN3000_ALARM_NUMBERS[pattern]


def device_category_label(mid: int) -> str:
    return DEVICE_CATEGORIES.get(mid, "UNKNOWN")


def device_model_label(mid: int, pti: int) -> str:
    if mid == 178:
        return SECURITY_DEVICE_MODELS.get(pti, "UNKNOWN")
    if mid == 1:
        return REPEATER_MODELS.get(pti, "UNKNOWN")
    if mid == 0:
        return "EN6040"
    return "UNKNOWN"
