

  
# hass_nemo
[![s.io/github/v/GitHub release (latest by date including pre-releases)](https://img.shields.io/github/v/release/jaycollett/hass_nemo?include_prereleases)](https://img.shields.io/github/v/release/jaycollett/hass_nemo?include_prereleases)
[![GitHub last commit](https://img.shields.io/github/last-commit/jaycollett/hass_nemo)](https://img.shields.io/github/last-commit/jaycollett/hass_nemo)
[![GitHub issues](https://img.shields.io/github/issues-raw/jaycollett/hass_nemo)](https://img.shields.io/github/issues-raw/jaycollett/hass_nemo)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/jaycollett/hass_nemo)](https://img.shields.io/github/issues-pr/jaycollett/hass_nemo)
[![GitHub](https://img.shields.io/github/license/jaycollett/hass_nemo)](https://img.shields.io/github/license/jaycollett/hass_nemo)

  

I built this Docker image to run the NVidia NeMo Framework. This framework has all sorts of interesting features, but I'm explicitly interested in the TN (Text Normalization) feature, which I plan to use with Home Assistant and my Piper TTS integration as part of my text pre-processing pipeline. The image is large but runs incredibly fast with NVidia GPU support (or without GPUs).

  

**Docker CLI:**

    docker run --gpus all -dit \
    -p 5000:5000 \
    -e LANG_TO_USE=it \
    --ipc=host --ulimit memlock=-1 \
    --ulimit stack=67108864 \
    ghcr.io/jaycollett/hass_nemo:latest


**Docker environment varible options ( -e ):**
| Varible Name    | Description of use |
| -------- | ------- |
| LANG_TO_USE  | Language to leverage for TN. Refer to the [Nemo documentation](https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/nlp/text_normalization/wfst/wfst_text_normalization.html#language-support-matrix) for supported langauges. *(Default: en)*  |
| INPUT_CASE | Accept either "lower_cased" or "cased" input. *(Default: cased)*     |
| PUNCT_POST_PROCESS    | Whether to normalize punctuation for post-processing. *(Default: True)*    |
| PUNCT_PRE_PROCESS    | Whether to normalize punctuation for pre-processing. *(Default: True)*    |
| VERBOSE_LOGGING    | More verbose output for normalize function. *(Default: False)*    |

**Example rest command (ensure rest commands are enabled in HA):**

    normalize_text:
      url: "http://<YOUR API IP HERE>:5000/normalize"
      method: POST
      headers:
        Content-Type: application/json
      payload: '{"text": "{{ text | replace("\n", " ") | replace("\"", "\\\"") }}"}'
      timeout: 5 # Timeout in seconds

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
                - media_player.<YOURSPEKAER>
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
