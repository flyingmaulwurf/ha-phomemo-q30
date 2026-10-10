# Phomemo Q30 label printer for Home Assistant

[Magyar leírás](README.hu.md)

Print labels from Home Assistant on a **Phomemo Q30** (and probably other Phomemo
label printers of the same family, such as the D30) over Bluetooth LE.

- Type a text into a **Label text** entity and press the **Print label** button, or
- call the `phomemo_q30.print_text` / `phomemo_q30.print_image` actions from scripts,
  automations, dashboards or the **Assist** voice assistant ("print a label: Chicken
  breast 2026-10-14").
- Text is sized automatically: one line at the largest size that fits; if two lines
  allow bigger letters, it is wrapped at the best space.
- Label size and margins are set in millimetres from the Home Assistant UI, so any
  custom label size works.

## Requirements

- Home Assistant 2025.1 or newer with the **Bluetooth** integration, using either
  - the Bluetooth adapter of the machine running Home Assistant, or
  - an **ESPHome Bluetooth proxy** near the printer. Any ESP32 running the ESPHome
    `bluetooth_proxy` works (tested with ESPHome-flashed Tuya devices acting as proxies).
    The proxy must allow connections: `bluetooth_proxy: active: true`.
- A Phomemo Q30 with gap labels loaded.

## Installation

### HACS (custom repository)

1. HACS → three dots → **Custom repositories**.
2. Add `https://github.com/YOUR_GITHUB_USERNAME/ha-phomemo-q30` with category **Integration**.
3. Download **Phomemo Q30 label printer** and restart Home Assistant.

### Manual

Copy `custom_components/phomemo_q30` into the `custom_components` folder of your
Home Assistant configuration and restart.

## Setup

1. Switch the printer on. Make sure nothing else (phone app, web app) is connected to
   it: the printer accepts only one Bluetooth connection at a time.
2. **Settings → Devices & services → Add integration → Phomemo Q30 label printer**.
3. Pick the printer from the list, or type its Bluetooth address
   (e.g. `AA:BB:CC:DD:EE:FF`). Enter the label size (default 28 × 12 mm).

Label size and margins can be changed later: **Settings → Devices & services →
Phomemo Q30 label printer → Configure**.

| Setting | Meaning |
|---|---|
| Label length | Long side of the label, in the direction the paper comes out (mm) |
| Label width | Short side of the label, across the paper (mm) |
| Margin at the ends | Empty space at both ends of the label (mm) |
| Margin at the sides | Empty space along the two long edges (mm) |

If text is cut off at the edges, increase the margins.

## Using it

### Entities

Open the printer's device page. There you find:

- **Label text**: the text of the next label (remembered across restarts). Write `\n`
  for a line break; usually not needed because long text is wrapped automatically.
- **Print label**: prints the current text.

### Actions

```yaml
action: phomemo_q30.print_text
data:
  text: "Chicken breast 2026-10-14"
  copies: 1          # optional
  font_size: 0       # optional, 0 = automatic (default)
  length_mm: 40      # optional, overrides the configured label length for this print
  width_mm: 15       # optional, overrides the configured label width for this print
```

```yaml
action: phomemo_q30.print_image
data:
  path: /config/www/label.png   # folder must be allowed (allowlist_external_dirs), /config is
  rotate: 0                     # 0 / 90 / 180 / 270
  dither: true                  # on for photos, off for sharp graphics
```

With more than one printer, also pass `device_id`.

### Voice / OpenAI (Assist)

Create a script and expose it to Assist (**Settings → Voice assistants → Expose**). With
the OpenAI Conversation integration set to **Control Home Assistant: Assist**, you can
then say "print a label: Milk 2026-10-14".

```yaml
alias: Print label
description: >-
  Prints a label on the Phomemo Q30 label printer. Use this when the user asks
  to print a label or sticker. Pass the exact text that should be on the label.
mode: single
fields:
  text:
    name: Text
    description: The text to print on the label, for example "Chicken breast 2026-10-14"
    required: true
    example: "Chicken breast 2026-10-14"
    selector:
      text:
  copies:
    name: Copies
    description: How many labels to print (default 1)
    required: false
    default: 1
    selector:
      number:
        min: 1
        max: 10
sequence:
  - action: phomemo_q30.print_text
    data:
      text: "{{ text }}"
      copies: "{{ copies | default(1) }}"
```

## Troubleshooting

| Problem | What to do |
|---|---|
| Printer not in the list | Switch it on, disconnect other apps, keep it close to the adapter/proxy, or type its address. |
| `org.bluez.Error.BREDR.ProfileUnavailable` | BlueZ cached the printer as a classic Bluetooth device. Run `bluetoothctl remove <address>` on the host and try again. |
| "not in Bluetooth range" | Home Assistant does not hear the printer. Move the adapter/proxy closer, or use an ESPHome proxy with `active: true`. |
| Prints, but cut off or on the wrong label | Check label length/width and margins in **Configure**. |
| Prints are slow, or incomplete | The Bluetooth connection is set up for every print (a few seconds). Timing values are at the top of `printer.py` (`CHUNK_DELAY`, `SETTLE_DELAY`). |

Debug log:

```yaml
logger:
  logs:
    custom_components.phomemo_q30: debug
```

## How it works

The Q30 exposes a BLE service `0000ff00-…` with a write characteristic `0000ff02-…` and
a notify characteristic `0000ff03-…` that acknowledges every write. A label is rendered
with Pillow to a 1-bit bitmap at 8 dots/mm and sent as ESC/POS raster blocks (at most
255 lines per block), preceded by the speed/density/media commands and followed by the
end-of-job commands. The command sequence was worked out on a real Q30 with the help of
the open projects below. Helper scripts for experimenting are in [`tools/`](tools/).

## Status

Tested on one Phomemo Q30 with 28 × 12 mm gap labels, through the Bluetooth adapter and
through ESPHome Bluetooth proxies. Other models, label sizes and firmware versions may
need adjustments: please open an issue and include the debug log.

## Credits

- [dmsc/web-label-printer](https://github.com/dmsc/web-label-printer): BLE service and
  characteristic identifiers and the basic raster approach for the D30/Q30.
- [vivier/phomemo-tools](https://github.com/vivier/phomemo-tools): documentation of the
  command sequences of the Phomemo printer family.

## License

[MIT](LICENSE)
