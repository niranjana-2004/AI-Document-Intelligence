from app.services.handwriting.pdf_rasterizer import rasterize_document_to_images
from app.services.handwriting.image_preprocessor import (
    preprocess_handwritten_image,
    calculate_deskew_angle,
    deskew_image,
    remove_shadows_and_normalize,
    enhance_contrast_clahe,
    denoise_image,
    generate_page_stages
)
from app.services.handwriting.line_segmenter import segment_page_into_lines, LineCrop
from app.services.handwriting.ocr_service import get_ocr_engine, recognize_line_image
from app.services.handwriting.transcription_pipeline import transcribe_page_image
from app.services.handwriting.handwritten_source_service import (
    get_document_transcription_source,
    sync_handwritten_chunks_and_embeddings
)
from app.services.handwriting.handwritten_summary_service import (
    generate_handwritten_summary,
    get_handwritten_summary
)
from app.services.handwriting.handwritten_concept_service import (
    generate_handwritten_concepts,
    list_handwritten_concepts,
    toggle_concept_bookmark
)
from app.services.handwriting.handwritten_quiz_service import (
    generate_handwritten_quiz,
    list_handwritten_quizzes,
    submit_quiz_answers,
    get_document_topics
)
from app.services.handwriting.handwritten_flashcard_service import (
    generate_handwritten_flashcards,
    list_handwritten_flashcards,
    update_card_status,
    reset_deck_status
)
from app.services.handwriting.handwritten_chat_service import (
    ask_handwritten_notes,
    get_chat_history,
    clear_chat_history
)

__all__ = [
    "rasterize_document_to_images",
    "preprocess_handwritten_image",
    "calculate_deskew_angle",
    "deskew_image",
    "remove_shadows_and_normalize",
    "enhance_contrast_clahe",
    "denoise_image",
    "generate_page_stages",
    "segment_page_into_lines",
    "LineCrop",
    "get_ocr_engine",
    "recognize_line_image",
    "transcribe_page_image",
    "get_document_transcription_source",
    "sync_handwritten_chunks_and_embeddings",
    "generate_handwritten_summary",
    "get_handwritten_summary",
    "generate_handwritten_concepts",
    "list_handwritten_concepts",
    "toggle_concept_bookmark",
    "generate_handwritten_quiz",
    "list_handwritten_quizzes",
    "submit_quiz_answers",
    "get_document_topics",
    "generate_handwritten_flashcards",
    "list_handwritten_flashcards",
    "update_card_status",
    "reset_deck_status",
    "ask_handwritten_notes",
    "get_chat_history",
    "clear_chat_history"
]
