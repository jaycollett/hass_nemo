from flask import Flask, request, jsonify
from nemo_text_processing.text_normalization.normalize import Normalizer

app = Flask(__name__)

# Initialize NeMo Normalizer
normalizer = Normalizer(input_case='cased', lang='en')

@app.route('/normalize', methods=['POST'])
def normalize_text():
    try:
        data = request.json
        text = data.get("text", "")
        if not text:
            return jsonify({"error": "No text provided"}), 400
        
        # Normalize the text
        normalized_text = normalizer.normalize(text, verbose=False)
        return jsonify({"normalized_text": normalized_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
