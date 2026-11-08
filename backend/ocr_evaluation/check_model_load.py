import time
import torch
from transformers import (
    ViTImageProcessorPil,
    RobertaTokenizer,
    TrOCRProcessor,
    VisionEncoderDecoderModel
)

print("Checking device...")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {device}")

print("Attempting to load TrOCR Base model and processor...")
t0 = time.time()
image_processor = ViTImageProcessorPil.from_pretrained("microsoft/trocr-base-handwritten")
tokenizer = RobertaTokenizer.from_pretrained("microsoft/trocr-base-handwritten")
processor = TrOCRProcessor(image_processor=image_processor, tokenizer=tokenizer)
print(f"Processor & Tokenizer loaded in {time.time() - t0:.2f}s")

t1 = time.time()
print("Downloading/Loading VisionEncoderDecoderModel weights (this may take 20-40s on first load)...")
model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten").to(device)
# Configure decoder start, pad, eos
model.config.decoder_start_token_id = tokenizer.cls_token_id
model.config.pad_token_id = tokenizer.pad_token_id
model.config.eos_token_id = tokenizer.sep_token_id
model.eval()
print(f"Model loaded in {time.time() - t1:.2f}s")
print(f"Total time: {time.time() - t0:.2f}s")
print("SUCCESS: TrOCR Base is fully loaded and operational on CPU!")
