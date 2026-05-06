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
