# hass_nemo

[![GitHub release (latest by date including pre-releases)](https://img.shields.io/github/v/release/jaycollett/hass_nemo?include_prereleases)](https://github.com/jaycollett/hass_nemo/releases)
[![GitHub last commit](https://img.shields.io/github/last-commit/jaycollett/hass_nemo)](https://github.com/jaycollett/hass_nemo/commits/main)
[![GitHub issues](https://img.shields.io/github/issues-raw/jaycollett/hass_nemo)](https://github.com/jaycollett/hass_nemo/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/jaycollett/hass_nemo)](https://github.com/jaycollett/hass_nemo/pulls)
[![GitHub](https://img.shields.io/github/license/jaycollett/hass_nemo)](https://github.com/jaycollett/hass_nemo/blob/main/LICENSE)

A small Docker image that wraps the [NVIDIA NeMo text processing](https://github.com/NVIDIA/NeMo-text-processing) TN (Text Normalization) engine in a simple REST API. I use it with Home Assistant and my Piper TTS integration as part of my text pre-processing pipeline - it converts things like "$5.30", "3/14/2026", and "72F" into words that TTS engines can pronounce naturally.

NeMo's WFST text normalization runs entirely on CPU (pynini/OpenFST), so no GPU is required. Long input is automatically split on sentence boundaries (NVIDIA's recommended approach) to avoid the performance blowup NeMo hits on long single strings.

A user-editable [preprocessing layer](#preprocessing-rules) rewrites text with your own regex rules *before* NeMo sees it - for example turning a bare `72F` into `72°F` so it's spoken as "seventy two degrees Fahrenheit". Rules live in a simple JSON file you can mount into the container; no rebuild and no Python required.

**Docker CLI:**

    docker run -dit \
    -p 5000:5000 \
    -e LANG_TO_USE=en \
    -v nemo_cache:/cache \
    ghcr.io/jaycollett/hass_nemo:latest

The `/cache` volume is optional but recommended: NeMo builds its grammar files on first start (which can take a few minutes), and the cache makes every later restart nearly instant.

**Docker environment variable options ( -e ):**

| Variable Name | Description of use |
| -------- | ------- |
| LANG_TO_USE | Language to leverage for TN. Refer to the [NeMo documentation](https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/nlp/text_normalization/wfst/wfst_text_normalization.html#language-support-matrix) for supported languages. *(Default: en)* |
| INPUT_CASE | Accept either "lower_cased" or "cased" input. *(Default: cased)* |
| PUNCT_POST_PROCESS | Whether to normalize punctuation for post-processing. *(Default: True)* |
| PUNCT_PRE_PROCESS | Whether to normalize punctuation for pre-processing. *(Default: True)* |
| VERBOSE_LOGGING | More verbose output for the normalize function. *(Default: False)* |
| CACHE_DIR | Directory for NeMo's compiled grammar cache. Mount a volume here for fast restarts. *(Default: /cache)* |
| PREPROCESS_ENABLED | Master on/off switch for the [preprocessing rules](#preprocessing-rules) layer. *(Default: True)* |
| PREPROCESS_RULES_FILE | Path to your own rules file. If it doesn't exist, only the built-in defaults are used (this is normal, not an error). *(Default: /config/preprocess_rules.json)* |
| PREPROCESS_MERGE_DEFAULTS | When a user rules file is present: `True` = built-in defaults first, then your rules appended; `False` = your file fully replaces the defaults. *(Default: True)* |

**Endpoints:**

| Endpoint | Method | Description |
| -------- | ------- | ------- |
| /normalize | POST | Body: `{"text": "..."}`. Returns `{"normalized_text": "..."}`. |
| /health | GET | Returns `{"status": "ok", "lang": "en"}` once the normalizer is loaded and serving (used by the Docker healthcheck). |
| /rules | GET | Returns the active (enabled, valid) [preprocessing rules](#preprocessing-rules) as JSON so you can confirm what's live. |

## Preprocessing rules

NeMo only expands a temperature when the degree symbol is present: `72°F` becomes *"seventy two degrees Fahrenheit"*, but a bare `72F` becomes the unhelpful *"seventy two F"*. The preprocessing layer rewrites text with user-editable **regex rules** *before* it reaches NeMo. The built-in default rule inserts a `°` before a bare C/F that follows a number, so `72F` -> `72°F` -> *"seventy two degrees Fahrenheit"*.

Rules are a simple ordered list in a JSON file - **no image rebuild and no Python editing required**. Each rule is applied top-to-bottom, so ordering matters. The design scales cleanly to dozens of rules: just add more entries.

**How it works:**

- The image ships with built-in defaults (currently just the temperature rule).
- Mount your own `preprocess_rules.json` at `/config/preprocess_rules.json` to add or override rules.
- By default your rules are **appended after** the defaults (`PREPROCESS_MERGE_DEFAULTS=True`). Set it to `False` to replace the defaults entirely.
- A rule with an **invalid regex or a malformed entry is logged and skipped** - it never crashes the server or a request. A missing user file is normal and simply falls back to the defaults.
- `GET /rules` returns exactly what's live, in order.

**Rule schema:**

| Field | Required | Description |
| -------- | ------- | ------- |
| `name` | no | Human-friendly label (shown in `/rules` and logs). |
| `description` | no | What the rule does and why. For your future self. |
| `pattern` | yes | A Python regex. Remember to escape backslashes in JSON (`\\d`, `\\w`). |
| `replacement` | yes | Replacement string using Python `re.sub` backreference syntax (`\\1`, `\\2`). |
| `enabled` | no | `true`/`false`. Omit to default to `true`. |

**Mount a custom rules file:**

    docker run -dit \
    -p 5000:5000 \
    -e LANG_TO_USE=en \
    -v nemo_cache:/cache \
    -v $(pwd)/preprocess_rules.json:/config/preprocess_rules.json \
    ghcr.io/jaycollett/hass_nemo:latest

**Sample `preprocess_rules.json`** (also in the repo as [`preprocess_rules.example.json`](preprocess_rules.example.json)):

```json
{
  "rules": [
    {
      "name": "temperature-degree-symbol",
      "description": "Insert ° before a bare C/F following a number so NeMo expands it (72F -> 72°F -> 'seventy two degrees Fahrenheit').",
      "pattern": "(?<!\\w)(\\d+(?:\\.\\d+)?)\\s?([CF])(?![A-Za-z°])",
      "replacement": "\\1°\\2",
      "enabled": true
    },
    {
      "name": "abbrev-with",
      "description": "Expand the shorthand 'w/' into the spoken word 'with'.",
      "pattern": "(?<![A-Za-z])w/(?=\\s|$)",
      "replacement": "with",
      "enabled": true
    },
    {
      "name": "abbrev-without",
      "description": "Expand the shorthand 'w/o' into the spoken words 'without'.",
      "pattern": "(?<![A-Za-z])w/o(?=\\s|$)",
      "replacement": "without",
      "enabled": true
    }
  ]
}
```

> **Note on the temperature rule:** it matches *any* number immediately followed by a bare `C` or `F`, so an apartment label like `4F` in `Apt 4F` becomes `4°F`. In practice the win on real temperatures is worth this rare false positive, but if it bothers you, disable or refine the rule in your own file (it's just regex).

**Example rest command (ensure rest commands are enabled in HA):**

    normalize_text:
      url: "http://<YOUR API IP HERE>:5000/normalize"
      method: POST
      headers:
        Content-Type: application/json
      payload: '{"text": "{{ text | replace("\n", " ") | replace("\"", "\\\"") }}"}'
      timeout: 15 # Timeout in seconds; first request after a cold start can be slow

**Use the rest command in an automation (portion of an automation below):**

      # Step 2: Call the API and process the response
      - action: rest_command.normalize_text
        response_variable: normalized_response
        data:
          text: "{{ message }}"

      # Step 3: Check if the API response was successful
      - if: "{{ normalized_response['status'] == 200 }}"
        then:
          # Step 4: Log the normalized text
          - service: logbook.log
            data:
              name: "Weather Report"
              message: >
                Normalized Text: {{ normalized_response['content']['normalized_text'] }}

          # Step 5: Play the normalized text using Piper TTS
          - service: media_player.play_media
            data:
              entity_id:
                - media_player.<YOUR SPEAKER>
              media_content_id: >
                media-source://tts/tts.piper?message={{ normalized_response['content']['normalized_text'] }}"
              media_content_type: "music"
              announce: true
              extra:
                volume_level: "{{ volume_level }}"
        else:
          # Handle API error
          - service: logbook.log
            data:
              name: "Weather Report"
              message: >
                Failed to normalize text. Status: {{ normalized_response['status'] }}
