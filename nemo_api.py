from flask import Flask, request, jsonify
from nemo_text_processing.text_normalization.normalize import Normalizer
import logging
import os

app = Flask(__name__)

# Read environment vars with defaults
LANG_TO_USE = os.getenv("LANG_TO_USE", "en")
INPUT_CASE = os.getenv("INPUT_CASE", "cased")
PUNCT_POST_PROCESS = os.getenv("PUNCT_POST_PROCESS", "True")
PUNCT_PRE_PROCESS = os.getenv("PUNCT_PRE_PROCESS", "True")
VERBOSE_LOGGING = os.getenv("VERBOSE_LOGGING", "False")

# Initialize NeMo Normalizer
normalizer = Normalizer(input_case=INPUT_CASE, lang=LANG_TO_USE)

logging.basicConfig(level=logging.ERROR)

def split_into_chunks(text, word_limit=500):
    """
    Split the input text into chunks of a specified word limit.
    """
    words = text.split()
    for i in range(0, len(words), word_limit):
        yield ' '.join(words[i:i + word_limit])

@app.route('/normalize', methods=['POST'])
def normalize_text():
    try:
        # Ensure the request contains valid JSON
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        # Extract and validate the text input
        text = data.get("text", "")
        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "Invalid input: text must be a non-empty string"}), 400

        # Normalize text in chunks
        normalized_chunks = []
        for chunk in split_into_chunks(text, word_limit=500):
            normalized_chunk = normalizer.normalize(chunk, verbose=VERBOSE_LOGGING, punct_post_process=PUNCT_POST_PROCESS, punct_pre_process=PUNCT_PRE_PROCESS)
            normalized_chunks.append(normalized_chunk)

        # Concatenate the normalized chunks with proper spacing
        normalized_text = ' '.join(normalized_chunks).strip()

        return jsonify({"normalized_text": normalized_text})
    except Exception as e:
        logging.error(f"Error in normalization: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    import signal
    import sys

    def handle_shutdown(signal, frame):
        print("Shutting down server...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    app.run(host="0.0.0.0", port=5000)
