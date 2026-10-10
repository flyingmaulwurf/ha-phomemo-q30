# Phomemo Q30 címkenyomtató Home Assistanthoz

[English README](README.md)

Címkenyomtatás Home Assistantból **Phomemo Q30** (és valószínűleg a hasonló D30)
nyomtatóra, Bluetooth LE-n.

- Írd be a szöveget a **Label text** mezőbe, és nyomd meg a **Print label** gombot, vagy
- hívd a `phomemo_q30.print_text` / `phomemo_q30.print_image` műveleteket scriptből,
  automatizációból, műszerfalról vagy az **Assist** hangsegédből ("nyomtass egy
  címkét: Csirkemell 2026-10-14").
- A szöveg magától igazodik: egy sorban a legnagyobb betűvel, ami elfér; ha két sorban
  nagyobb betű férne el, a legjobb szóköznél két sorra töri.
- A címke mérete és a margók milliméterben állíthatók a Home Assistant felületén,
  bármilyen egyedi címkemérettel.

## Követelmények

- Home Assistant 2025.1 vagy újabb, **Bluetooth** integrációval, a következők egyikével:
  - a Home Assistant gépének Bluetooth adaptere, vagy
  - **ESPHome Bluetooth proxy** a nyomtató közelében. Bármelyik ESP32 működik ESPHome
    `bluetooth_proxy`-val (ESPHome-mal flashelt Tuya eszközökkel, proxyként is
    kipróbálva). A proxynak kapcsolódni is kell tudnia: `bluetooth_proxy: active: true`.
- Phomemo Q30, réses (gap) címkékkel.

## Telepítés

### HACS (egyedi tároló)

1. HACS → három pont → **Custom repositories**.
2. Add hozzá: `https://github.com/YOUR_GITHUB_USERNAME/ha-phomemo-q30`, kategória: **Integration**.
3. Töltsd le a **Phomemo Q30 label printer** integrációt, majd indítsd újra a Home Assistantot.

### Kézzel

Másold a `custom_components/phomemo_q30` mappát a Home Assistant konfigurációs mappájának
`custom_components` könyvtárába, majd indítsd újra.

## Beállítás

1. Kapcsold be a nyomtatót. Ügyelj rá, hogy semmi más (telefonos app, web app) ne legyen
   hozzá csatlakozva: egyszerre csak egy Bluetooth kapcsolatot fogad.
2. **Settings → Devices & services → Add integration → Phomemo Q30 label printer**.
3. Válaszd ki a nyomtatót a listából, vagy írd be a Bluetooth címét
   (pl. `AA:BB:CC:DD:EE:FF`). Add meg a címke méretét (alapértelmezés: 28 × 12 mm).

A címke mérete és a margók később is módosíthatók: **Settings → Devices & services →
Phomemo Q30 label printer → Configure**.

| Beállítás | Jelentése |
|---|---|
| Label length | A címke hosszú oldala, a papír kijövetelének irányában (mm) |
| Label width | A címke rövid oldala, a papírra merőlegesen (mm) |
| Margin at the ends | Üres hely a címke két végén (mm) |
| Margin at the sides | Üres hely a két hosszú szélen (mm) |

Ha a szöveg a szélén levágódik, növeld a margókat.

## Használat

### Entitások

A nyomtató eszközoldalán találod:

- **Label text**: a következő címke szövege (újraindítás után is megmarad). `\n`-nel
  sortörést adhatsz, de általában nem kell, mert a hosszú szöveget magától töri.
- **Print label**: kinyomtatja az aktuális szöveget.

### Műveletek

```yaml
action: phomemo_q30.print_text
data:
  text: "Csirkemell 2026-10-14"
  copies: 1          # opcionális
  font_size: 0       # opcionális, 0 = automatikus (alapértelmezés)
  length_mm: 40      # opcionális, erre a nyomtatásra felülírja a címke hosszát
  width_mm: 15       # opcionális, erre a nyomtatásra felülírja a címke szélességét
```

```yaml
action: phomemo_q30.print_image
data:
  path: /config/www/label.png   # a mappának engedélyezettnek kell lennie (allowlist_external_dirs), a /config az
  rotate: 0                     # 0 / 90 / 180 / 270
  dither: true                  # fotókhoz be, éles grafikához ki
```

Több nyomtatónál add meg a `device_id`-t is.

### Hang / OpenAI (Assist)

Hozz létre egy scriptet, és oszd meg az Assisttal (**Settings → Voice assistants →
Expose**). Ha az OpenAI Conversation **Control Home Assistant: Assist** módban van,
mondhatod: "nyomtass egy címkét: Tej 2026-10-14". A script YAML-ja az
[angol README-ben](README.md#voice--openai-assist) van.

## Hibaelhárítás

| Gond | Teendő |
|---|---|
| A nyomtató nincs a listában | Kapcsold be, bontsd a többi kapcsolatot, vidd közelebb az adapterhez/proxyhoz, vagy írd be a címét. |
| `org.bluez.Error.BREDR.ProfileUnavailable` | A BlueZ klasszikus Bluetooth eszközként tárolta a nyomtatót. A gépen futtasd: `bluetoothctl remove <cím>`, majd próbáld újra. |
| "not in Bluetooth range" | A Home Assistant nem hallja a nyomtatót. Vidd közelebb az adaptert/proxyt, vagy használj `active: true` ESPHome proxyt. |
| Nyomtat, de levágja vagy rossz a címke | Ellenőrizd a hosszt/szélességet és a margókat a **Configure** ablakban. |
| Lassú vagy hiányos a nyomtatás | A Bluetooth kapcsolat minden nyomtatásnál újra felépül (pár másodperc). Az időzítések a `printer.py` elején vannak (`CHUNK_DELAY`, `SETTLE_DELAY`). |

Hibakeresési napló:

```yaml
logger:
  logs:
    custom_components.phomemo_q30: debug
```

## Állapot

Egy Phomemo Q30-on, 28 × 12 mm-es réses címkékkel tesztelve, a Bluetooth adapteren és
ESPHome Bluetooth proxykon keresztül is. Más modellek, címkeméretek és firmware-ek
igazítást kérhetnek: nyiss egy issue-t, és csatold a debug naplót.

## Licenc

[MIT](LICENSE)
