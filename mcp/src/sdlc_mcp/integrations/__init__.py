"""External actions: open a PR, build an APK, deliver it to Telegram.

Each is a small ``Protocol`` (``base.py``) with two implementations: a **fake**
that records the call and succeeds (``fakes.py``, used in tests and whenever
credentials are absent) and a **real** one guarded behind config/secrets
(``git_ops.py`` / ``apk_build.py`` / ``telegram.py``). ``factory.build(cfg)``
picks real-or-fake per capability, so the core keeps working with no keys set —
see ``docs/SETUP.md`` to switch the real ones on.
"""
