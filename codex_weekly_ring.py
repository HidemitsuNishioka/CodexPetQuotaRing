#!/usr/bin/env python3
"""Transparent, click-through 7-day usage ring for the Codex desktop pet."""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402


CODEX_DIR = Path.home() / ".codex"
GLOBAL_STATE_PATH = CODEX_DIR / ".codex-global-state.json"
AUTH_PATH = CODEX_DIR / "auth.json"
LOGS_PATH = CODEX_DIR / "logs_2.sqlite"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
APP_STATE_DIR = STATE_DIR / "codex-weekly-ring"
PID_PATH = APP_STATE_DIR / "app.pid"
LOG_PATH = APP_STATE_DIR / "app.log"

USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
WEEK_SECONDS = 7 * 24 * 60 * 60
WEEK_TOLERANCE_SECONDS = 24 * 60 * 60

# The saved avatar coordinates identify the pet artwork's top-left corner.
# These offsets center the ring around the current Codex avatar window.
PET_CENTER_OFFSET_X = 112
PET_CENTER_OFFSET_Y = 122
WINDOW_SIZE = 280
RING_RADIUS = 120
RING_WIDTH = 8
STATE_POLL_MS = 350
USAGE_POLL_SECONDS = 60


@dataclass
class Usage:
    used_percent: float
    fetched_at: float
    source: str

    @property
    def remaining_percent(self) -> float:
        return min(100.0, max(0.0, 100.0 - self.used_percent))


def _valid_percent(value: Any) -> float | None:
    if isinstance(value, (int, float)) and 0 <= float(value) <= 100:
        return float(value)
    return None


def _bucket_duration_seconds(bucket: dict[str, Any]) -> float | None:
    seconds = bucket.get("limit_window_seconds")
    minutes = bucket.get("window_minutes")
    if isinstance(seconds, (int, float)) and seconds > 0:
        return float(seconds)
    if isinstance(minutes, (int, float)) and minutes > 0:
        return float(minutes) * 60
    return None


def _collect_rate_buckets(rate: Any) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(rate, dict):
        return []
    buckets: list[tuple[str, dict[str, Any]]] = []
    for key in ("primary_window", "primary", "secondary_window", "secondary"):
        value = rate.get(key)
        if isinstance(value, dict) and _valid_percent(value.get("used_percent")) is not None:
            buckets.append((key, value))
    return buckets


def _weekly_bucket(payload: dict[str, Any], *, cached: bool = False) -> dict[str, Any] | None:
    rate_key = "rate_limits" if cached else "rate_limit"
    buckets = _collect_rate_buckets(payload.get(rate_key))
    for _key, bucket in buckets:
        duration = _bucket_duration_seconds(bucket)
        if duration is not None and abs(duration - WEEK_SECONDS) <= WEEK_TOLERANCE_SECONDS:
            return bucket

    # Older cached events and API responses sometimes omit the duration while
    # retaining the conventional secondary-window weekly bucket.
    for key, bucket in buckets:
        if key in ("secondary_window", "secondary") and _bucket_duration_seconds(bucket) is None:
            return bucket
    return None


def _read_access_token() -> str | None:
    try:
        data = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    tokens = data.get("tokens") if isinstance(data, dict) else None
    token = tokens.get("access_token") if isinstance(tokens, dict) else None
    return token if isinstance(token, str) and token else None


