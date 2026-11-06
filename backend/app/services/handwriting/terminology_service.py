import logging
import re
from typing import Dict, List, Set, Any, Optional

logger = logging.getLogger(__name__)

# Core academic discipline vocabularies (acronyms + multi-word expressions)
DOMAIN_VOCABULARIES: Dict[str, Dict[str, Any]] = {
    "Computer Science & Networking": {
        "acronyms": {
            "TCP", "UDP", "IP", "SYN", "ACK", "RST", "FIN", "TCB", "DoS", "DDoS",
            "BGP", "SSH", "TLS", "SSL", "IPSec", "ICMP", "ARP", "DNS", "HTTP", "HTTPS",
            "BCP 38", "RFC 5961", "API", "CPU", "MAC", "LAN", "WAN", "NAT", "MTU"
        },
        "phrases": [
            "TCP Attacks", "three-way handshake", "TCP three-way handshake", "TCP three-way",
            "TCP handshake", "SYN flood", "ACK flood", "TCP SYN Flood", "TCP ACK Flood",
            "TCP RST attack", "TCP Session Hijacking", "session hijacking",
            "sequence number", "sequence numbers", "acknowledgement number",
            "acknowledgement numbers", "backlog queue", "SYN cookies", "spoofed source IP",
            "spoofed IP", "spoofed address", "stateful firewall", "stateful firewalls",
            "firewall filtering", "load balancer", "half-open attack",
            "Transmission Control Block", "Transmission Control Block (TCB)", "ACK storm",
            "RST packet", "connection-oriented", "ingress filtering", "SYN_RECEIVED",
            "packet sniffing", "packet injection", "man-in-the-middle",
            "denial-of-service", "distributed denial-of-service",
            "initial sequence numbers", "session hygiene", "unsolicited packets",
            "bandwidth saturation", "per-packet state checks"
        ],
        "context_colocations": {
            "flood": ["SYN", "ACK", "TCP SYN", "TCP ACK"],
            "hijacking": ["TCP", "session", "TCP Session"],
            "handshake": ["three-way", "TCP", "SYN", "SYN-ACK", "ACK"],
            "three-way": ["TCP"],
            "connection-oriented": ["TCP"],
            "queue": ["backlog"],
            "cookies": ["SYN"],
            "attacks": ["TCP", "ICMP", "DoS", "DDoS", "network"],
            "attack": ["TCP SYN", "TCP RST", "TCP ACK", "session hijacking", "half-open", "denial-of-service"],
            "storm": ["ACK"],
            "packet": ["SYN", "ACK", "RST", "TCP", "spoofed"],
            "packets": ["SYN", "ACK", "RST", "TCP", "spoofed"],
            "spoofing": ["IP", "reset", "TCP"],
            "block": ["Transmission Control", "TCB"],
            "syn-ack": ["ACK"],
            "syn": ["SYN-ACK", "ACK"],
            "filtering": ["ingress", "firewall", "BCP 38"],
            "validation": ["RST", "TCP RST", "RFC 5961"],
            "stricter": ["RST"],
            "challenge": ["ACK"],
            "entry": ["TCB"],
            "backlog": ["queue", "TCB"],
            "rfc": ["5961", "RFC 5961"],
            "compliance": ["RFC 5961"],
            "bcp": ["38", "BCP 38"],
            "denial-of-service": ["DoS", "DDoS"],
            "flag": ["ACK", "SYN", "RST", "FIN"],
            "replies": ["RST", "ACK", "SYN-ACK"],
            "stream": ["ACK", "SYN", "packets"],
            "unsolicited": ["ACK", "packets"]
        }
    },
    "Artificial Intelligence & Data Science": {
        "acronyms": {
            "AI", "ML", "DL", "NLP", "CNN", "RNN", "LSTM", "BERT", "GPT", "LLM",
            "PCA", "SVM", "SGD", "MSE", "MAE", "ROC", "AUC", "GPU", "TPU"
        },
        "phrases": [
            "neural network", "gradient descent", "backpropagation", "loss function",
            "learning rate", "overfitting", "regularization", "cross entropy",
            "transformer model", "self-attention", "feature vector", "decision tree"
        ],
        "context_colocations": {
            "descent": ["gradient", "stochastic"],
            "network": ["neural", "convolutional", "recurrent"],
            "attention": ["self", "multi-head"]
        }
    },
    "Mathematics & Statistics": {
        "acronyms": {
            "ODE", "PDE", "CDF", "PDF", "IQR", "CI", "ANOVA", "SVD"
        },
        "phrases": [
            "standard deviation", "normal distribution", "hypothesis testing",
            "null hypothesis", "eigenvalues and eigenvectors", "partial derivative",
            "differential equation", "linear transformation", "central limit theorem"
        ],
        "context_colocations": {
            "distribution": ["normal", "probability", "poisson", "gaussian"],
            "hypothesis": ["null", "alternative"],
            "derivative": ["partial", "second"]
        }
    }
}


def get_subject_vocabulary(subject: Optional[str]) -> Dict[str, Any]:
    """Retrieve the domain terminology dictionary for a given subject."""
    if not subject:
        subject = "Computer Science & Networking"

    for domain_key, vocab in DOMAIN_VOCABULARIES.items():
        if domain_key.lower() in subject.lower() or subject.lower() in domain_key.lower():
            return vocab

    # Default fallback to CS/Networking if general or unspecified
    return DOMAIN_VOCABULARIES["Computer Science & Networking"]


def extract_document_terminology(
    pages_text: List[str],
    subject: Optional[str] = None
) -> Dict[str, Any]:
    """
    Construct a document-specific terminology index combining:
    1. Standard domain vocabulary for the detected subject.
    2. Acronyms and technical terms verified with high consistency across the document.
    3. Repeated capitalized technical n-grams found in the document.
    """
    base_vocab = get_subject_vocabulary(subject)
    acronyms: Set[str] = set(base_vocab.get("acronyms", set()))
    phrases: List[str] = list(base_vocab.get("phrases", []))
    colocations: Dict[str, List[str]] = dict(base_vocab.get("context_colocations", {}))

    combined_text = "\n".join(pages_text)
    
    # 1. Scan for uppercase tokens (2-5 letters) appearing in the document
    found_caps = re.findall(r'\b[A-Z]{2,6}\b', combined_text)
    token_freq: Dict[str, int] = {}
    for token in found_caps:
        token_freq[token] = token_freq.get(token, 0) + 1

    # Tokens appearing frequently or in base vocabulary are recorded as verified document terms
    verified_doc_terms = {t for t, count in token_freq.items() if count >= 2 or t in acronyms}

    return {
        "acronyms": acronyms,
        "verified_document_terms": verified_doc_terms,
        "token_frequencies": token_freq,
        "phrases": phrases,
        "colocations": colocations,
        "subject": subject or "Computer Science & Networking"
    }
