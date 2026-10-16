import sys
import torch
import gradio as gr
from PIL import Image
import numpy as np
from rembg import remove
from app.utils import change_rgba_bg, rgba_to_rgb
from app.custom_models.utils import load_pipeline
from scripts.all_typing import *
from scripts.utils import session, simple_preprocess

trainer = None
pipeline = None


def get_pipeline():
    global trainer, pipeline
    if trainer is not None and pipeline is not None:
        return trainer, pipeline

    root = Path(__file__).resolve().parent.parent.parent
    training_config = str(root / "app" / "custom_models" / "image2mvimage.yaml")

    ckpt_candidates = [
        root / "ckpt" / "img2mvimg" / "unet_state_dict.pth",
        root / "ckpt" / "img2mvimg" / "unet" / "diffusion_pytorch_model.safetensors",
        root.parent.parent / "pretrained" / "Unique3D" / "ckpt" / "img2mvimg" / "unet" / "diffusion_pytorch_model.safetensors",
        root.parent.parent / "pretrained" / "Unique3D" / "ckpt" / "img2mvimg" / "unet_state_dict.pth",
    ]
    checkpoint_path = None
    for cand in ckpt_candidates:
        if cand.exists():
            checkpoint_path = str(cand)
            break
    if checkpoint_path is None:
        checkpoint_path = str(root / "ckpt" / "img2mvimg" / "unet_state_dict.pth")

    trainer, pipeline = load_pipeline(training_config, checkpoint_path)
    return trainer, pipeline


def predict(img_list: List[Image.Image], guidance_scale=2., **kwargs):
    tr, pipe = get_pipeline()
    if torch.cuda.is_available():
        if hasattr(pipe, "device") and pipe.device.type != "cuda":
            pipe.to("cuda")
        if hasattr(pipe, "enable_attention_slicing"):
            try:
                pipe.enable_attention_slicing()
            except Exception:
                pass
        if hasattr(pipe, "enable_vae_slicing"):
            try:
                pipe.enable_vae_slicing()
            except Exception:
                pass

    if isinstance(img_list, Image.Image):
        img_list = [img_list]
    img_list = [rgba_to_rgb(i) if i.mode == 'RGBA' else i for i in img_list]
    ret = []
    for img in img_list:
        images = tr.pipeline_forward(
            pipeline=pipe,
            image=img,
            guidance_scale=guidance_scale, 
            **kwargs
        ).images
        ret.extend(images)
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return ret


def run_mvprediction(input_image: Image.Image, remove_bg=True, guidance_scale=1.5, seed=1145):
    if input_image.mode == 'RGB' or np.array(input_image)[..., -1].mean() == 255.:
        # still do remove using rembg, since simple_preprocess requires RGBA image
        print("RGB image not RGBA! still remove bg!")
        remove_bg = True

    if remove_bg:
        input_image = remove(input_image, session=session)

    # make front_pil RGBA with white bg
    input_image = change_rgba_bg(input_image, "white")
    single_image = simple_preprocess(input_image)

    generator = torch.Generator(device="cuda").manual_seed(int(seed)) if seed >= 0 else None

    rgb_pils = predict(
        single_image,
        generator=generator,
        guidance_scale=guidance_scale,
        width=256,
        height=256,
        num_inference_steps=30,
    )

    return rgb_pils, single_image
