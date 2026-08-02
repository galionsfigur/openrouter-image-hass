# OpenRouter Image for Home Assistant

Custom integration that plugs OpenRouter in as a backend for
`ai_task.generate_image`. This gives you access to every image model
OpenRouter offers — Gemini Image, FLUX.2, Riverflow, and whatever else shows
up — without needing a separate provider account for each one.

The core `open_router` integration only handles text and structured data
(`ai_task.generate_data`). This integration adds the missing image part and
runs alongside it.

## Installation

### HACS

1. HACS → ⋮ → *Custom repositories*
2. Add this repository's URL, category **Integration**
3. Install *OpenRouter Image*
4. Restart Home Assistant

### Manual

Copy `custom_components/openrouter_image` to `<config>/custom_components/`
and restart Home Assistant.

## Setup

1. *Settings → Devices & Services → Add Integration → OpenRouter Image*
2. Enter an API key from <https://openrouter.ai/keys>
3. On the integration page, choose **Add image generator**

The subentry offers these options:

| Option | Meaning |
| --- | --- |
| Model | Only models with `output_modalities: ["image"]` are listed |
| Aspect ratio | `1:1` to `21:9`, sent as `image_config.aspect_ratio` |
| Image size | `1K`/`2K`/`4K`, currently only honoured by Gemini |
| Timeout | Seconds until the request is aborted (default 180) |
| Prompt suffix | Text appended to every prompt, e.g. a fixed style |

`Model default` for aspect ratio or image size means the parameter isn't
sent at all. That matters for models that don't understand `image_config`
and would otherwise error out.

Multiple subentries are possible — for example a fast, cheap model for
notifications and a high-resolution one for dashboard backgrounds.

## Usage

```yaml
action: ai_task.generate_image
data:
  task_name: weather_image
  entity_id: ai_task.gemini_3_pro_image
  instructions: >-
    A minimalist watercolor of a rainy street at dusk, muted blue tones,
    no text.
response_variable: generated
```

The result contains `url`, `media_source_id`, `mime_type`, `width`,
`height`, `model` and `revised_prompt`. The `url` is signed and expires
after a short time; `media_source_id` stays valid.

Example as a full automation:

```yaml
alias: Daily weather image
triggers:
  - trigger: time
    at: "06:30:00"
actions:
  - action: ai_task.generate_image
    data:
      task_name: weather_image
      entity_id: ai_task.gemini_3_pro_image
      instructions: >-
        Generate an atmospheric image matching this weather:
        {{ states('weather.home') }}, {{ state_attr('weather.home','temperature') }} °C.
        No text in the image.
    response_variable: generated
  - action: notify.mobile_app_pixel
    data:
      title: Good morning
      message: "{{ states('weather.home') }}"
      data:
        image: "{{ generated.url }}"
```

### Image editing with attachments

The entity reports `SUPPORT_ATTACHMENTS`. Image models capable of
image-to-image (e.g. Gemini Image) can be used for editing:

```yaml
action: ai_task.generate_image
data:
  task_name: stylize_camera
  entity_id: ai_task.gemini_3_pro_image
  instructions: Turn this into a pencil sketch.
  attachments:
    - media_content_id: media-source://camera/camera.front_door
      media_content_type: image/jpeg
response_variable: generated
```

Only image attachments are accepted, up to 20 MB per file.

## How it works

OpenRouter generates images through the regular chat endpoint. The
integration sends a `POST /api/v1/chat/completions`:

```json
{
  "model": "google/gemini-3-pro-image-preview",
  "messages": [{ "role": "user", "content": [{ "type": "text", "text": "..." }] }],
  "modalities": ["image", "text"],
  "image_config": { "aspect_ratio": "16:9" }
}
```

The response returns the image as a base64 data URL under
`choices[0].message.images[0].image_url.url`. That gets decoded and
returned as a `GenImageTaskResult`; Home Assistant stores the file in the
media source itself.

Width and height are read directly from the image headers (PNG, JPEG,
WebP), without any extra dependency. The integration has no
`requirements`.

## Known limitations

- `image_config` is reliably honoured only by Gemini models. Choose
  `Model default` for other models.
- High resolutions can take a request over a minute. That's why the
  timeout is configurable.
- If a model returns multiple images, only the first is used — Home
  Assistant's `ai_task` API currently only supports one image per call.
- Streaming isn't used; the integration waits for the full response.

## Requirements

Home Assistant 2025.7 or newer (for `ai_task` with `GENERATE_IMAGE` and
config subentries).

## License

MIT
