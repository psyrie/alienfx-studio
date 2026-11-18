"""Curated AlienFX palettes and safe theme construction helpers."""

import math
import re


# Original palettes are authored in display hex and quantized to AlienFX's
# four-bit-per-channel theme values (0..15) when building device commands.
_PRESET_ROWS = [
    ("xenon-bloom", "Xenon Bloom", ["#7C3AED", "#00E5FF", "#D7FF3F"], "morph", ["Alien", "Cosmic"], 74),
    ("neon-parasite", "Neon Parasite", ["#FF2BD6", "#8BFF00", "#00F0FF"], "blink", ["Psychedelic", "Alien"], 42),
    ("void-garden", "Void Garden", ["#1B0B3A", "#A855F7", "#39FFB6"], "morph", ["Alien", "Bioluminescent"], 88),
    ("plasma-orchard", "Plasma Orchard", ["#FF4D6D", "#FFB000", "#742BFF"], "morph", ["Psychedelic", "Cosmic"], 65),
    ("biolume-drift", "Biolume Drift", ["#00FFC6", "#65FF7A", "#146BFF"], "morph", ["Bioluminescent", "Alien"], 92),
    ("gamma-garden", "Gamma Garden", ["#C7FF00", "#00FF9D", "#3B1EFF"], "blink", ["Psychedelic", "Bioluminescent"], 38),
    ("chromatic-orbit", "Chromatic Orbit", ["#FF3CAC", "#784BA0", "#2B86C5"], "morph", ["Cosmic", "Vaporwave"], 80),
    ("acid-comet", "Acid Comet", ["#D6FF00", "#FF2E88", "#3C00FF"], "blink", ["Psychedelic", "Cosmic"], 35),
    ("deep-space-jelly", "Deep Space Jelly", ["#2DE2E6", "#9B5DE5", "#F15BB5"], "morph", ["Cosmic", "Bioluminescent"], 83),
    ("dream-circuit", "Dream Circuit", ["#00F5D4", "#F15BB5", "#FEE440"], "fixed", ["Vaporwave", "Psychedelic"], 72),
    ("xeno-aurora", "Xeno Aurora", ["#00FFB3", "#00A8FF", "#B000FF"], "morph", ["Alien", "Cosmic"], 96),
    ("ultraviolet-reef", "Ultraviolet Reef", ["#6A00F4", "#00D9FF", "#FF4DCE"], "morph", ["Bioluminescent", "Vaporwave"], 86),
    ("toxic-sunrise", "Toxic Sunrise", ["#B8FF00", "#FF5E00", "#FF00A8"], "blink", ["Psychedelic", "Alien"], 32),
    ("synth-nebula", "Synth Nebula", ["#FF71CE", "#01CDFE", "#05FFA1"], "morph", ["Vaporwave", "Cosmic"], 77),
    ("plasma-moth", "Plasma Moth", ["#FF00E5", "#7A00FF", "#00FFE1"], "blink", ["Alien", "Psychedelic"], 40),
    ("ghost-in-the-machine", "Ghost in the Machine", ["#E7FFF6", "#61FFE5", "#4B4DFF"], "morph", ["Alien", "Bioluminescent"], 104),
    ("starfruit-supernova", "Starfruit Supernova", ["#FFEC00", "#FF4FA3", "#6E37FF"], "morph", ["Cosmic", "Psychedelic"], 68),
    ("liquid-laser", "Liquid Laser", ["#00F0FF", "#FF00E6", "#B6FF00"], "blink", ["Psychedelic", "Vaporwave"], 34),
    ("blacklight-bloom", "Blacklight Bloom", ["#5B00FF", "#FF00B8", "#C5FF00"], "morph", ["Psychedelic", "Alien"], 89),
    ("nebula-noodle", "Nebula Noodle", ["#FF5CF4", "#8D62FF", "#39D6FF"], "morph", ["Cosmic", "Vaporwave"], 75),
    ("radioactive-rain", "Radioactive Rain", ["#9DFF00", "#00FF77", "#FFF000"], "blink", ["Bioluminescent", "Psychedelic"], 29),
    ("celestial-coral", "Celestial Coral", ["#FF6B6B", "#FFD166", "#7B61FF"], "fixed", ["Cosmic", "Bioluminescent"], 82),
    ("alien-monsoon", "Alien Monsoon", ["#00E5A8", "#3977FF", "#C94FFF"], "morph", ["Alien", "Bioluminescent"], 98),
    ("electric-nectar", "Electric Nectar", ["#E6FF00", "#FF00C8", "#00D5FF"], "blink", ["Psychedelic", "Alien"], 36),
    ("mirage-protocol", "Mirage Protocol", ["#FF79C6", "#BD93F9", "#8BE9FD"], "morph", ["Vaporwave", "Alien"], 73),
    ("event-horizon", "Event Horizon", ["#16002B", "#7C00FF", "#FF2F92"], "morph", ["Cosmic", "Alien"], 108),
    ("magma-microbe", "Magma Microbe", ["#FF2D00", "#FFB000", "#A600FF"], "blink", ["Alien", "Psychedelic"], 31),
    ("prism-afterglow", "Prism Afterglow", ["#FF4FD8", "#8C5BFF", "#4DFFF3"], "morph", ["Vaporwave", "Cosmic"], 84),
    ("hyperion-haze", "Hyperion Haze", ["#00D1FF", "#7B2FFF", "#FF3D81"], "morph", ["Cosmic", "Psychedelic"], 70),
    ("orchid-overdrive", "Orchid Overdrive", ["#C000FF", "#FF00A8", "#00FFC8"], "blink", ["Psychedelic", "Vaporwave"], 37),
    ("chlorophyll-cosmos", "Chlorophyll Cosmos", ["#5CFF00", "#00F5A0", "#741BFF"], "morph", ["Bioluminescent", "Cosmic"], 90),
    ("psychic-tide", "Psychic Tide", ["#00E7FF", "#FF48C4", "#E7FF4B"], "morph", ["Psychedelic", "Bioluminescent"], 66),
    ("lunar-lichen", "Lunar Lichen", ["#B8FFDE", "#7E7BFF", "#C9FF4A"], "fixed", ["Alien", "Bioluminescent"], 101),
    ("fuchsia-fission", "Fuchsia Fission", ["#FF00FF", "#FF5A00", "#2D00FF"], "blink", ["Psychedelic", "Cosmic"], 33),
    ("cyber-cuttlefish", "Cyber Cuttlefish", ["#00FFD1", "#FF4DA6", "#6500FF"], "morph", ["Alien", "Vaporwave"], 79),
    ("ion-storm", "Ion Storm", ["#00A6FF", "#C000FF", "#FF2A6D"], "blink", ["Cosmic", "Psychedelic"], 44),
    ("glowworm-galaxy", "Glowworm Galaxy", ["#B4FF39", "#00E5C3", "#6A5CFF"], "morph", ["Bioluminescent", "Cosmic"], 94),
    ("dream-eater", "Dream Eater", ["#FF00A8", "#7300FF", "#00F5FF"], "morph", ["Alien", "Psychedelic"], 63),
    ("quantum-quasar", "Quantum Quasar", ["#FFE600", "#FF3D9A", "#00B8FF"], "blink", ["Cosmic", "Vaporwave"], 39),
    ("sea-of-sparks", "Sea of Sparks", ["#00FFB8", "#00B4FF", "#D84CFF"], "morph", ["Bioluminescent", "Vaporwave"], 87),
    ("velvet-singularity", "Velvet Singularity", ["#240046", "#9D4EDD", "#FF70A6"], "fixed", ["Cosmic", "Vaporwave"], 76),
    ("chromatic-amoeba", "Chromatic Amoeba", ["#B2FF00", "#FF00D4", "#00C8FF"], "morph", ["Psychedelic", "Alien"], 57),
    ("saturns-garden", "Saturn's Garden", ["#FFB000", "#FF5CA8", "#41EAD4"], "morph", ["Cosmic", "Bioluminescent"], 91),
    ("neon-marrow", "Neon Marrow", ["#F000FF", "#00FFB3", "#FFEF00"], "blink", ["Psychedelic", "Alien"], 30),
    ("opal-ectoplasm", "Opal Ectoplasm", ["#B8FFF9", "#E6A7FF", "#C8FF72"], "morph", ["Alien", "Bioluminescent"], 110),
    ("hyperspace-honey", "Hyperspace Honey", ["#FFB703", "#FB5607", "#8338EC"], "morph", ["Cosmic", "Psychedelic"], 69),
    ("pink-noise-planet", "Pink Noise Planet", ["#FF2E93", "#FF7AC6", "#7A4DFF"], "blink", ["Vaporwave", "Psychedelic"], 41),
    ("mycelium-matrix", "Mycelium Matrix", ["#D5FF00", "#00F5B8", "#00A3FF"], "morph", ["Bioluminescent", "Alien"], 97),
    ("electric-eclipse", "Electric Eclipse", ["#17002E", "#5C00FF", "#00F5E9"], "morph", ["Cosmic", "Alien"], 103),
    ("neural-firefly", "Neural Firefly", ["#DFFF00", "#00FFA8", "#FF4FD8"], "blink", ["Bioluminescent", "Psychedelic"], 35),
]

