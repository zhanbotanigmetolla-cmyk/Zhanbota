import logging

from pullup_bot import config


def _record(name, level, msg, args=()):
    return logging.LogRecord(name, level, __file__, 1, msg, args, None)


def test_failed_polls_are_demoted_to_warnings():
    flt = config._PollingNoiseFilter()
    poll = _record("aiogram.dispatcher", logging.ERROR, "Failed to fetch updates - %s: %s",
                   ("TelegramServerError", "Telegram server says - Bad Gateway"))
    assert flt.filter(poll) is True
    assert poll.levelno == logging.WARNING and poll.levelname == "WARNING"

    real = _record("aiogram.dispatcher", logging.ERROR, "Cause exception while process update")
    assert flt.filter(real) is True
    assert real.levelno == logging.ERROR


def test_per_minute_jobs_are_hidden_but_daily_jobs_and_failures_stay():
    flt = config._FrequentJobFilter()
    tick = _record("apscheduler.executors.default", logging.INFO, 'Running job "%s" (scheduled at %s)',
                   ("daily_reminder (trigger: cron[minute='*'])", "2026-11-08 14:21:00+05:00"))
    watchdog = _record("apscheduler.executors.default", logging.INFO, 'Job "%s" executed successfully',
                       ("watchdog_health_check (trigger: interval[0:05:00])",))
    daily = _record("apscheduler.executors.default", logging.INFO, 'Job "%s" executed successfully',
                    ("daily_report (trigger: cron[hour='22'])",))
    failure = _record("apscheduler.executors.default", logging.ERROR, 'Job "%s" raised an exception',
                      ("daily_reminder (trigger: cron[minute='*'])",))
    assert flt.filter(tick) is False
    assert flt.filter(watchdog) is False
    assert flt.filter(daily) is True
    assert flt.filter(failure) is True


def test_filters_are_attached_to_the_noisy_loggers():
    assert any(isinstance(f, config._PollingNoiseFilter)
               for f in logging.getLogger("aiogram.dispatcher").filters)
    assert any(isinstance(f, config._FrequentJobFilter)
               for f in logging.getLogger("apscheduler.executors.default").filters)
