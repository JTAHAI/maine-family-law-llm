"""Child-only tripwire for accidental Python networking, NOT an OS sandbox.

Native code and malicious Python can bypass sys.addaudithook. The trusted,
hash-checked ranker uses anonymous pipes and needs no socket, including loopback.
No event arguments (hosts, URLs, credentials or record text) are retained.
"""

import sys

GUARD_VERSION = "python_audit_tripwire_v1"
_PROBE = "mfl.compact_network_guard.probe"
_NETWORK_EVENTS = frozenset(
    {
        "socket.__new__",
        "socket.bind",
        "socket.connect",
        "socket.getaddrinfo",
        "socket.gethostbyaddr",
        "socket.gethostbyname",
        "socket.getnameinfo",
        "socket.sendmsg",
        "socket.sendto",
        "urllib.Request",
        "http.client.connect",
        "http.client.send",
        "ftplib.connect",
        "ftplib.sendcmd",
        "smtplib.connect",
        "smtplib.send",
        "imaplib.open",
        "imaplib.send",
        "poplib.connect",
        "poplib.putline",
        "telnetlib.Telnet.open",
        "telnetlib.Telnet.write",
        "webbrowser.open",
    }
)


class PythonNetworkDenied(RuntimeError):
    def __init__(self):
        super().__init__("compact_python_network_denied")


class _ProbeObserved(Exception):
    pass


class PythonNetworkGuard:
    """Install only in a disposable child; hooks cannot be safely uninstalled."""

    def __init__(self):
        self.denied = False
        sys.addaudithook(self._audit)
        # Existing hooks may silently refuse addaudithook. Fail closed if this
        # exact hook did not observe the probe (not merely any existing hook).
        self._probe_seen = False
        try:
            sys.audit(_PROBE, self)
        except _ProbeObserved:
            if self._probe_seen:
                return
        raise RuntimeError("compact_network_guard_unavailable")

    def _audit(self, event, arguments):
        if event == _PROBE and arguments == (self,):
            self._probe_seen = True
            raise _ProbeObserved()
        if event in _NETWORK_EVENTS:
            self.denied = True
            raise PythonNetworkDenied()

    def check(self):
        # A dependency may catch the first exception and return a fallback.
        # Such output is still discarded; this child must never be reused.
        if self.denied:
            raise PythonNetworkDenied()
