
# hass_nemo

I built this Docker image to run the NVidia Nemo Framework. This framework has all sorts of intresting features, but I'm explicitly intrested in the TN (Text Normalization) feature which I plan to use with Home Assistant and my Piper TTS integration as part of my text pre-processings pipeline. The image is rather large but runs incredibly fast with NVidia GPU support (or without GPUs). 

  
**Docker CLI:**

    docker run --gpus all -dit \
       -p 5000:5000 \
       --ipc=host --ulimit memlock=-1 \
       --ulimit stack=67108864 \
       ghcr.io/jaycollett/hass_nemo:latest



**Example Python script in Home Assistant (python_scripts):**

    import requests
    
    # Configuration
    nemo_url = "http://<IP OF API>:<PORT>/normalize"  # Replace with your NeMo API server URL
    input_text = data.get("text", "")
    
    if not input_text:
        logger.error("No input text provided for normalization.")
        return
    
    try:
        # Call NeMo API
        response = requests.post(nemo_url, json={"text": input_text})
        response.raise_for_status()
        normalized_text = response.json().get("normalized_text", input_text)
    except Exception as e:
        logger.error(f"Error calling NeMo API: {e}")
        normalized_text = input_text  # Fallback to the original text
    
    # Return the normalized text for further use
    hass.services.call(
        "python_script",
        "set_output_variable",
        {"output_key": "normalized_text", "output_value": normalized_text},
    )

**Inside a Home Assistant Script you can add a service call to get the normalized text:**

      # Call the NeMo API to normalize the text
      - service: rest_command.normalize_text
        data:
          text: "{{ text_to_normalize }}"
        response_variable: normalized_text
        
**And then just use that as you normally would in your TTS calls (example):**

      # Play the detailed weather report using Piper TTS with announce
      - service: media_player.play_media
        data:
          entity_id:
            - media_player.YOUR_SPEAKER
          media_content_id: "media-source://tts/tts.piper?message={{ normalized_text }}"
          media_content_type: "music"
          announce: true
          extra:
            volume_level: 0.25
