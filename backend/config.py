import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

@dataclass
class Config:
    """Configuration settings for the RAG system"""
    # OpenRouter API settings
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Model configuration with auto-fallback support
    DEFAULT_MODEL: str = "deepseek/deepseek-chat-v3.1:free"

    # Priority-ordered list of fallback models
    FALLBACK_MODELS: list = None

    # Available free models with metadata
    AVAILABLE_MODELS: dict = None

    # Embedding model settings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Document processing settings
    CHUNK_SIZE: int = 800       # Size of text chunks for vector storage
    CHUNK_OVERLAP: int = 100     # Characters to overlap between chunks
    MAX_RESULTS: int = 5         # Maximum search results to return
    MAX_HISTORY: int = 2         # Number of conversation messages to remember

    # Database paths
    CHROMA_PATH: str = "./chroma_db"  # ChromaDB storage location

    def __post_init__(self):
        """Initialize model lists after dataclass creation"""
        if self.FALLBACK_MODELS is None:
            self.FALLBACK_MODELS = [
                "deepseek/deepseek-chat-v3.1:free",
                "qwen/qwen3-coder:free",
                "google/gemini-2.0-flash-exp:free",
                "meta-llama/llama-3.3-70b-instruct:free",
                "deepseek/deepseek-r1-0528:free",
                "mistralai/mistral-small-3.2-24b-instruct:free",
                "qwen/qwen-2.5-72b-instruct:free",
            ]

        if self.AVAILABLE_MODELS is None:
            self.AVAILABLE_MODELS = {
                "deepseek/deepseek-chat-v3.1:free": {
                    "name": "DeepSeek V3.1",
                    "context": 163800,
                    "description": "Fast and capable general-purpose model"
                },
                "qwen/qwen3-coder:free": {
                    "name": "Qwen3 Coder 480B",
                    "context": 262000,
                    "description": "Optimized for coding tasks"
                },
                "google/gemini-2.0-flash-exp:free": {
                    "name": "Gemini 2.0 Flash",
                    "context": 1048576,
                    "description": "Largest context window (1M tokens)"
                },
                "meta-llama/llama-3.3-70b-instruct:free": {
                    "name": "Llama 3.3 70B",
                    "context": 131072,
                    "description": "Solid general-purpose model"
                },
                "deepseek/deepseek-r1-0528:free": {
                    "name": "DeepSeek R1",
                    "context": 163840,
                    "description": "Reasoning-focused model"
                },
                "mistralai/mistral-small-3.2-24b-instruct:free": {
                    "name": "Mistral Small 3.2 24B",
                    "context": 131072,
                    "description": "Efficient and fast"
                },
                "qwen/qwen-2.5-72b-instruct:free": {
                    "name": "Qwen 2.5 72B",
                    "context": 32768,
                    "description": "Strong instruction following"
                },
                "nvidia/nemotron-nano-12b-v2-vl:free": {
                    "name": "NVIDIA Nemotron Nano 12B VL",
                    "context": 128000,
                    "description": "Vision + language model"
                },
                "minimax/minimax-m2:free": {
                    "name": "MiniMax M2",
                    "context": 196608,
                    "description": "Balanced performance"
                },
                "openrouter/polaris-alpha": {
                    "name": "Polaris Alpha",
                    "context": 256000,
                    "description": "Large context model"
                }
            }

config = Config()


