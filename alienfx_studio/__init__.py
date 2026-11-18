"""Loopback-only Flask interface for AlienFX."""

import hmac
import json
import logging
import os
import secrets
import tempfile
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, session

from alienfx.core.themefile import AlienFXThemeFile
from alienfx_studio.diagnostics import (
    describe_controller,
    make_zone_test_profile,
    make_zone_restore_profile,
    probe_link,
    sanitize_restore_profile,
)
from alienfx_studio.presets import (
    ALLOWED_EFFECTS,
    PRESETS,
    PRESETS_BY_ID,
    build_theme,
    validate_brightness_levels,
    validate_theme_options,
)


_UNSET = object()
MAX_PALETTE_NAME = 60


def _palette_store_path():
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(config_home) / "alienfx-studio" / "palettes.json"


def _read_palette_store(path):
    try:
        with path.open(encoding="utf-8") as palette_file:
            palettes = json.load(palette_file)
    except FileNotFoundError:
        return []
    if not isinstance(palettes, list) or any(not isinstance(item, dict) for item in palettes):
        raise ValueError("The saved palette file has an invalid format.")
    return palettes


def _write_palette_store(path, palettes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".palettes-", suffix=".tmp", delete=False,
        ) as palette_file:
            temporary_path = Path(palette_file.name)
            json.dump(palettes, palette_file, indent=2)
            palette_file.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _saved_palette_record(payload):
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON palette object.")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > MAX_PALETTE_NAME:
        raise ValueError("Palette names must contain 1 to 60 characters.")
    palette = payload.get("palette")
    effect = payload.get("effect")
    speed = payload.get("speed")
    if effect not in ALLOWED_EFFECTS:
        raise ValueError("Unsupported effect.")
    normalized_palette, _colors = validate_theme_options(palette, effect, speed)
    brightness = validate_brightness_levels(payload.get("brightness"), len(normalized_palette))
    return {
        "name": name.strip(),
        "palette": normalized_palette,
        "brightness": brightness,
        "effect": effect,
        "speed": speed,
    }


def _discover_controller():
    """Use normal supported-device probing only; never run zonescan here."""
    try:
        from alienfx.core.prober import AlienFXProber

        return AlienFXProber.get_controller(), None
    except Exception as exc:  # Keep the dashboard usable when optional USB deps are absent.
        logging.exception("Unable to initialize AlienFX controller discovery")
        return None, str(exc)


def _controller_error_message(exc):
    if getattr(exc, "errno", None) == 13 or "access denied" in str(exc).lower():
        return (
            "USB access denied. Reload the AlienFX udev rules for this device, "
            "re-trigger it, then restart the studio. See README, USB permissions."
        )
    if getattr(exc, "errno", None) == 110 or "timed out" in str(exc).lower():
        return "The controller did not respond within 1 second. It may be busy; wait briefly and retry."
    return "Controller operation failed: {}".format(exc)