def _showcase_effect(effect, index):
    if effect == "morph":
        return (
            "morph", "breathe", "ripple", "spectrum", "aurora", "shimmer",
            "comet", "orbit", "prism", "polyphase",
        )[index % 10]
    if effect == "blink":
        return ("pulse", "blink")[index % 2]
    return effect


def _showcase_speed(effect, speed):
    if effect in ("orbit", "prism", "polyphase"):
        return 180
    if effect == "comet":
        return 50
    if effect == "blink":
        return max(220, speed)
    if effect == "pulse":
        return max(300, speed)
    return max(50, speed)


def _scale_brightness(color, amount):
    return [max(0, min(15, int(round(channel * amount)))) for channel in color]


def _apply_zone_brightness(actions, zone_index, zone_count):
    if not actions:
        return actions
    phase = 2 * math.pi * zone_index / zone_count
    cycle_length = len(actions)
    for step, action in enumerate(actions):
        if action["type"] != "morph" or len(action["colours"]) != 2:
            continue
        start_wave = math.sin(phase + 2 * math.pi * step / cycle_length)
        end_wave = math.sin(phase + 2 * math.pi * (step + 1) / cycle_length)
        start_gain = 0.55 + 0.45 * (0.5 + 0.5 * start_wave)
        end_gain = 0.55 + 0.45 * (0.5 + 0.5 * end_wave)
        action["colours"] = [
            _scale_brightness(action["colours"][0], start_gain),
            _scale_brightness(action["colours"][1], end_gain),
        ]
    return actions


