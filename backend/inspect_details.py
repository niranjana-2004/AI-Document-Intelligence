import os
import json
import re

json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluate_results.json")
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Overall Metrics:")
print(f"  - Total Pages: {data['overall']['total_pages']}")
print(f"  - Total Lines Detected: {data['overall']['total_lines']}")
print(f"  - Avg Confidence: {data['overall']['avg_conf']}%")
print(f"  - Min Confidence: {data['overall']['min_conf']}%")
print(f"  - Max Confidence: {data['overall']['max_conf']}%")
print(f"  - Raw CER: {data['overall']['raw_cer']*100:.2f}% | Raw WER: {data['overall']['raw_wer']*100:.2f}%")
print(f"  - Edited CER: {data['overall']['edited_cer']*100:.2f}% | Edited WER: {data['overall']['edited_wer']*100:.2f}%\n")

terms_to_check = [
    "TCP",
    "SYN",
    "ACK",
    "SYN-ACK",
    "RST",
    "TCP handshake",
    "three-way handshake",
    "SYN flood",
    "TCP session hijacking",
    "TCP RST attack",
    "TCP ACK flood",
    "DoS",
    "DDoS",
    "Transmission Control Block",
    "TCB",
    "sequence number",
    "acknowledgement number",
    "spoofed source IP",
    "backlog queue",
    "SYN cookies",
    "RFC 5961"
]

all_raw_text = "\n".join([p["raw_text"] for p in data["pages"]])
all_edited_text = "\n".join([p["edited_text"] for p in data["pages"]])

print("================ TECHNICAL TERMINOLOGY EVALUATION ================")
for term in terms_to_check:
    # Check in raw OCR
    found_raw = bool(re.search(r'\b' + re.escape(term) + r'\b', all_raw_text, re.IGNORECASE))
    found_edited = bool(re.search(r'\b' + re.escape(term) + r'\b', all_edited_text, re.IGNORECASE))
    
    # Find occurrences or close misreadings in raw lines
    matches = []
    for p in data["pages"]:
        for l in p["raw_lines"]:
            if any(part.lower() in l.lower() for part in term.split() if len(part) > 2):
                matches.append((p["page_number"], l))
    
    print(f"Term: '{term}'")
    print(f"  - In Raw OCR: {found_raw} | In Edited: {found_edited}")
    if matches:
        print(f"  - Sample appearances/contexts ({len(matches)} found):")
        for pnum, line in matches[:3]:
            print(f"     [Page {pnum}] {line}")
    else:
        print("  - NO direct matches found in line OCR!")
    print()

print("================ FALSE CONTENT / HALLUCINATION CHECK ================")
hallucination_keywords = ["HelpLearn", "Community portal", "Municipalities", "political legislative", "Wikipedia", "navigation"]
found_hallucinations = []
for kw in hallucination_keywords:
    for p in data["pages"]:
        for l in p["raw_lines"]:
            if kw.lower() in l.lower():
                found_hallucinations.append((p["page_number"], kw, l))

if found_hallucinations:
    print(f"FOUND {len(found_hallucinations)} HALLUCINATIONS:")
    for pnum, kw, l in found_hallucinations:
        print(f"  Page {pnum} (match '{kw}'): {l}")
else:
    print("ZERO hallucinated boilerplate/web text found across all 7 pages! Clean OCR output.")

print("\n================ PAGE BY PAGE BREAKDOWN ================")
for p in data["pages"]:
    print(f"--- PAGE {p['page_number']} ---")
    print(f"  - Lines: {p['lines_detected']} (Empty/failed: {p['empty_failed_lines']})")
    print(f"  - Confidence: Avg={p['avg_line_conf']}%, Min={p['min_line_conf']}%, Max={p['max_line_conf']}%")
    print(f"  - Raw CER: {p['raw_cer']*100:.2f}% | WER: {p['raw_wer']*100:.2f}% (Edits: {p['raw_c_dist']}/{p['gt_chars']} chars, {p['raw_w_dist']}/{p['gt_words']} words)")
    print(f"  - Edited CER: {p['edited_cer']*100:.2f}% | WER: {p['edited_wer']*100:.2f}%")
    blocks = p["structured_layout"].get("blocks", [])
    b_types = [b.get("type") for b in blocks]
    print(f"  - Structure Blocks ({len(blocks)}): {b_types}")
    print(f"  - First 3 raw lines:")
    for l in p["raw_lines"][:3]:
        print(f"     * {l}")
    print()
