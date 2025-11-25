import json
import torch
from PIL import Image
from transformers import DonutProcessor, VisionEncoderDecoderModel

MODEL_NAME = "naver-clova-ix/donut-base-finetuned-idcard"
device = "cuda" if torch.cuda.is_available() else "cpu"
processor = DonutProcessor.from_pretrained(MODEL_NAME)
model = VisionEncoderDecoderModel.from_pretrained(MODEL_NAME).to(device)

def infer_image_to_json(image_path, max_length=1024, num_beams=1):
    image = Image.open(image_path).convert("RGB")
    inputs = processor(image, return_tensors="pt").pixel_values.to(device)
    generated_ids = model.generate(inputs, max_length=max_length, num_beams=num_beams)
    raw = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
    try:
        parsed = json.loads(raw)
        return parsed
    except Exception:
        return {"raw": raw}
