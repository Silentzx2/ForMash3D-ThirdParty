import os
import logging
from typing import *
from transformers import AutoModelForImageSegmentation
import torch
import numpy as np
from torchvision import transforms
from PIL import Image

logger = logging.getLogger(__name__)


class BiRefNet:
    def __init__(self, model_name: str = "ZhengPeng7/BiRefNet"):
        candidates = [model_name]
        # If requested model is gated/restricted (e.g. briaai/RMBG-2.0), provide ungated fallbacks
        for alt in ("ZhengPeng7/BiRefNet", "briaai/RMBG-1.4"):
            if alt not in candidates:
                candidates.append(alt)

        # Check local pretrained paths
        for local_dir in ("backend/pretrained/RMBG-1.4", "pretrained/RMBG-1.4"):
            if os.path.isdir(local_dir) and local_dir not in candidates:
                candidates.insert(1, local_dir)

        loaded_model = None
        last_err = None
        for cand in candidates:
            try:
                kwargs = {"trust_remote_code": True}
                hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
                if hf_token and hf_token.strip():
                    kwargs["token"] = hf_token.strip()
                loaded_model = AutoModelForImageSegmentation.from_pretrained(
                    cand, **kwargs
                )
                logger.info(f"Loaded background segmentation model from '{cand}'")
                break
            except Exception as e:
                last_err = e
                logger.warning(f"Could not load BiRefNet from '{cand}': {e}. Trying next candidate...")

        self.model = loaded_model
        if self.model is not None:
            self.model.eval()
        self.transform_image = transforms.Compose(
            [
                transforms.Resize((1024, 1024)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )
        self._device = "cuda" if torch.cuda.is_available() else "cpu"

    def to(self, device: str):
        self._device = device
        if self.model is not None:
            self.model.to(device)

    def cuda(self):
        self.to("cuda")

    def cpu(self):
        self.to("cpu")

    def __call__(self, image: Image.Image) -> Image.Image:
        # If input image already has an alpha channel, no background removal is needed
        if image.mode == "RGBA":
            alpha = np.array(image)[:, :, 3]
            if not np.all(alpha == 255):
                return image

        if self.model is None:
            try:
                import rembg
                return rembg.remove(image)
            except Exception:
                return image.convert("RGBA")

        device = getattr(self, "_device", "cuda" if torch.cuda.is_available() else "cpu")
        image_size = image.size
        input_images = self.transform_image(image).unsqueeze(0).to(device)
        with torch.no_grad():
            preds = self.model(input_images)[-1].sigmoid().cpu()
        pred = preds[0].squeeze()
        pred_pil = transforms.ToPILImage()(pred)
        mask = pred_pil.resize(image_size)
        image.putalpha(mask)
        return image

    