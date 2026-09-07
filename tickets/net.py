"""Force IPv4-only outbound connections.

Some hosts have IPv6 "available" at the socket/library level
(`socket.has_ipv6` is a compile-time flag, not a connectivity check)
but no actual working IPv6 route — DNS resolution for a dual-stack
host like api.telegram.org can then hand back an IPv6 address first,
and the connection attempt fails immediately with
`OSError: [Errno 101] Network is unreachable` (urllib3/requests) or a
slow timeout that looks like the remote end is just slow (aiohttp).
This showed up as both symptoms in production: the aiogram bot
crash-looping on a "Request timeout" reaching api.telegram.org, and a
plain `requests.post()` call failing outright with "Network is
unreachable" — almost certainly the same root cause.

Call force_ipv4_for_requests() once at process startup (see
tickets/apps.py) to fix it for every `requests`-based call in this
project (services.py's Telegram calls, freedompay.py, finik.py).
aiohttp (used by the Telegram bot) needs its own fix — see
telegram_bot.py, which forces the same thing on its TCPConnector.
"""

import socket


def force_ipv4_for_requests():
    import urllib3.util.connection as urllib3_connection

    def _allowed_gai_family_ipv4_only():
        return socket.AF_INET

    urllib3_connection.allowed_gai_family = _allowed_gai_family_ipv4_only