def _fetch_live_usage() -> Usage | None:
    token = _read_access_token()
    if token is None:
        return None
    request = urllib.request.Request(
        USAGE_URL,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            if not 200 <= response.status < 300:
                return None
            payload = json.loads(response.read())
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    bucket = _weekly_bucket(payload)
    used = _valid_percent(bucket.get("used_percent")) if bucket else None
    return Usage(used, time.time(), "live") if used is not None else None


def _extract_rate_limit_event(body: str) -> dict[str, Any] | None:
    match = re.search(r'\{"type"\s*:\s*"codex\.rate_limits"', body)
    if match is None:
        return None
    try:
        event, _end = json.JSONDecoder().raw_decode(body[match.start():])
    except json.JSONDecodeError:
        return None
    return event if isinstance(event, dict) else None


def _fetch_cached_usage() -> Usage | None:
    if not LOGS_PATH.exists():
        return None
    try:
        uri = f"file:{LOGS_PATH.as_posix()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=0.5)) as connection:
            row = connection.execute(
                "SELECT feedback_log_body FROM logs "
                "WHERE feedback_log_body LIKE '%\"type\":\"codex.rate_limits\"%' "
                "ORDER BY ts DESC, ts_nanos DESC, id DESC LIMIT 1"
            ).fetchone()
    except sqlite3.Error:
        return None
    if not row or not isinstance(row[0], str):
        return None
    event = _extract_rate_limit_event(row[0])
    bucket = _weekly_bucket(event, cached=True) if event else None
    used = _valid_percent(bucket.get("used_percent")) if bucket else None
    return Usage(used, time.time(), "cached") if used is not None else None


def _read_pet_position() -> tuple[int, int] | None:
    try:
        state = json.loads(GLOBAL_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(state, dict) or not state.get("electron-avatar-overlay-open", False):
        return None
    bounds = state.get("electron-avatar-overlay-bounds")
    if not isinstance(bounds, dict):
        return None
    x, y = bounds.get("x"), bounds.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    center_x = round(x + PET_CENTER_OFFSET_X)
    center_y = round(y + PET_CENTER_OFFSET_Y)
    return center_x - WINDOW_SIZE // 2, center_y - WINDOW_SIZE // 2


def _weekly_color(remaining: float) -> tuple[float, float, float]:
    if remaining <= 12:
        return (1.0, 0.25, 0.30)
    if remaining <= 30:
        return (1.0, 0.68, 0.25)
    return (0.36, 0.82, 0.96)


class WeeklyRingWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.usage: Usage | None = None
        self.current_position: tuple[int, int] | None = None
        self._fetch_lock = threading.Lock()
        self.input_ready = False
        self.input_failed = False
        self._x_display = None
        self._pet_window_id: int | None = None

        self.set_title("Codex 7-day limit ring")
        self.set_default_size(WINDOW_SIZE, WINDOW_SIZE)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_app_paintable(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_accept_focus(False)
        self.set_focus_on_map(False)
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)

        self.connect("draw", self._draw)
        self.connect("realize", self._make_clickthrough)
        self.connect("map-event", self._make_clickthrough)

        try:
            from Xlib import display as xdisplay

            self._x_display = xdisplay.Display()
        except Exception:
            logging.exception("Could not connect to X11 for pet window grouping")

        self.realize()
        GLib.timeout_add(STATE_POLL_MS, self._poll_pet_state)
        GLib.timeout_add_seconds(USAGE_POLL_SECONDS, self._refresh_usage)
        self._refresh_usage()

    def _make_clickthrough(self, _widget: Gtk.Widget, _event: Gdk.Event | None = None) -> bool:
        window = self.get_window()
        if window is None:
            self.hide()
            return False
        try:
            window.set_pass_through(True)
            window.input_shape_combine_region(cairo.Region(), 0, 0)

            # Set the X11 input shape explicitly as well. This is the reliable
            # path for transparent windows on Linux and leaves the pet fully
            # draggable beneath the overlay.
            from Xlib import X
            from Xlib.ext import shape

            if self._x_display is None:
                raise RuntimeError("X11 display connection is unavailable")
            target = self._x_display.create_resource_object("window", window.get_xid())
            target.shape_rectangles(shape.SO.Set, shape.SK.Input, X.Unsorted, 0, 0, [])
            self._x_display.sync()
            rectangles = target.shape_get_rectangles(shape.SK.Input).rectangles
            if rectangles:
                raise RuntimeError("X11 did not accept the empty input shape")
            self.input_ready = True
        except Exception:
            self.input_failed = True
            logging.exception("Could not confirm click-through input; hiding the ring for safety")
            self.hide()
        return False

    def _poll_pet_state(self) -> bool:
        if self.input_failed:
            return True
        position = _read_pet_position()
        pet_window = self._find_pet_window() if position is not None else None
        if position is None or pet_window is None:
            if self.get_visible():
                self.hide()
            self.current_position = None
            return True

        if self._pet_window_id != pet_window.id:
            try:
                ring_window = self._x_display.create_resource_object("window", self.get_window().get_xid())
                ring_window.set_wm_transient_for(pet_window)
                self._x_display.sync()
                self._pet_window_id = pet_window.id
            except Exception:
                logging.exception("Could not associate the ring with the Codex pet window")
                self.hide()
                return True

        if not self.get_visible():
            self.show_all()
        actual_x, actual_y = self.get_position()
        if position != self.current_position or (abs(actual_x - position[0]) > 3 or abs(actual_y - position[1]) > 3):
            # Move after mapping: some window managers place a new utility
            # window at the active app's position on its first map.
            self.move(*position)
            self.current_position = position
        return True

    def _find_pet_window(self) -> Any | None:
        """Find the mapped, compact Codex desktop window used by the pet."""
        if self._x_display is None:
            return None
        try:
            from Xlib import X

            root = self._x_display.screen().root
            for candidate in reversed(root.query_tree().children):
                if candidate.id == self.get_window().get_xid():
                    continue
                attrs = candidate.get_attributes()
                if attrs.map_state != X.IsViewable:
                    continue
                if candidate.get_wm_class() != ("codex-desktop", "codex-desktop"):
                    continue
                geometry = candidate.get_geometry()
                if 200 <= geometry.width <= 700 and 200 <= geometry.height <= 700:
                    return candidate
        except Exception:
            logging.exception("Could not locate the Codex pet window")
        return None

    def _refresh_usage(self) -> bool:
        if not self._fetch_lock.acquire(blocking=False):
            return True

        def worker() -> None:
            try:
                usage = _fetch_live_usage()
                if usage is None:
                    usage = _fetch_cached_usage()
                GLib.idle_add(self._set_usage, usage)
            except Exception:
                logging.exception("Unexpected usage refresh error")
            finally:
                self._fetch_lock.release()

        threading.Thread(target=worker, name="weekly-usage-fetch", daemon=True).start()
        return True

    def _set_usage(self, usage: Usage | None) -> bool:
        self.usage = usage
        self.queue_draw()
        return False

    def _draw(self, _widget: Gtk.Widget, context: cairo.Context) -> bool:
        context.save()
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.set_source_rgba(0, 0, 0, 0)
        context.paint()
        context.set_operator(cairo.OPERATOR_OVER)

        center = WINDOW_SIZE / 2
        context.set_line_width(RING_WIDTH)
        context.set_line_cap(cairo.LINE_CAP_ROUND)

        # A faint full circle makes the remaining portion legible on any theme.
        context.set_source_rgba(0.92, 0.96, 1.0, 0.38)
        context.arc(center, center, RING_RADIUS, 0, 2 * 3.141592653589793)
        context.stroke()

        if self.usage is not None:
            remaining = self.usage.remaining_percent
            if remaining > 0:
                start = -3.141592653589793 / 2
                end = start + (remaining / 100) * 2 * 3.141592653589793
                red, green, blue = _weekly_color(remaining)
                context.set_source_rgba(red, green, blue, 0.98)
                context.arc(center, center, RING_RADIUS, start, end)
                context.stroke()

        context.restore()
        return False


def main() -> int:
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=100_000, backupCount=1)],
    )
    try:
        PID_PATH.write_text(str(os.getpid()), encoding="ascii")
    except OSError:
        pass

    app = WeeklyRingWindow()

    def cleanup(*_args: Any) -> None:
        try:
            PID_PATH.unlink(missing_ok=True)
        except OSError:
            pass
        if app._x_display is not None:
            app._x_display.close()
        Gtk.main_quit()

    app.connect("destroy", cleanup)
    try:
        Gtk.main()
    finally:
        try:
            PID_PATH.unlink(missing_ok=True)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
