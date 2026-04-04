import asyncio
import os
import sys


def _check_systemd():
    """Block launch unless we are running under the pullup-bot systemd user service."""
    # INVOCATION_ID is set by systemd for every service unit it starts
    if os.environ.get("INVOCATION_ID"):
        return  # running under systemd — OK

    print(
        "ERROR: The bot must be started via systemd:\n"
        "  systemctl --user start pullup-bot.service\n"
        "\n"
        "Do NOT launch it directly with `python -m pullup_bot` or `nohup …`.\n"
        "Running multiple instances causes TelegramConflictError.",
        file=sys.stderr,
    )
    sys.exit(1)


_check_systemd()

from .main import main  # noqa: E402

asyncio.run(main())
