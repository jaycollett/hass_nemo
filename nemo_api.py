import logging
import os
import traceback

from flask import Flask, jsonify, request
from nemo_text_processing.text_normalization.normalize import Normalizer

from preprocess import build_preprocessor

app = Flask(__name__)


def env_bool(name, default):
    """Parse a boolean environment variable ("True"/"False", "1"/"0", "yes"/"no")."""
    return os.getenv(name, default).strip().lower() in ("true", "1", "yes", "on")


# Read environment vars with defaults
LANG_TO_USE = os.getenv("LANG_TO_USE", "en")
INPUT_CASE = os.getenv("INPUT_CASE", "cased")
PUNCT_POST_PROCESS = env_bool("PUNCT_POST_PROCESS", "True")
PUNCT_PRE_PROCESS = env_bool("PUNCT_PRE_PROCESS", "True")
VERBOSE_LOGGING = env_bool("VERBOSE_LOGGING", "False")
CACHE_DIR = os.getenv("CACHE_DIR") or None

# Preprocessing: user-editable regex rules applied to text before NeMo sees it.
PREPROCESS_ENABLED = env_bool("PREPROCESS_ENABLED", "True")
PREPROCESS_RULES_FILE = os.getenv("PREPROCESS_RULES_FILE", "/config/preprocess_rules.json")
PREPROCESS_MERGE_DEFAULTS = env_bool("PREPROCESS_MERGE_DEFAULTS", "True")

# NeMo's WFST normalizer degrades exponentially on long single inputs; keep
# any one normalize() call under this many words (NeMo's documented limit).
MAX_WORDS_PER_CHUNK = 500

logging.basicConfig(level=logging.INFO if VERBOSE_LOGGING else logging.WARNING)
logger = logging.getLogger("nemo_api")

if INPUT_CASE not in ("cased", "lower_cased"):
    logger.warning("INPUT_CASE=%r is not 'cased' or 'lower_cased'; NeMo may reject it", INPUT_CASE)

preprocessor = build_preprocessor(
    enabled=PREPROCESS_ENABLED,
    user_file=PREPROCESS_RULES_FILE,
    merge_defaults=PREPROCESS_MERGE_DEFAULTS,
)

logger.info("Loading NeMo Normalizer (lang=%s, input_case=%s, cache_dir=%s)...", LANG_TO_USE, INPUT_CASE, CACHE_DIR)
normalizer = Normalizer(input_case=INPUT_CASE, lang=LANG_TO_USE, cache_dir=CACHE_DIR)
logger.info("Normalizer ready")


def preprocess(text):
    """Apply the configured preprocessing rules before normalization.

    No-op passthrough when PREPROCESS_ENABLED is false or no rules are active.
    """
    return preprocessor.apply(text)


def split_long_sentence(sentence, word_limit=MAX_WORDS_PER_CHUNK):
    """Fallback word-based split for a single sentence that exceeds the word limit."""
    words = sentence.split()
    for i in range(0, len(words), word_limit):
        yield " ".join(words[i:i + word_limit])


def split_for_normalization(text):
    """
    Split text into normalizer-safe pieces: sentence boundaries first (NeMo's
    recommended approach for long input), then a word-limit fallback for any
    single sentence that is still too long.
    """
    for sentence in normalizer.split_text_into_sentences(text):
        if len(sentence.split()) <= MAX_WORDS_PER_CHUNK:
            yield sentence
        else:
            yield from split_long_sentence(sentence)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "lang": LANG_TO_USE})


@app.route("/rules", methods=["GET"])
def rules():
    """Return the active (enabled, successfully-compiled) preprocessing rules."""
    return jsonify({
        "preprocess_enabled": PREPROCESS_ENABLED,
        "rules": preprocessor.active_rules(),
    })


@app.route("/normalize", methods=["POST"])
def normalize_text():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        text = data.get("text", "")
        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "Invalid input: text must be a non-empty string"}), 400

        text = preprocess(text)

        normalized_chunks = []
        for chunk in split_for_normalization(text):
            normalized_chunks.append(
                normalizer.normalize(
                    chunk,
                    verbose=VERBOSE_LOGGING,
                    punct_post_process=PUNCT_POST_PROCESS,
                    punct_pre_process=PUNCT_PRE_PROCESS,
                )
            )

        normalized_text = " ".join(normalized_chunks).strip()

        return jsonify({"normalized_text": normalized_text})
    except Exception as e:
        logger.error("Error in normalization: %s\n%s", e, traceback.format_exc())
        return jsonify({"error": f"Normalization failed: {type(e).__name__}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