def create_app(controller=_UNSET, discovery_error=None):
    """Create the local web app; ``controller`` can be injected for tests."""
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        MAX_CONTENT_LENGTH=16 * 1024,
    )

    if controller is _UNSET:
        controller, discovery_error = _discover_controller()
    app.extensions["alienfx_controller"] = controller
    app.extensions["alienfx_discovery_error"] = discovery_error
    app.extensions["alienfx_apply_lock"] = threading.Lock()
    app.extensions["alienfx_palette_lock"] = threading.Lock()
    app.extensions["alienfx_palette_path"] = _palette_store_path()
    app.extensions["alienfx_zone_test"] = {
        "active": False,
        "timer": None,
        "restore_failed": False,
        "restore_pending": False,
        "restore_theme": None,
        "zone": None,
    }

    def valid_csrf():
        supplied_token = request.headers.get("X-CSRF-Token", "")
        expected_token = session.get("csrf_token", "")
        return bool(expected_token) and hmac.compare_digest(supplied_token, expected_token)

    def load_restore_profile(current):
        saved = AlienFXThemeFile(current)
        if not saved.load_last_theme():
            return None
        profile = sanitize_restore_profile(current, saved.theme)
        if profile is None:
            return None
        expected_zones = set(current.zone_map)
        for state_name in current.state_map:
            covered_zones = {
                zone
                for item in profile.get(state_name, [])
                for zone in item.get("zones", [])
            }
            if covered_zones != expected_zones:
                return None
        saved.theme = profile
        return saved

    def finish_zone_test():
        diagnostic = app.extensions["alienfx_zone_test"]
        with app.extensions["alienfx_apply_lock"]:
            diagnostic["active"] = False
            diagnostic["timer"] = None

    def restore_zone_test():
        current = app.extensions["alienfx_controller"]
        diagnostic = app.extensions["alienfx_zone_test"]
        if current is None:
            return False
        with app.extensions["alienfx_apply_lock"]:
            if not diagnostic["restore_pending"] and not diagnostic["restore_failed"]:
                return False
            if diagnostic["timer"] is not None:
                diagnostic["timer"].cancel()
            try:
                restore_theme = AlienFXThemeFile(current)
                restore_theme.theme = make_zone_restore_profile(
                    current,
                    diagnostic["restore_theme"].theme,
                    diagnostic["zone"],
                )
                current.set_theme(restore_theme, persist=False, reset=False)
                diagnostic["active"] = False
                diagnostic["timer"] = None
                diagnostic["restore_pending"] = False
                diagnostic["restore_theme"] = None
                diagnostic["zone"] = None
                diagnostic["restore_failed"] = False
                return True
            except Exception:
                logging.exception("Failed to restore lighting after zone test")
                diagnostic["active"] = False
                diagnostic["timer"] = None
                diagnostic["restore_pending"] = True
                diagnostic["restore_failed"] = True
                return False

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response

    @app.get("/")
    def index():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return render_template("index.html", csrf_token=session["csrf_token"])

    @app.post("/api/shutdown")
    def shutdown():
        if not valid_csrf():
            abort(403, description="Session token missing or invalid. Reload the page and retry.")
        stop_server = app.extensions.get("alienfx_shutdown")
        if stop_server is None:
            return jsonify({"ok": False, "error": "The server cannot be stopped from this session."}), 503
        timer = threading.Timer(0.35, stop_server)
        timer.daemon = True
        timer.start()
        return jsonify({"ok": True})

    @app.get("/api/status")
    def status():
        current = app.extensions["alienfx_controller"]
        if current is None:
            return jsonify({
                "connected": False,
                "name": None,
                "zones": [],
                "message": "No supported controller detected. No scan or hardware writes were attempted.",
                "detail": app.extensions["alienfx_discovery_error"],
            })
        return jsonify({
            "connected": True,
            "name": getattr(current, "name", "AlienFX controller"),
            "zones": list(current.zone_map),
            "message": "Controller ready",
        })

    @app.get("/api/themes")
    def themes():
        return jsonify(PRESETS)

    @app.get("/api/palettes")
    def saved_palettes():
        try:
            with app.extensions["alienfx_palette_lock"]:
                return jsonify(_read_palette_store(app.extensions["alienfx_palette_path"]))
        except (OSError, ValueError, json.JSONDecodeError):
            logging.exception("Unable to read saved AlienFX palettes")
            return jsonify({"error": "Saved palettes could not be read."}), 500

    @app.post("/api/palettes")
    def create_saved_palette():
        if not valid_csrf():
            abort(403, description="Session token missing or invalid. Reload the page and retry.")
        try:
            record = _saved_palette_record(request.get_json(silent=True))
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        try:
            with app.extensions["alienfx_palette_lock"]:
                palettes = _read_palette_store(app.extensions["alienfx_palette_path"])
                if any(item.get("name", "").casefold() == record["name"].casefold() for item in palettes):
                    return jsonify({"error": "A saved palette already has this name."}), 409
                record["id"] = secrets.token_urlsafe(12)
                palettes.append(record)
                _write_palette_store(app.extensions["alienfx_palette_path"], palettes)
        except (OSError, ValueError, json.JSONDecodeError):
            logging.exception("Unable to save AlienFX palette")
            return jsonify({"error": "Palette could not be saved."}), 500
        return jsonify({"ok": True, "palette": record, "palettes": palettes}), 201

    @app.put("/api/palettes/<palette_id>")
    def update_saved_palette(palette_id):
        if not valid_csrf():
            abort(403, description="Session token missing or invalid. Reload the page and retry.")
        try:
            record = _saved_palette_record(request.get_json(silent=True))
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        try:
            with app.extensions["alienfx_palette_lock"]:
                palettes = _read_palette_store(app.extensions["alienfx_palette_path"])
                index = next((i for i, item in enumerate(palettes) if item.get("id") == palette_id), None)
                if index is None:
                    return jsonify({"error": "Saved palette not found."}), 404
                if any(
                    item.get("id") != palette_id
                    and item.get("name", "").casefold() == record["name"].casefold()
                    for item in palettes
                ):
                    return jsonify({"error": "A saved palette already has this name."}), 409
                record["id"] = palette_id
                palettes[index] = record
                _write_palette_store(app.extensions["alienfx_palette_path"], palettes)
        except (OSError, ValueError, json.JSONDecodeError):
            logging.exception("Unable to update AlienFX palette")
            return jsonify({"error": "Palette could not be updated."}), 500
        return jsonify({"ok": True, "palette": record, "palettes": palettes})

    @app.delete("/api/palettes/<palette_id>")
    def delete_saved_palette(palette_id):
        if not valid_csrf():
            abort(403, description="Session token missing or invalid. Reload the page and retry.")
        try:
            with app.extensions["alienfx_palette_lock"]:
                palettes = _read_palette_store(app.extensions["alienfx_palette_path"])
                remaining = [item for item in palettes if item.get("id") != palette_id]
                if len(remaining) == len(palettes):
                    return jsonify({"error": "Saved palette not found."}), 404
                _write_palette_store(app.extensions["alienfx_palette_path"], remaining)
        except (OSError, ValueError, json.JSONDecodeError):
            logging.exception("Unable to delete AlienFX palette")
            return jsonify({"error": "Palette could not be deleted."}), 500
        return jsonify({"ok": True, "palettes": remaining})

    @app.get("/api/diagnostics")
    def diagnostics():
        current = app.extensions["alienfx_controller"]
        if current is None:
            return jsonify({
                "connected": False,
                "profile_available": False,
                "zones": [],
                "message": "Connect a supported controller before running diagnostics.",
            })
        diagnostic = app.extensions["alienfx_zone_test"]
        with app.extensions["alienfx_apply_lock"]:
            restore_available = load_restore_profile(current) is not None
            return jsonify({
                "connected": True,
                "controller": describe_controller(current),
                "profile_available": restore_available,
                "test_active": diagnostic["active"],
                "restore_pending": diagnostic["restore_pending"],
                "restore_failed": diagnostic["restore_failed"],
                "test_zone": diagnostic["zone"],
                "restore_after_seconds": app.config.get("ZONE_TEST_SECONDS", 8),
                "message": (
                    "Ready" if restore_available else
                    "Apply a complete theme from this studio first so a zone test can restore it exactly."
                ),
            })

    @app.post("/api/diagnostics/probe")
    def diagnostics_probe():
        if not valid_csrf():
            abort(403, description="Session token missing or invalid. Reload the page and retry.")
        current = app.extensions["alienfx_controller"]
        if current is None:
            return jsonify({"ok": False, "error": "No supported controller is connected."}), 503
        try:
            with app.extensions["alienfx_apply_lock"]:
                if (app.extensions["alienfx_zone_test"]["active"]
                    or app.extensions["alienfx_zone_test"]["restore_pending"]
                    or app.extensions["alienfx_zone_test"]["restore_failed"]):
                    return jsonify({"ok": False, "error": "Restore the selected zone before probing the controller."}), 409
                return jsonify(probe_link(current))
        except Exception as exc:
            logging.exception("AlienFX read-only status probe failed")
            return jsonify({"ok": False, "error": _controller_error_message(exc)}), 500

    @app.post("/api/diagnostics/zone-test")
    def diagnostics_zone_test():
        if not valid_csrf():
            abort(403, description="Session token missing or invalid. Reload the page and retry.")
        current = app.extensions["alienfx_controller"]
        if current is None:
            return jsonify({"ok": False, "error": "No supported controller is connected."}), 503
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Expected a JSON request."}), 400
        zone_name = payload.get("zone")
        color = payload.get("color", "#ffffff")
        try:
            test_theme = AlienFXThemeFile(current)
            test_theme.theme = make_zone_test_profile(current, zone_name, color)
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

        diagnostic = app.extensions["alienfx_zone_test"]
        timer = None
        with app.extensions["alienfx_apply_lock"]:
            if diagnostic["active"] or diagnostic["restore_pending"] or diagnostic["restore_failed"]:
                return jsonify({"ok": False, "error": "Restore the previously tested zone before starting another test."}), 409
            restore_theme = load_restore_profile(current)
            if restore_theme is None:
                return jsonify({
                    "ok": False,
                    "error": "No complete saved theme is available. Apply a theme in this studio first; no test was run.",
                }), 409
            try:
                current.set_theme(test_theme, persist=False, reset=False)
            except Exception as exc:
                logging.exception("Temporary AlienFX zone test failed")
                diagnostic["active"] = False
                diagnostic["restore_failed"] = True
                diagnostic["restore_pending"] = True
                diagnostic["restore_theme"] = restore_theme
                diagnostic["zone"] = zone_name
                return jsonify({
                    "ok": False,
                    "error": "{}. No retry or restore was sent. Use Restore selected zone if needed.".format(
                        _controller_error_message(exc)),
                }), 500

            diagnostic["active"] = True
            diagnostic["restore_failed"] = False
            diagnostic["restore_pending"] = True
            diagnostic["zone"] = zone_name
            diagnostic["restore_theme"] = restore_theme
            seconds = app.config.get("ZONE_TEST_SECONDS", 8)
            timer = threading.Timer(seconds, finish_zone_test)
            timer.daemon = True
            diagnostic["timer"] = timer
            timer.start()

        return jsonify({
            "ok": True,
            "zone": zone_name,
            "restore_after_seconds": seconds,
            "message": "Only the selected zone was changed. Restore it manually when finished; no SAVE or reset was sent.",
        })

    @app.post("/api/diagnostics/restore")
    def diagnostics_restore():
        if not valid_csrf():
            abort(403, description="Session token missing or invalid. Reload the page and retry.")
        diagnostic = app.extensions["alienfx_zone_test"]
        current = app.extensions["alienfx_controller"]
        if current is None:
            return jsonify({"ok": False, "error": "No supported controller is connected."}), 503
        if diagnostic["restore_pending"] or diagnostic["restore_failed"]:
            if restore_zone_test():
                return jsonify({"ok": True, "message": "Selected zone restored without saving or changing other zones."})
            return jsonify({"ok": False, "error": "Selected-zone restore failed. Retry only when you choose."}), 500

        with app.extensions["alienfx_apply_lock"]:
            restore_theme = load_restore_profile(current)
            if restore_theme is None:
                return jsonify({"ok": False, "error": "No complete saved theme is available."}), 409
            try:
                current.set_theme(restore_theme, persist=True, reset=False)
            except Exception as exc:
                logging.exception("Failed to reapply the saved AlienFX profile")
                return jsonify({"ok": False, "error": _controller_error_message(exc)}), 500
        return jsonify({"ok": True, "message": "Saved lighting profile reapplied."})

    @app.post("/api/apply")
    def apply_theme():
        supplied_token = request.headers.get("X-CSRF-Token", "")
        expected_token = session.get("csrf_token", "")
        if not expected_token or not hmac.compare_digest(supplied_token, expected_token):
            abort(403, description="Session token missing or invalid. Reload the page and retry.")

        current = app.extensions["alienfx_controller"]
        if current is None:
            return jsonify({"ok": False, "error": "No supported controller is connected."}), 503

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Expected a JSON request."}), 400

        preset_id = payload.get("preset_id")
        if preset_id == "custom":
            palette = payload.get("palette")
            brightness = payload.get("brightness")
            effect = payload.get("effect")
            theme_name = "Custom spectrum"
            default_speed = getattr(current, "DEFAULT_SPEED", 75)
        else:
            preset = PRESETS_BY_ID.get(preset_id)
            if preset is None:
                return jsonify({"ok": False, "error": "Unknown preset."}), 400
            palette = preset["palette"]
            brightness = None
            effect = preset["effect"]
            theme_name = preset["name"]
            default_speed = preset["speed"]

        speed = payload.get("speed", default_speed)
        try:
            theme_data = build_theme(current, palette, effect, speed, brightness)
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

        theme_file = AlienFXThemeFile(current)
        theme_file.theme = theme_data
        try:
            with app.extensions["alienfx_apply_lock"]:
                diagnostic = app.extensions["alienfx_zone_test"]
                if diagnostic["active"]:
                    return jsonify({"ok": False, "error": "Restore the selected test zone before applying a theme."}), 409
                current.set_theme(theme_file)
                theme_file.applied()
                if diagnostic["timer"] is not None:
                    diagnostic["timer"].cancel()
                diagnostic.update({
                    "active": False,
                    "timer": None,
                    "restore_failed": False,
                    "restore_pending": False,
                    "restore_theme": None,
                    "zone": None,
                })
        except Exception as exc:
            logging.exception("Unable to apply AlienFX theme")
            return jsonify({"ok": False, "error": _controller_error_message(exc)}), 500

        return jsonify({"ok": True, "name": theme_name, "effect": effect})

    return app


def main():
    """Start the private desktop web UI."""
    import argparse
    import signal
    import webbrowser

    parser = argparse.ArgumentParser(description="Local AlienFX lighting studio")
    parser.add_argument("--port", type=int, default=8765, help="local web port (default: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser automatically")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    url = "http://127.0.0.1:{}".format(args.port)
    print("AlienFX Studio: {} (local machine only)".format(url))
    if not args.no_browser:
        browser_timer = threading.Timer(0.75, webbrowser.open, args=(url,))
        browser_timer.daemon = True
        browser_timer.start()
    from waitress import serve

    app = create_app()
    app.extensions["alienfx_shutdown"] = lambda: os.kill(os.getpid(), signal.SIGINT)

    serve(
        app,
        host="127.0.0.1",
        port=args.port,
        threads=4,
    )
