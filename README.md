# OpenRouter Image für Home Assistant

Custom-Integration, die OpenRouter als Backend für `ai_task.generate_image` einbindet.
Damit lassen sich alle Bildmodelle nutzen, die OpenRouter anbietet – Gemini Image,
FLUX.2, Riverflow und was sonst noch dazukommt – ohne für jedes einen eigenen
Anbieter-Account zu brauchen.

Die Core-Integration `open_router` kann nur Text und strukturierte Daten
(`ai_task.generate_data`). Diese Integration ergänzt den fehlenden Bildteil und
läuft parallel dazu.

## Installation

### HACS

1. HACS → ⋮ → *Custom repositories*
2. URL dieses Repos eintragen, Kategorie **Integration**
3. *OpenRouter Image* installieren
4. Home Assistant neu starten

### Manuell

`custom_components/openrouter_image` nach `<config>/custom_components/` kopieren
und Home Assistant neu starten.

## Einrichtung

1. *Einstellungen → Geräte & Dienste → Integration hinzufügen → OpenRouter Image*
2. API-Key von <https://openrouter.ai/keys> eintragen
3. Auf der Integrationsseite **Bildgenerator hinzufügen** wählen

Im Untereintrag stehen zur Auswahl:

| Option | Bedeutung |
| --- | --- |
| Modell | Nur Modelle mit `output_modalities: ["image"]` werden gelistet |
| Seitenverhältnis | `1:1` bis `21:9`, wird als `image_config.aspect_ratio` gesendet |
| Bildgröße | `1K`/`2K`/`4K`, derzeit nur von Gemini unterstützt |
| Zeitlimit | Sekunden, bis die Anfrage abgebrochen wird (Standard 180) |
| Prompt-Zusatz | Text, der an jeden Prompt angehängt wird, z. B. ein fester Stil |

`Modell-Standard` bei Seitenverhältnis oder Bildgröße bedeutet: Der Parameter
wird gar nicht mitgeschickt. Das ist für Modelle wichtig, die `image_config`
nicht kennen und sonst mit einem Fehler antworten.

Mehrere Untereinträge sind möglich – etwa ein schnelles, günstiges Modell für
Benachrichtigungen und ein hochauflösendes für Dashboard-Hintergründe.

## Verwendung

```yaml
action: ai_task.generate_image
data:
  task_name: wetter_bild
  entity_id: ai_task.gemini_3_pro_image
  instructions: >-
    Ein minimalistisches Aquarell einer verregneten Straße bei Dämmerung,
    gedämpfte Blautöne, kein Text.
response_variable: generated
```

Das Ergebnis enthält `url`, `media_source_id`, `mime_type`, `width`, `height`,
`model` und `revised_prompt`. Die `url` ist signiert und läuft nach kurzer Zeit
ab; `media_source_id` bleibt gültig.

Beispiel als vollständige Automatisierung:

```yaml
alias: Tägliches Wetterbild
triggers:
  - trigger: time
    at: "06:30:00"
actions:
  - action: ai_task.generate_image
    data:
      task_name: wetter_bild
      entity_id: ai_task.gemini_3_pro_image
      instructions: >-
        Erzeuge ein stimmungsvolles Bild passend zu diesem Wetter:
        {{ states('weather.zuhause') }}, {{ state_attr('weather.zuhause','temperature') }} °C.
        Keine Schrift im Bild.
    response_variable: generated
  - action: notify.mobile_app_pixel
    data:
      title: Guten Morgen
      message: "{{ states('weather.zuhause') }}"
      data:
        image: "{{ generated.url }}"
```

### Bildbearbeitung mit Anhängen

Die Entität meldet `SUPPORT_ATTACHMENTS`. Bildmodelle, die Bild-zu-Bild können
(z. B. Gemini Image), lassen sich damit zum Editieren verwenden:

```yaml
action: ai_task.generate_image
data:
  task_name: kamera_stilisieren
  entity_id: ai_task.gemini_3_pro_image
  instructions: Mach daraus eine Bleistiftzeichnung.
  attachments:
    - media_content_id: media-source://camera/camera.haustuer
      media_content_type: image/jpeg
response_variable: generated
```

Nur Bild-Anhänge werden akzeptiert, maximal 20 MB pro Datei.

## Wie es funktioniert

OpenRouter erzeugt Bilder über den normalen Chat-Endpunkt. Die Integration
schickt an `POST /api/v1/chat/completions`:

```json
{
  "model": "google/gemini-3-pro-image-preview",
  "messages": [{ "role": "user", "content": [{ "type": "text", "text": "..." }] }],
  "modalities": ["image", "text"],
  "image_config": { "aspect_ratio": "16:9" }
}
```

Die Antwort liefert das Bild als Base64-Data-URL unter
`choices[0].message.images[0].image_url.url`. Die wird dekodiert und als
`GenImageTaskResult` zurückgegeben; Home Assistant legt die Datei selbst in der
Media-Source ab.

Breite und Höhe werden direkt aus den Bild-Headern gelesen (PNG, JPEG, WebP),
ohne zusätzliche Abhängigkeit. Die Integration hat keine `requirements`.

## Bekannte Einschränkungen

- `image_config` wird nur von Gemini-Modellen zuverlässig beachtet. Bei anderen
  Modellen `Modell-Standard` wählen.
- Bei hohen Auflösungen kann eine Anfrage über eine Minute dauern. Das Zeitlimit
  ist deshalb konfigurierbar.
- Liefert ein Modell mehrere Bilder, wird nur das erste verwendet – die
  `ai_task`-API in Home Assistant kennt bislang nur ein Bild pro Aufruf.
- Streaming wird nicht genutzt, es wird auf die vollständige Antwort gewartet.

## Voraussetzungen

Home Assistant 2025.7 oder neuer (wegen `ai_task` mit `GENERATE_IMAGE` und
Config-Subentries).

## Lizenz

MIT
