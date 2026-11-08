import sqlite3
import json

conn = sqlite3.connect('backend/documents.db')
c = conn.cursor()
for row in c.execute('SELECT document_id, page_number, confidence_score, raw_transcription, edited_transcription, ocr_metadata FROM handwritten_pages'):
    doc_id, p_num, conf, raw, ed, meta_str = row
    meta = json.loads(meta_str) if meta_str else {}
    print(f"Doc {doc_id} Page {p_num}: conf={conf}")
    print(f"  RAW (len={len(raw or '')}): {repr((raw or '')[:140])}")
    print(f"  EDITED (len={len(ed or '')}): {repr((ed or '')[:140])}")
    print(f"  Corrs: {len(meta.get('technical_corrections', []))}, Tokens: {len(meta.get('tokens', []))}, Lines: {len(meta.get('lines', []))}")

