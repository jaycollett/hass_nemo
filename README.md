
  

# hass_nemo

  

I built this Docker image to run the NVidia Nemo Framework. This framework has all sorts of intresting features, but I'm explicitly intrested in the TN (Text Normalization) feature which I plan to use with Home Assistant and my Piper TTS integration as part of my text pre-processings pipeline. The image is rather large but runs incredibly fast with NVidia GPU support (or without GPUs).

  

**Docker CLI:**

    docker run --gpus all -dit \
    -p 5000:5000 \
    --ipc=host --ulimit memlock=-1 \
    --ulimit stack=67108864 \
    ghcr.io/jaycollett/hass_nemo:latest

**Example rest command (ensure rest commands are enabled in HA):**

    normalize_text:
      url: "http://192.168.0.210:5000/normalize"
      method: POST
      headers:
        Content-Type: application/json
      payload: '{"text": "{{ text | replace("\n", " ") | replace("\"", "\\\"") }}"}'

**Use the rest command in a script (portion of a script below):**

      # Step 2: Call the API and process response
      - action: rest_command.normalize_text
        response_variable: normalized_response
        data:
          text: "{{ message }}"
    
      # Step 3: Check if API response was successful
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
