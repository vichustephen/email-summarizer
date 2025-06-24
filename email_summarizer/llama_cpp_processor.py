import os
from typing import Dict, Optional

from llama_cpp import Llama

from email_summarizer.base_processor import BaseProcessor


class LlamaCppProcessor(BaseProcessor):
    """Processor that uses a local llama.cpp model."""

    def __init__(self):
        """Initialize the LlamaCppProcessor."""
        super().__init__()
        self.model_path = os.getenv("LLAMA_MODEL_PATH")
        if not self.model_path:
            raise ValueError("LLAMA_MODEL_PATH environment variable is required")

        self.llm = Llama(
            model_path=self.model_path,
            n_ctx=int(os.getenv("LLAMA_N_CTX", 2048)),
            n_threads=int(os.getenv("LLAMA_N_THREADS", 8)),
            n_gpu_layers=int(os.getenv("LLAMA_N_GPU_LAYERS", 0)),
        )

    def _call_llm_api(self, messages: list, format: Optional[Dict] = None) -> Dict:
        """Make a call to the local Llama.cpp model."""
        # The format argument is ignored since llama.cpp doesn't have a native
        # JSON schema enforcement feature like the OpenAI API. The prompt
        # engineering is expected to guide the model to produce JSON.
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])

        response = self.llm(
            prompt,
            max_tokens=1024,
            temperature=0.25,
            top_k=40,
            top_p=0.38,
            stop=["\n"],
            echo=False,
        )

        return response
