import json
from pathlib import Path

with open("backend/ocr_evaluation/general_handwriting_results.json", "r") as f:
    d = json.load(f)

for s in d["samples"]:
    if s["sample_id"] == "web_p01":
        print("Sample:", s["sample_id"])
        print("Lines count:", s["lines_count"])
        print("Raw CER:", s["raw_cer"], "Rec CER:", s["recovered_cer"])
        print("Raw WER:", s["raw_wer"], "Rec WER:", s["recovered_wer"])
        print("Word Acc:", s["word_accuracy"])
        print("Technical terms:", s["technical_terms"])
        print("\nRaw transcription preview:\n", s["raw_transcription_preview"])
        print("\nRecovered transcription preview:\n", s["recovered_transcription_preview"])

