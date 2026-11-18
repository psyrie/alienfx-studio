"""Conservative, controller-aware diagnostics for the local web UI."""

import re


def describe_controller(controller):
    packet = controller.cmd_packet
    return {
        "name": getattr(controller, "name", "AlienFX controller"),
        "vendor_id": "{:04x}".format(controller.vendor_id),
        "product_id": "{:04x}".format(controller.product_id),
        "revision": getattr(packet, "controllerrevision", None),
        "packet_length": getattr(packet, "PACKET_LENGTH", None),
        "zones": [
            {
                "name": name,
                "code": "0x{:04x}".format(code),
                "power_zone": name in getattr(controller, "power_zones", []),
            }
            for name, code in controller.zone_map.items()
        ],
        "states": list(controller.state_map),
    }


def probe_link(controller):
    """Send only the protocol GET_STATUS request; never reset or set lights."""
    driver = controller._driver
    driver.acquire()
    try:
        driver.write_packet(controller.cmd_packet.make_cmd_get_status())
        response = driver.read_packet()
    finally:
        driver.release()

    if response is None or len(response) == 0:
        return {
            "ok": False,
            "status": "No status response",
            "detail": "The USB controller was found, but it did not return a status packet.",
        }

    response = list(response)
    code = response[0]
    if code == controller.cmd_packet.STATUS_READY:
        label = "Ready"
        ok = True
        ready = True
    elif code == controller.cmd_packet.STATUS_BUSY:
        label = "Busy"
        ok = True
        ready = False
    else:
        label = "Unrecognized status 0x{:02x}".format(code)
        ok = False
        ready = False
    return {
        "ok": ok,
        "ready": ready,
        "status": label,
        "status_code": "0x{:02x}".format(code),
        "response_length": len(response),
        "detail": (
            "GET_STATUS returned READY; no reset, lighting, or save command was sent."
            if ready else
            "The controller responded but is busy; this read-only probe sent no lighting or save command."
            if code == controller.cmd_packet.STATUS_BUSY else
            "GET_STATUS returned an unrecognized status; no lighting or save command was sent."
        ),
    }


def sanitize_restore_profile(controller, profile):
    """Keep only valid actions and zones supported by the detected controller."""
    if not isinstance(profile, dict):
        return None

    speed = profile.get("speed", getattr(controller, "DEFAULT_SPEED", 75))
    if isinstance(speed, bool) or not isinstance(speed, int) or not 1 <= speed <= 65535:
        speed = getattr(controller, "DEFAULT_SPEED", 75)
    speed = min(942, max(25, speed))

    allowed_zones = set(controller.zone_map)
    restored = {"speed": speed}
    valid_items = 0
    for state_name in controller.state_map:
        output_items = []
        state_items = profile.get(state_name, [])
        if not isinstance(state_items, list):
            continue
        for item in state_items:
            if not isinstance(item, dict):
                continue
            raw_zones = item.get("zones", [])
            zones = list(dict.fromkeys(
                zone for zone in raw_zones
                if isinstance(zone, str) and zone in allowed_zones
            )) if isinstance(raw_zones, list) else []
            raw_actions = item.get("loop", [])
            if not zones or not isinstance(raw_actions, list):
                continue
            actions = []
            for action in raw_actions:
                if not isinstance(action, dict):
                    continue
                kind = action.get("type")
                colors = action.get("colours")
                expected_count = 2 if kind == "morph" else 1
                if kind not in {"fixed", "blink", "morph"}:
                    continue
                if not isinstance(colors, list) or len(colors) != expected_count:
                    continue
                if any(
                    not isinstance(color, list)
                    or len(color) != 3
                    or any(
                        isinstance(channel, bool)
                        or not isinstance(channel, int)
                        or not 0 <= channel <= 15
                        for channel in color
                    )
                    for color in colors
                ):
                    continue
                actions.append({"type": kind, "colours": colors})
            if actions:
                output_items.append({"zones": zones, "loop": actions})
                valid_items += 1
        restored[state_name] = output_items

    return restored if valid_items else None


def make_zone_test_profile(controller, zone_name, color_hex):
    """Make a fixed-color test that changes only the requested zone."""
    if zone_name not in controller.zone_map:
        raise ValueError("That zone is not mapped for the detected controller.")
    if not isinstance(color_hex, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color_hex):
        raise ValueError("Choose a valid six-digit hex color.")

    color = [int(color_hex[index:index + 2], 16) // 17 for index in (1, 3, 5)]
    result = {"speed": getattr(controller, "DEFAULT_SPEED", 75)}
    for state_name in controller.state_map:
        result[state_name] = [{
            "zones": [zone_name],
            "loop": [{"type": "fixed", "colours": [color]}],
        }]
    return result


def make_zone_restore_profile(controller, profile, zone_name):
    """Keep only the saved actions for one mapped zone across all states."""
    if zone_name not in controller.zone_map:
        raise ValueError("That zone is not mapped for the detected controller.")
    if not isinstance(profile, dict):
        raise ValueError("A saved lighting profile is required to restore this zone.")

    result = {"speed": profile.get("speed", getattr(controller, "DEFAULT_SPEED", 75))}
    found = False
    for state_name in controller.state_map:
        items = []
        for item in profile.get(state_name, []):
            if not isinstance(item, dict) or zone_name not in item.get("zones", []):
                continue
            actions = item.get("loop", [])
            if actions:
                items.append({"zones": [zone_name], "loop": actions})
                found = True
        result[state_name] = items
    if not found:
        raise ValueError("The saved profile has no actions for the selected zone.")
    return result
