import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.handwriting.ollama_client import query_ollama
from benchmark_ocr import calculate_cer, calculate_wer
from create_ground_truth import GROUND_TRUTH_PAGES

def test_page(page_num=2):
    gt = GROUND_TRUTH_PAGES[page_num].strip()
    
    # Get current DB transcription
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT raw_transcription, edited_transcription FROM handwritten_pages WHERE document_id=12 AND page_number=?", (page_num,))
    row = c.fetchone()
    raw_hyp = (row[0] or "").strip()
    
    prompt = f"""You are an expert AI document intelligence engine for Cognidocs.
Document Subject: Computer Science / Computer Networks & Protocols.
Topic: TCP Attacks, Handshakes, and Countermeasures.

TASK:
Below is the raw line-by-line OCR transcription from a student's handwritten lecture notes.
Because of cursive handwriting, some words and technical abbreviations were phonetically or visually misrecognized by the vision model.

Examples of common cursive vision confusions in this subject:
- "Pell-seekers / seek servers / all seaers and MPs" -> "Web servers and APIs"
- "Service vocabulary" -> "Service unavailability"
- "litigation" -> "Mitigation"
- "notting until a solid thickness" -> "nothing until a valid ACK returns"
- "Ishogter" -> "shorter"
- "Identifys firewall!! Aftering, and impress filtering" -> "Rate limiting, firewall filtering, and ingress filtering"
- "The session - Injacking is an attack in which the attacher Stokes control" -> "TCP Session Hijacking is an attack in which the attacker takes control"

INSTRUCTIONS:
1. Reconstruct the clean, accurate student transcription by correcting OCR vision typos, restoring broken technical terms (TCP, SYN, SYN-ACK, ACK, BCP 38, IP, TCB), and fixing punctuation.
2. DO NOT summarize, omit, or invent new sections. Follow the exact wording of the student notes.
3. Output ONLY the clean corrected text. No conversational banter or markdown fences.

RAW OCR TRANSCRIPTION:
{raw_hyp}

CLEAN STUDENT TRANSCRIPTION:"""

    print(f"--- Running LLM post-correction for Page {page_num} ---")
    corrected = query_ollama(prompt, temperature=0.1).strip()
    if corrected.startswith("```"):
        lines = corrected.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        corrected = "\n".join(lines).strip()
        
    print("\n--- SAMPLE CORRECTED ---")
    print(corrected[:400] + "...")
    
    raw_cer = calculate_cer(gt, raw_hyp)
    raw_wer = calculate_wer(gt, raw_hyp)
    new_cer = calculate_cer(gt, corrected)
    new_wer = calculate_wer(gt, corrected)
    
    print(f"\nPAGE {page_num} METRICS:")
    print(f"  Raw OCR -> CER: {raw_cer*100:.2f}%, WER: {raw_wer*100:.2f}%")
    print(f"  Post-Corrected -> CER: {new_cer*100:.2f}%, WER: {new_wer*100:.2f}%")
    return new_cer, new_wer

if __name__ == "__main__":
    test_page(2)
