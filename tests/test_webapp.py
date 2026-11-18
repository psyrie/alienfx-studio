import os
import tempfile
import time
import unittest
from collections import Counter
from unittest.mock import Mock, patch

from alienfx.core.controller_13r3 import AlienFXController13R3
from alienfx.core.themefile import AlienFXThemeFile
from alienfx.core.usbdriver import AlienFXUSBDriver
from alienfx_studio import create_app
from alienfx_studio.diagnostics import (
    make_zone_restore_profile,
    make_zone_test_profile,
    probe_link,
    sanitize_restore_profile,
)
from alienfx_studio.presets import PRESETS, build_theme


class FakeController:
    DEFAULT_SPEED = 75
    name = "Test AlienFX 13 R3"
    zone_map = {
        "Left Keyboard": 0x0008,
        "Middle-left Keyboard": 0x0004,
        "Middle-right Keyboard": 0x0002,
        "Right Keyboard": 0x0001,
        "Alien Head": 0x0020,
        "Logo": 0x0040,
        "Touchpad": 0x0080,
        "Power Button": 0x0100,
    }
    power_zones = ["Power Button"]
    state_map = {"Boot": 1, "Battery On": 8}

    class Packet:
        STATUS_READY = 0x10
        STATUS_BUSY = 0x11
        controllerrevision = 2
        PACKET_LENGTH = 12

        @staticmethod
        def make_cmd_get_status():
            return [2, 6, 0, 0, 0, 0, 0, 0, 0]

    class Driver:
        def __init__(self):
            self.writes = []
            self.response = [0x10, 0, 0]
            self.released = False

        def acquire(self):
            return None

        def write_packet(self, packet):
            self.writes.append(packet)

        def read_packet(self):
            return self.response

        def release(self):
            self.released = True

    def __init__(self):
        self.applied_theme = None
        self.apply_calls = []
        self.cmd_packet = self.Packet()
        self.vendor_id = 0x187c
        self.product_id = 0x0529
        self._driver = self.Driver()
        self.fail_zone_restore = False
        self.apply_error = None

    def set_theme(self, theme_file, persist=True, reset=True):
        if self.apply_error is not None:
            raise self.apply_error
        if self.fail_zone_restore and not persist and not reset and len(self.apply_calls) > 1:
            raise RuntimeError("mock restore failure")
        self.applied_theme = theme_file.theme
        self.apply_calls.append({"theme": theme_file.theme, "persist": persist, "reset": reset})


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.config_dir = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.config_dir.name})
        self.environment.start()
        self.controller = FakeController()
        self.app = create_app(controller=self.controller)
        self.app.config["ZONE_TEST_SECONDS"] = 0.05
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.environment.stop()
        self.config_dir.cleanup()

    def csrf_token(self):
        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def test_catalog_has_ten_unique_palettes_per_effect(self):
        self.assertEqual(len(PRESETS), 130)
        self.assertEqual(len({preset["id"] for preset in PRESETS}), len(PRESETS))
        counts = Counter(preset["effect"] for preset in PRESETS)
        self.assertEqual(len(counts), 13)
        self.assertTrue(all(count >= 10 for count in counts.values()))
        for effect in counts:
            palettes = {tuple(preset["palette"]) for preset in PRESETS if preset["effect"] == effect}
            self.assertGreaterEqual(len(palettes), 10)
        for preset in PRESETS:
            self.assertEqual(len(preset["palette"]), 5)
            self.assertGreaterEqual(preset["speed"], 50)
            self.assertLessEqual(preset["speed"], 942)
            if preset["effect"] == "blink":
                self.assertGreaterEqual(preset["speed"], 220)
            elif preset["effect"] == "pulse":
                self.assertGreaterEqual(preset["speed"], 300)

    def test_smooth_recipes_use_only_morph_commands(self):
        for effect in (
            "blink", "pulse", "aurora", "shimmer", "comet", "orbit", "prism", "polyphase",
        ):
            with self.subTest(effect=effect):
                theme = build_theme(self.controller, ["#a060ff", "#00d9ff"], effect, 300)
                commands = [
                    action
                    for state in self.controller.state_map
                    for item in theme[state]
                    for action in item["loop"]
                ]
                self.assertTrue(commands)
                self.assertTrue(all(action["type"] == "morph" for action in commands))

    def test_new_fluid_effects_use_distinct_per_zone_morph_loops(self):
        colors = ["#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff"]
        for effect in ("orbit", "prism", "polyphase"):
            with self.subTest(effect=effect):
                theme = build_theme(self.controller, colors, effect, 180)
                loops = [item["loop"] for item in theme["Boot"]]
                signatures = {
                    tuple(tuple(action["colours"][0] + action["colours"][1]) for action in loop)
                    for loop in loops
                }
                self.assertEqual(len(loops), len(self.controller.zone_map))
                self.assertGreater(len(signatures), 1)
                self.assertTrue(all(action["type"] == "morph" for loop in loops for action in loop))
                self.assertTrue(all(preset["speed"] == 180 for preset in PRESETS if preset["effect"] == effect))
                if effect == "polyphase":
                    self.assertEqual({len(loop) for loop in loops}, {2, 3, 4})

    def test_flicker_effects_are_no_longer_supported(self):
        for effect in ("strobe", "glitch"):
            with self.subTest(effect=effect):
                with self.assertRaisesRegex(ValueError, "Unsupported effect"):
                    build_theme(self.controller, ["#ff0000"], effect, 180)

    def test_every_preset_maps_to_supported_zones_and_color_range(self):
        for preset in PRESETS:
            with self.subTest(preset=preset["id"]):
                theme = build_theme(
                    self.controller,
                    preset["palette"],
                    preset["effect"],
                    preset["speed"],
                )
                self.assertEqual(set(theme) - {"speed"}, set(self.controller.state_map))
                for state_items in (value for key, value in theme.items() if key != "speed"):
                    self.assertEqual(
                        {zone for item in state_items for zone in item["zones"]},
                        set(self.controller.zone_map),
                    )
                    for item in state_items:
                        for action in item["loop"]:
                            for color in action["colours"]:
                                self.assertEqual(len(color), 3)
                                self.assertTrue(all(0 <= channel <= 15 for channel in color))

    def test_custom_theme_supports_ten_shades(self):
        colors = ["#{:02x}{:02x}{:02x}".format(index * 20, 255 - index * 17, index * 11)
                  for index in range(10)]
        theme = build_theme(self.controller, colors, "spectrum", 75)
        self.assertEqual(len(theme["Boot"][0]["loop"]), 10)
        with self.assertRaisesRegex(ValueError, "one and ten colors"):
            build_theme(self.controller, colors + ["#ffffff"], "spectrum", 75)

    def test_extreme_tempo_25_is_supported_and_lower_values_are_rejected(self):
        theme = build_theme(self.controller, ["#ff0044", "#00ddff", "#f2ff00"], "orbit", 25)
        self.assertEqual(theme["speed"], 25)
        with self.assertRaisesRegex(ValueError, "25 to 942"):
            build_theme(self.controller, ["#ff0044", "#00ddff"], "orbit", 24)
        self.assertTrue(all(
            action["type"] == "morph"
            for item in theme["Boot"]
            for action in item["loop"]
        ))

    def test_smooth_effects_shift_brightness_between_zones_and_over_time(self):
        theme = build_theme(self.controller, ["#ffffff"], "morph", 180)
        loops = [item["loop"] for item in theme["Boot"]]
        zone_levels = [sum(loop[0]["colours"][0]) for loop in loops]
        self.assertGreater(len(set(zone_levels)), 1)
        self.assertTrue(any(
            action["colours"][0] != action["colours"][1]
            for loop in loops
            for action in loop
        ))
        self.assertTrue(all(action["type"] == "morph" for loop in loops for action in loop))

    def test_per_color_brightness_scales_theme_colors(self):
        theme = build_theme(
            self.controller,
            ["#ffffff", "#ffffff"],
            "fixed",
            75,
            [100, 50],
        )
        self.assertEqual(theme["Boot"][0]["loop"][0]["colours"], [[15, 15, 15]])
        self.assertEqual(theme["Boot"][1]["loop"][0]["colours"], [[8, 8, 8]])
        self.assertEqual(
            build_theme(self.controller, ["#ffffff"], "fixed", 75, [0])["Boot"][0]["loop"][0]["colours"],
            [[0, 0, 0]],
        )
        with self.assertRaisesRegex(ValueError, "one brightness value"):
            build_theme(self.controller, ["#ffffff"], "fixed", 75, [50, 60])
        with self.assertRaisesRegex(ValueError, "integers from 0 to 100"):
            build_theme(self.controller, ["#ffffff"], "fixed", 75, [101])

    def test_brightness_wave_does_not_change_fixed_or_blink_effects(self):
        fixed = build_theme(self.controller, ["#ffffff"], "fixed", 180)
        blink = build_theme(self.controller, ["#ffffff"], "blink", 220)
        self.assertTrue(all(
            action["colours"] == [[15, 15, 15]]
            for item in fixed["Boot"]
            for action in item["loop"]
        ))
        self.assertEqual(blink["Boot"][0]["loop"][0]["colours"], [[15, 15, 15], [5, 5, 5]])

    def test_saved_palettes_can_be_created_updated_loaded_and_deleted(self):
        self.client.get("/")
        headers = {"X-CSRF-Token": self.csrf_token()}
        colors = ["#{:02x}{:02x}{:02x}".format(index * 20, 255 - index * 17, index * 11)
                  for index in range(10)]
        brightness = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]
        payload = {
            "name": "Orbit Spectrum",
            "palette": colors,
            "brightness": brightness,
            "effect": "polyphase",
            "speed": 180,
        }
        self.assertEqual(self.client.get("/api/palettes").get_json(), [])
        created = self.client.post("/api/palettes", json=payload, headers=headers)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["palette"]["brightness"], brightness)
        palette_id = created.get_json()["palette"]["id"]
        self.assertEqual(self.client.post("/api/palettes", json=payload, headers=headers).status_code, 409)

        update = dict(payload, name="Orbit Spectrum Edit", effect="comet", speed=50)
        updated = self.client.put("/api/palettes/{}".format(palette_id), json=update, headers=headers)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["palette"]["name"], "Orbit Spectrum Edit")
        self.assertEqual(updated.get_json()["palette"]["effect"], "comet")
        self.assertEqual(updated.get_json()["palette"]["brightness"], brightness)

        reopened = create_app(controller=self.controller).test_client()
        self.assertEqual(reopened.get("/api/palettes").get_json()[0]["id"], palette_id)
        self.assertEqual(self.controller.apply_calls, [])

        deleted = self.client.delete("/api/palettes/{}".format(palette_id), headers=headers)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.get_json()["palettes"], [])

    def test_single_shade_palette_can_be_saved_and_applied(self):
        self.client.get("/")
        headers = {"X-CSRF-Token": self.csrf_token()}
        payload = {
            "name": "Single Shade",
            "palette": ["#ffffff"],
            "brightness": [100],
            "effect": "fixed",
            "speed": 75,
        }
        saved = self.client.post("/api/palettes", json=payload, headers=headers)
        self.assertEqual(saved.status_code, 201)
        self.assertEqual(saved.get_json()["palette"]["palette"], ["#FFFFFF"])

        applied = self.client.post(
            "/api/apply",
            json=dict(payload, preset_id="custom"),
            headers=headers,
        )
        self.assertEqual(applied.status_code, 200)
        self.assertEqual(
            self.controller.applied_theme["Boot"][0]["loop"][0]["colours"],
            [[15, 15, 15]],
        )

    def test_saved_palette_mutations_require_csrf_and_validate_recipe(self):
        self.client.get("/")
        payload = {"name": "Bad Palette", "palette": ["not-a-color"], "effect": "fixed", "speed": 50}
        self.assertEqual(self.client.post("/api/palettes", json=payload).status_code, 403)
        response = self.client.post(
            "/api/palettes",
            json=payload,
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/palettes").get_json(), [])

    def test_main_page_exposes_effect_filter_and_ten_shades(self):
        response = self.client.get("/")
        html = response.get_data(as_text=True)
        self.assertIn('id="effect-filter"', html)
        self.assertEqual(html.count('name="effect"'), 13)
        self.assertNotIn('value="strobe"', html)
        self.assertNotIn('value="glitch"', html)
        self.assertEqual(html.count('class="custom-color"'), 10)
        self.assertIn('id="add-shade"', html)
        self.assertIn('id="remove-shade"', html)
        self.assertIn('id="shade-count"', html)
        self.assertIn('id="palette-source"', html)
        self.assertIn('id="save-palette-new"', html)
        self.assertIn('data-lab-mode="extreme"', html)
        self.assertIn('id="generate-wild-palette"', html)
        self.assertIn('id="quit-studio"', html)
        self.assertIn('min="50"', html)
        asset_response = self.client.get("/static/shade-picker.css")
        self.assertEqual(asset_response.status_code, 200)
        asset_response.close()

    def test_apply_requires_csrf_token(self):
        self.client.get("/")
        response = self.client.post("/api/apply", json={"preset_id": PRESETS[0]["id"]})
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(self.controller.applied_theme)

    def test_shutdown_requires_csrf_and_running_server_callback(self):
        self.client.get("/")
        self.assertEqual(self.client.post("/api/shutdown").status_code, 403)
        response = self.client.post(
            "/api/shutdown",
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(response.status_code, 503)

    def test_apply_uses_existing_controller_interface(self):
        self.client.get("/")
        response = self.client.post(
            "/api/apply",
            json={"preset_id": PRESETS[0]["id"]},
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        self.assertIsNotNone(self.controller.applied_theme)
        self.assertTrue(self.client.get("/api/diagnostics").get_json()["profile_available"])

    def test_apply_reports_usb_permission_error(self):
        self.controller.apply_error = PermissionError(13, "Access denied")
        self.client.get("/")
        response = self.client.post(
            "/api/apply",
            json={"preset_id": PRESETS[0]["id"]},
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(response.status_code, 500)
        self.assertIn("USB access denied", response.get_json()["error"])

    def test_usb_driver_propagates_access_denied(self):
        driver = AlienFXUSBDriver(self.controller)
        driver._control_taken = True
        driver._dev = Mock()
        driver._dev.ctrl_transfer.side_effect = PermissionError(13, "Access denied")
        with self.assertRaises(PermissionError):
            driver.write_packet([1, 2, 3])

    def test_usb_driver_read_uses_finite_timeout(self):
        driver = AlienFXUSBDriver(self.controller)
        driver._control_taken = True
        driver._dev = Mock()
        driver._dev.ctrl_transfer.return_value = [self.controller.Packet.STATUS_READY]
        driver.read_packet()
        self.assertEqual(driver._dev.ctrl_transfer.call_args.args[-1], 1000)

    def test_controller_ready_timeout_raises_without_exiting_process(self):
        controller = AlienFXController13R3()
        controller._driver = Mock()
        controller._driver.read_packet.return_value = None
        with self.assertRaisesRegex(RuntimeError, "50 status requests"):
            controller._wait_controller_ready()
        self.assertEqual(controller._driver.write_packet.call_count, 50)

    def test_custom_palette_is_validated(self):
        self.client.get("/")
        response = self.client.post(
            "/api/apply",
            json={
                "preset_id": "custom",
                "palette": ["not-a-color"],
                "effect": "fixed",
                "speed": 75,
            },
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.controller.applied_theme)

    def test_no_controller_returns_status_without_scan(self):
        app = create_app(controller=None)
        response = app.test_client().get("/api/status")
        self.assertFalse(response.get_json()["connected"])
        self.assertIn("No scan", response.get_json()["message"])

    def test_diagnostics_reports_controller_protocol_and_touchpad_zone(self):
        response = self.client.get("/api/diagnostics")
        data = response.get_json()
        self.assertTrue(data["connected"])
        self.assertEqual(data["controller"]["vendor_id"], "187c")
        self.assertEqual(data["controller"]["product_id"], "0529")
        self.assertEqual(data["controller"]["revision"], 2)
        self.assertIn("Touchpad", {zone["name"] for zone in data["controller"]["zones"]})

    def test_status_probe_is_read_only(self):
        result = probe_link(self.controller)
        self.assertTrue(result["ok"])
        self.assertTrue(result["ready"])
        self.assertEqual(self.controller._driver.writes, [[2, 6, 0, 0, 0, 0, 0, 0, 0]])
        self.assertTrue(self.controller._driver.released)

    def test_status_probe_explains_busy_controller(self):
        self.controller._driver.response = [self.controller.Packet.STATUS_BUSY, 0, 0]
        result = probe_link(self.controller)
        self.assertTrue(result["ok"])
        self.assertFalse(result["ready"])
        self.assertIn("responded but is busy", result["detail"])

    def test_restore_tempo_is_clamped_to_protocol_range(self):
        profile = {"speed": 1, "Battery On": [{
            "zones": ["Touchpad"],
            "loop": [{"type": "fixed", "colours": [[1, 2, 3]]}],
        }]}
        restored = sanitize_restore_profile(self.controller, profile)
        self.assertEqual(restored["speed"], 25)

    def test_zone_test_profile_changes_only_selected_mapped_zone(self):
        theme = make_zone_test_profile(self.controller, "Touchpad", "#00ffff")
        self.assertEqual(set(theme) - {"speed"}, set(self.controller.state_map))
        for state_name in self.controller.state_map:
            items = theme[state_name]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["zones"], ["Touchpad"])
            self.assertEqual(items[0]["loop"][0]["type"], "fixed")

    def test_zone_restore_profile_keeps_only_selected_saved_zone(self):
        original = build_theme(self.controller, ["#112233", "#abcdef"], "morph", 75)
        restored = make_zone_restore_profile(self.controller, original, "Touchpad")
        self.assertEqual(restored["speed"], original["speed"])
        for state_name in self.controller.state_map:
            self.assertTrue(restored[state_name])
            self.assertTrue(all(item["zones"] == ["Touchpad"] for item in restored[state_name]))
            expected = [
                item["loop"] for item in original[state_name]
                if "Touchpad" in item["zones"]
            ]
            self.assertEqual([item["loop"] for item in restored[state_name]], expected)

    def test_temporary_controller_commands_omit_permanent_save(self):
        controller = AlienFXController13R3()
        theme = AlienFXThemeFile(controller)
        theme.theme = {
            "AC Sleep": [{
                "zones": ["Touchpad"],
                "loop": [{"type": "fixed", "colours": [[0, 12, 12]]}],
            }]
        }
        temporary = controller._make_zone_cmds(theme, "AC Sleep", persist=False)
        permanent = controller._make_zone_cmds(theme, "AC Sleep", persist=True)
        self.assertFalse(any(packet[1] == controller.cmd_packet.CMD_SAVE for packet in temporary))
        self.assertTrue(any(packet[1] == controller.cmd_packet.CMD_SAVE_NEXT for packet in temporary))
        self.assertTrue(any(packet[1] == controller.cmd_packet.CMD_SAVE for packet in permanent))

    def test_zone_test_refuses_without_a_complete_restore_profile(self):
        self.client.get("/")
        response = self.client.post(
            "/api/diagnostics/zone-test",
            json={"zone": "Touchpad", "color": "#ffffff"},
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.controller.apply_calls, [])

    def test_zone_test_changes_and_restores_only_selected_zone_on_request(self):
        self.client.get("/")
        apply_response = self.client.post(
            "/api/apply",
            json={"preset_id": PRESETS[0]["id"]},
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(apply_response.status_code, 200)
        original_theme = self.controller.applied_theme

        test_response = self.client.post(
            "/api/diagnostics/zone-test",
            json={"zone": "Touchpad", "color": "#ffffff"},
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(test_response.status_code, 200)
        test_call = self.controller.apply_calls[-1]
        self.assertFalse(test_call["persist"])
        self.assertFalse(test_call["reset"])
        self.assertTrue(all(
            item["zones"] == ["Touchpad"]
            for state_name in self.controller.state_map
            for item in test_call["theme"][state_name]
        ))

        time.sleep(0.12)
        self.assertEqual(len(self.controller.apply_calls), 2)
        status = self.client.get("/api/diagnostics").get_json()
        self.assertFalse(status["test_active"])
        self.assertTrue(status["restore_pending"])

        response = self.client.post(
            "/api/diagnostics/restore",
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(response.status_code, 200)
        restore_call = self.controller.apply_calls[-1]
        self.assertFalse(restore_call["persist"])
        self.assertFalse(restore_call["reset"])
        self.assertEqual(
            restore_call["theme"],
            make_zone_restore_profile(self.controller, original_theme, "Touchpad"),
        )
        self.assertFalse(self.client.get("/api/diagnostics").get_json()["restore_pending"])

    def test_failed_zone_test_does_not_retry_until_manual_restore(self):
        self.client.get("/")
        self.client.post(
            "/api/apply",
            json={"preset_id": PRESETS[0]["id"]},
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.controller.apply_error = RuntimeError("mock test failure")
        response = self.client.post(
            "/api/diagnostics/zone-test",
            json={"zone": "Touchpad", "color": "#ffffff"},
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(len(self.controller.apply_calls), 1)
        self.assertIn("No retry or restore was sent", response.get_json()["error"])
        state = self.client.get("/api/diagnostics").get_json()
        self.assertTrue(state["restore_pending"])
        self.assertTrue(state["restore_failed"])

        self.controller.apply_error = None
        restored = self.client.post(
            "/api/diagnostics/restore",
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(restored.status_code, 200)
        self.assertFalse(self.client.get("/api/diagnostics").get_json()["restore_failed"])
        self.assertEqual(len(self.controller.apply_calls), 2)
        self.assertTrue(all(
            item["zones"] == ["Touchpad"]
            for state_name in self.controller.state_map
            for item in self.controller.apply_calls[-1]["theme"][state_name]
        ))

    def test_failed_manual_zone_restore_waits_for_explicit_retry(self):
        self.client.get("/")
        headers = {"X-CSRF-Token": self.csrf_token()}
        self.client.post("/api/apply", json={"preset_id": PRESETS[0]["id"]}, headers=headers)
        self.client.post("/api/diagnostics/zone-test", json={"zone": "Touchpad"}, headers=headers)
        time.sleep(0.12)

        self.controller.fail_zone_restore = True
        with self.assertLogs(level="ERROR"):
            failed = self.client.post("/api/diagnostics/restore", headers=headers)
        self.assertEqual(failed.status_code, 500)
        self.assertEqual(len(self.controller.apply_calls), 2)
        time.sleep(0.12)
        self.assertEqual(len(self.controller.apply_calls), 2)

        self.controller.fail_zone_restore = False
        retried = self.client.post("/api/diagnostics/restore", headers=headers)
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(len(self.controller.apply_calls), 3)

    def test_local_ui_and_effect_assets_are_served(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"AlienFX Studio", page.data)
        for stylesheet in ("effects.css", "diagnostics.css", "zone-results.css"):
            asset = self.client.get(f"/static/{stylesheet}")
            self.assertEqual(asset.status_code, 200)
            asset.close()


if __name__ == "__main__":
    unittest.main()
