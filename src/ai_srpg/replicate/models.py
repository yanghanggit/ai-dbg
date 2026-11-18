"""Replicate 可用的图像模型引用表。

只保存「业务名 → Replicate model_ref」映射；不提供默认模型，调用方必须显式
选择。模型支持的尺寸与限制见 docs/wiki/image-generation.md。
"""

from typing import Dict, Final

IMAGE_MODELS: Final[Dict[str, Dict[str, str]]] = {
    "ideogram-v3-turbo": {
        "model_ref": "ideogram-ai/ideogram-v3-turbo:32a9584617b239dd119c773c8c18298d310068863d26499e6199538e9c29a586",
    },
    "stable-diffusion-3.5-large": {
        "model_ref": "stability-ai/stable-diffusion-3.5-large",
    },  # 由于 SD 3.5 不支持中文!
    "flux-schnell": {
        "model_ref": "black-forest-labs/flux-schnell",
    },  # 1-4步极速生成，Apache 2.0开源，成本极低($0.003/张)
    "nano-banana": {
        "model_ref": "google/nano-banana",
    },  # Google Gemini 2.5 图像生成和编辑模型，$0.039/张
    "nano-banana-pro": {
        "model_ref": "google/nano-banana-pro",
    },  # Google Gemini 3 Pro 图像生成，支持4K，$0.15-0.30/张
}


__all__ = ["IMAGE_MODELS"]