def _blend_hex(first, second):
    return "#" + "".join(
        "{:02X}".format(
            (int(first[index:index + 2], 16) + int(second[index:index + 2], 16)) // 2
        )
        for index in (1, 3, 5)
    )


def _expand_palette(palette):
    if len(palette) >= 5:
        return palette
    expanded = []
    for index, color in enumerate(palette[:-1]):
        expanded.extend((color, _blend_hex(color, palette[index + 1])))
    expanded.append(palette[-1])
    return expanded


PRESETS = [
    {
        "id": preset_id,
        "name": name,
        "palette": _expand_palette(palette),
        "effect": _showcase_effect(effect, index),
        "tags": tags,
        "speed": _showcase_speed(_showcase_effect(effect, index), speed),
    }
    for index, (preset_id, name, palette, effect, tags, speed) in enumerate(_PRESET_ROWS)
]
EFFECT_ORDER = (
    "fixed", "blink", "morph", "breathe", "ripple", "spectrum", "pulse",
    "comet", "orbit", "prism", "polyphase", "aurora", "shimmer",
)
EFFECT_LABELS = {
    "fixed": "Fixed",
    "blink": "Blink",
    "morph": "Morph",
    "breathe": "Breathe",
    "ripple": "Ripple",
    "spectrum": "Spectrum",
    "pulse": "Pulse",
    "comet": "Comet",
    "orbit": "Orbit",
    "prism": "Prism",
    "polyphase": "Polyphase",
    "aurora": "Aurora",
    "shimmer": "Shimmer",
}

