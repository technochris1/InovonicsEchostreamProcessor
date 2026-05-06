import sys


def detect_runtime():
    implementation = getattr(sys, "implementation", None)
    if implementation is None:
        return "unknown"
    return getattr(implementation, "name", "unknown")


def is_cpython():
    return detect_runtime() == "cpython"


def is_micropython():
    return detect_runtime() == "micropython"
