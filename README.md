
# hass_nemo

I built this Docker image to run the NVidia Nemo Framework. This framework has all sorts of intresting features, but I'm explicitly intrested in the TN (Text Normalization) feature which I plan to use with Home Assistant and my Piper TTS integration as part of my text pre-processings pipeline. The image is rather large but runs incredibly fast with NVidia GPU support (or without GPUs). 

  
**Docker CLI:**

    docker run --gpus all -dit \
       -p 5000:5000 \
       --ipc=host --ulimit memlock=-1 \
       --ulimit stack=67108864 \
       ghcr.io/jaycollett/hass_nemo:latest