for effect in EFFECT_ORDER:
    seen_palettes = {
        tuple(preset["palette"])
        for preset in PRESETS
        if preset["effect"] == effect
    }
    effect_count = sum(preset["effect"] == effect for preset in PRESETS)
    for preset_id, name, palette, _source_effect, tags, speed in _PRESET_ROWS:
        if effect_count >= 10:
            break
        expanded_palette = _expand_palette(palette)
        palette_key = tuple(expanded_palette)
        if palette_key in seen_palettes:
            continue
        PRESETS.append({
            "id": "{}-{}".format(preset_id, effect),
            "name": "{} / {}".format(name, EFFECT_LABELS[effect]),
            "palette": expanded_palette,
            "effect": effect,
            "tags": tags,
            "speed": _showcase_speed(effect, speed),
        })
        seen_palettes.add(palette_key)
        effect_count += 1

PRESETS_BY_ID = {preset["id"]: preset for preset in PRESETS}
ALLOWED_EFFECTS = {
    "fixed", "blink", "morph", "breathe", "ripple", "spectrum", "pulse",
    "comet", "orbit", "prism", "polyphase", "aurora", "shimmer",
}
def _hex_to_rgb4(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError("Colors must be six-digit hexadecimal values.")
    return [int(value[index:index + 2], 16) // 17 for index in (1, 3, 5)]


def validate_theme_options(palette, effect, speed):
    if effect not in ALLOWED_EFFECTS:
        raise ValueError("Unsupported effect.")
    if not isinstance(palette, list) or not 1 <= len(palette) <= 10:
        raise ValueError("Choose between one and ten colors.")
    colors = [_hex_to_rgb4(color) for color in palette]
    if isinstance(speed, bool) or not isinstance(speed, int) or not 25 <= speed <= 942:
        raise ValueError("Tempo must be an integer from 25 to 942.")
    return [color.upper() for color in palette], colors


def validate_brightness_levels(brightness, color_count):
    if brightness is None:
        return [100] * color_count
    if not isinstance(brightness, list) or len(brightness) != color_count:
        raise ValueError("Choose one brightness value from 0 to 100 for each color.")
    if any(
        isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 100
        for level in brightness
    ):
        raise ValueError("Brightness values must be integers from 0 to 100.")
    return list(brightness)


def build_theme(controller, palette, effect, speed, brightness=None):
    """Build the existing AlienFX JSON schema using only zones on this controller."""
    _palette, colors = validate_theme_options(palette, effect, speed)
    brightness_levels = validate_brightness_levels(brightness, len(colors))
    colors = [
        _scale_brightness(color, level / 100)
        for color, level in zip(colors, brightness_levels)
    ]

    zones = list(controller.zone_map)
    states = list(controller.state_map)
    if not zones or not states:
        raise ValueError("The detected controller does not expose usable zones and states.")

    theme = {"speed": speed}
    for state_name in states:
        items = []
        for index, zone_name in enumerate(zones):
            first = colors[index % len(colors)]
            if effect == "fixed":
                actions = [{"type": "fixed", "colours": [first]}]
            elif effect == "blink":
                dimmed = [channel // 3 for channel in first]
                off = [0, 0, 0]
                actions = [
                    {"type": "morph", "colours": [first, dimmed]},
                    {"type": "morph", "colours": [dimmed, off]},
                    {"type": "morph", "colours": [off, dimmed]},
                    {"type": "morph", "colours": [dimmed, first]},
                ]
            elif effect == "pulse":
                dimmed = [channel // 3 for channel in first]
                actions = [
                    {"type": "morph", "colours": [first, dimmed]},
                    {"type": "morph", "colours": [dimmed, first]},
                ]
            elif effect == "comet":
                phase = index % len(colors)
                lead = colors[phase]
                tail = [channel // 3 for channel in lead]
                next_color = colors[(phase + 1) % len(colors)]
                off = [0, 0, 0]
                actions = [
                    {"type": "morph", "colours": [off, lead]},
                    {"type": "morph", "colours": [lead, tail]},
                    {"type": "morph", "colours": [tail, off]},
                    {"type": "morph", "colours": [off, next_color]},
                ]
            elif effect == "orbit":
                if len(colors) == 1:
                    orbit_path = [first, [channel // 2 for channel in first], first]
                else:
                    stride = max(1, round(len(colors) / 3))
                    phase = (index * stride) % len(colors)
                    orbit_path = [
                        colors[(phase + step * stride) % len(colors)]
                        for step in range(3)
                    ]
                actions = [
                    {"type": "morph", "colours": [orbit_path[step], orbit_path[(step + 1) % 3]]}
                    for step in range(3)
                ]
            elif effect == "prism":
                if len(colors) == 1:
                    prism_path = [first, [channel // 2 for channel in first], first]
                else:
                    phase = index % len(colors)
                    distant = (phase + max(1, len(colors) // 2)) % len(colors)
                    prism_path = [colors[phase], colors[distant], colors[(phase + 1) % len(colors)]]
                actions = [
                    {"type": "morph", "colours": [prism_path[step], prism_path[(step + 1) % 3]]}
                    for step in range(3)
                ]
            elif effect == "polyphase":
                if len(colors) == 1:
                    polyphase_path = [first, [channel // 2 for channel in first]]
                else:
                    phase = (index * 2) % len(colors)
                    path_length = min(2 + index % 3, len(colors))
                    polyphase_path = [
                        colors[(phase + step) % len(colors)]
                        for step in range(path_length)
                    ]
                actions = [
                    {
                        "type": "morph",
                        "colours": [polyphase_path[step], polyphase_path[(step + 1) % len(polyphase_path)]],
                    }
                    for step in range(len(polyphase_path))
                ]
            elif effect == "breathe":
                off = [0, 0, 0]
                actions = [
                    {"type": "morph", "colours": [first, off]},
                    {"type": "morph", "colours": [off, first]},
                ]
            elif effect == "morph":
                second = colors[(index + 1) % len(colors)]
                actions = [
                    {"type": "morph", "colours": [first, second]},
                    {"type": "morph", "colours": [second, first]},
                ]
            elif effect == "aurora":
                aurora_colors = colors
                if len(aurora_colors) == 1:
                    aurora_colors = [first, [channel // 2 for channel in first]]
                direction = -1 if index % 2 else 1
                phase = index % len(aurora_colors)
                actions = [
                    {
                        "type": "morph",
                        "colours": [
                            aurora_colors[(phase + direction * step) % len(aurora_colors)],
                            aurora_colors[(phase + direction * (step + 1)) % len(aurora_colors)],
                        ],
                    }
                    for step in range(len(aurora_colors))
                ]
            elif effect == "shimmer":
                second = colors[(index + 1) % len(colors)]
                dimmed = [channel // 3 for channel in first]
                second_dimmed = [channel // 3 for channel in second]
                actions = [
                    {"type": "morph", "colours": [first, dimmed]},
                    {"type": "morph", "colours": [dimmed, second_dimmed]},
                    {"type": "morph", "colours": [second_dimmed, second]},
                    {"type": "morph", "colours": [second, first]},
                ]
            else:
                phase = index % len(colors) if effect == "ripple" else 0
                actions = [
                    {
                        "type": "morph",
                        "colours": [
                            colors[(phase + step) % len(colors)],
                            colors[(phase + step + 1) % len(colors)],
                        ],
                    }
                    for step in range(len(colors))
                ]
            if effect not in {"fixed", "blink"}:
                actions = _apply_zone_brightness(actions, index, len(zones))
            items.append({"zones": [zone_name], "loop": actions})
        theme[state_name] = items
    return theme
