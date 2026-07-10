# hass_nemo

[![GitHub release (latest by date including pre-releases)](https://img.shields.io/github/v/release/jaycollett/hass_nemo?include_prereleases)](https://github.com/jaycollett/hass_nemo/releases)
[![GitHub last commit](https://img.shields.io/github/last-commit/jaycollett/hass_nemo)](https://github.com/jaycollett/hass_nemo/commits/main)
[![GitHub issues](https://img.shields.io/github/issues-raw/jaycollett/hass_nemo)](https://github.com/jaycollett/hass_nemo/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/jaycollett/hass_nemo)](https://github.com/jaycollett/hass_nemo/pulls)
[![GitHub](https://img.shields.io/github/license/jaycollett/hass_nemo)](https://github.com/jaycollett/hass_nemo/blob/main/LICENSE)

A small Docker image that wraps the [NVIDIA NeMo text processing](https://github.com/NVIDIA/NeMo-text-processing) TN (Text Normalization) engine in a simple REST API. I use it with Home Assistant and my Piper TTS integration as part of my text pre-processing pipeline - it converts things like "$5.30", "3/14/2026", and "72F" into words that TTS engines can pronounce naturally.

NeMo's WFST text normalization runs entirely on CPU (pynini/OpenFST), so no GPU is required. Long input is automatically split on sentence boundaries (NVIDIA's recommended approach) to avoid the performance blowup NeMo hits on long single strings.

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

**Endpoints:**

| Endpoint | Method | Description |
| -------- | ------- | ------- |
| /normalize | POST | Body: `{"text": "..."}`. Returns `{"normalized_text": "..."}`. |
| /health | GET | Returns `{"status": "ok"}` once the normalizer is loaded and serving. |

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
