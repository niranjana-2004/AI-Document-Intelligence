import logging
from pathlib import Path
from typing import List, Dict, Any
from PIL import Image

logger = logging.getLogger(__name__)


def rasterize_document_to_images(
    file_path: Path,
    output_dir: Path,
    dpi: int = 200
) -> List[Dict[str, Any]]:
    """
    Rasterize a multi-page PDF or standard image into high-resolution PNG page images.

    Args:
        file_path: Path to the input PDF or image file.
        output_dir: Directory where rasterized page images will be saved.
        dpi: Target resolution for PDF rendering (default 200 DPI for optimal OCR balance).

    Returns:
        List of dicts: [
            {
                "page_number": int,
                "image_path": str,
                "width": int,
                "height": int
            }, ...
        ]
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = file_path.suffix.lower()
    page_records: List[Dict[str, Any]] = []

    if suffix == ".pdf":
        import pypdfium2 as pdfium

        try:
            pdf = pdfium.PdfDocument(str(file_path))
            total_pages = len(pdf)

            if total_pages == 0:
                raise ValueError("PDF document contains no pages.")

            # Calculate render scale: standard PDF point is 1/72 inch
            scale = dpi / 72.0

            for idx in range(total_pages):
                page_num = idx + 1
                page = pdf[idx]
                # Render to PIL Image
                pil_image = page.render(scale=scale).to_pil()

                # Ensure RGB mode
                if pil_image.mode != "RGB":
                    pil_image = pil_image.convert("RGB")

                target_filename = f"page_{page_num:03d}.png"
                target_path = output_dir / target_filename
                pil_image.save(target_path, format="PNG", optimize=True)

                page_records.append({
                    "page_number": page_num,
                    "image_path": str(target_path),
                    "width": pil_image.width,
                    "height": pil_image.height
                })

            logger.info(f"Successfully rasterized {total_pages} PDF pages to {output_dir}")

        except Exception as error:
            logger.error(f"Failed to rasterize PDF '{file_path}': {error}")
            raise ValueError(f"Could not rasterize PDF: {error}") from error

    elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}:
        try:
            with Image.open(str(file_path)) as img:
                if img.mode != "RGB":
                    img = img.convert("RGB")

                target_filename = "page_001.png"
                target_path = output_dir / target_filename
                img.save(target_path, format="PNG", optimize=True)

                page_records.append({
                    "page_number": 1,
                    "image_path": str(target_path),
                    "width": img.width,
                    "height": img.height
                })

            logger.info(f"Saved single page image from {file_path} to {target_path}")

        except Exception as error:
            logger.error(f"Failed to load image file '{file_path}': {error}")
            raise ValueError(f"Could not load image: {error}") from error

    else:
        raise ValueError(f"Unsupported file format for handwritten processing: {suffix}")

    return page_records

