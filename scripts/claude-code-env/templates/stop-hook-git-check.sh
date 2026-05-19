#!/bin/bash
# Neutralized by operator on 2026-05-18. The original content
# (re-staged at every session start by /opt/env-runner/environment-manager
# from a baked-in template) interpreted any uncommitted-or-unpushed git
# state as a Stop-block (exit 2), which broke long-running /goal
# sessions during development work — multi-hour goal sessions would
# turn into perpetual "There are uncommitted changes" loops.
#
# This file is re-staged from the read-only squashfs image on each
# new session, so this neutralized version only persists for the
# current session. The DURABLE fix is in ~/.claude/settings.json:
# we declare `"hooks": { "Stop": [], "SubagentStop": [] }` explicitly
# so even if some future merge logic combines template + user
# settings, the empty-array override wins and this script is never
# wired in.
#
# If you legitimately want a git-clean Stop check, configure it via
# ~/.claude/settings.json's hooks block with your own script, not
# this orphan.
exit 0
