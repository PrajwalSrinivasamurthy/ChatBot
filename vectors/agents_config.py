from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(__file__)

AGENTS: dict[str, dict] = {
    "ttu-online": {
        "collection": "ttu_kb",
        "display_name": "TTU Online",
        "description": "Texas Tech University Online programs, admissions, and courses.",
        "kb_folder": os.path.join(BASE_DIR, "kb", "ttu_online"),
        "kb_url": os.getenv("KB_URL_TTU_ONLINE") or os.getenv("KB_URL", ""),
        "guardrails": (
            "You are an assistant specifically for Texas Tech University Online (TTU Online) programs. "
            "Only answer questions related to TTU Online"
            "If the question is about K-12, competitor universities, general academic advice unrelated to TTU, "
            "medical, legal, or financial advice — politely say that is outside your scope and offer to "
            "connect them with the TTU Online team."
        ),
    },
    "k12": {
        "collection": "k12",
        "display_name": "K-12",
        "description": "K-12 education programs and resources at Texas Tech.",
        "kb_folder": os.path.join(BASE_DIR, "kb", "k12"),
        "kb_url": os.getenv("KB_URL_K12", ""),
        "guardrails": (
            "You are an assistant specifically for the Texas Tech University K-12 program (TTU K-12). "
            "Only answer questions related to TTU K-12 "
            "If the question is about topics unrelated to K-12 — politely say that is outside your scope and suggest they contact "
            "the TTU K-12 support team."
        ),
    },
}
