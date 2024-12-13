from typing import Dict, List, Optional
from pathlib import Path
import os
from huggingface_hub import snapshot_download
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ModelInfo:
    model_id: str
    is_downloaded: bool
    local_path: Optional[str] = None
    size_gb: Optional[float] = None
    last_used: Optional[datetime] = None


class ModelManager:
    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize ModelManager with optional custom cache directory"""
        self.cache_dir = cache_dir or os.getenv(
            'HF_HOME',
            Path.home() / '.cache' / 'huggingface'
        )
        self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Track registered and downloaded models
        self.registered_models: Dict[str, ModelInfo] = {}

        # Register some default models
        self._register_default_models()

        # Scan cache directory for existing models
        self._scan_cache()

    def _register_default_models(self):
        """Register default supported models"""
        defaults = [
            "mistralai/Mistral-7B-Instruct-v0.3",
            "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            "meta-llama/Llama-2-7b-chat-hf",
            "gpt2"
        ]
        for model_id in defaults:
            self.register_model(model_id)

    def _scan_cache(self):
        """Scan cache directory for downloaded models"""
        cache_path = self.cache_dir
        if not self.cache_dir.exists():
            return

        for model_dir in cache_path.iterdir():
            if model_dir.is_dir():
                if model_dir.name.startswith("models--"):
                    model_id = model_dir.name
                    model_id.removeprefix("models--")

                    size = self._calculate_model_size(model_dir)

                    self.registered_models[model_id] = ModelInfo(
                        model_id=model_id,
                        is_downloaded=True,
                        local_path=str(model_dir),
                        size_gb=size,
                        last_used=datetime.fromtimestamp(model_dir.stat().st_mtime)
                    )

    def _calculate_model_size(self, model_path: Path) -> float:
        """Calculate model size in GB"""
        total_size = sum(
            f.stat().st_size for f in model_path.rglob('*') if f.is_file())
        return total_size / (1024 * 1024 * 1024)

    def register_model(self, model_id: str):
        """Register a new model"""
        if model_id not in self.registered_models:
            model_path = self.cache_dir / 'hub' / model_id
            is_downloaded = model_path.exists()

            self.registered_models[model_id] = ModelInfo(
                model_id=model_id,
                is_downloaded=is_downloaded,
                local_path=str(model_path) if is_downloaded else None,
                size_gb=self._calculate_model_size(
                    model_path) if is_downloaded else None
            )

    def download_model(self, model_id: str, force: bool = False) -> str:
        """Download a model and return its local path"""
        if model_id not in self.registered_models:
            self.register_model(model_id)

        model_info = self.registered_models[model_id]

        if not model_info.is_downloaded or force:
            print(f"Downloading model {model_id}...")
            local_dir = snapshot_download(
                repo_id=model_id,
                cache_dir=self.cache_dir,
                force_download=force,
                local_dir_use_symlinks=False
            )

            # Update model info
            model_info.is_downloaded = True
            model_info.local_path = local_dir
            model_info.size_gb = self._calculate_model_size(Path(local_dir))
            model_info.last_used = datetime.now()

            print("Registering downloaded model, ", model_id)
            self.register_model(self, model_id)

            return local_dir

        return model_info.local_path

    def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """Get information about a registered model"""
        return self.registered_models.get(model_id)

    def list_registered_models(self) -> List[ModelInfo]:
        """List all registered models"""
        return list(self.registered_models.values())

    def list_downloaded_models(self) -> List[ModelInfo]:
        """List only downloaded models"""
        return [
            info
            for info in self.registered_models.values()
            if info.is_downloaded
        ]

    def clear_model(self, model_id: str):
        """Remove a specific model from cache"""
        if model_id in self.registered_models:
            model_info = self.registered_models[model_id]
            if model_info.local_path and Path(model_info.local_path).exists():
                for path in Path(model_info.local_path).rglob('*'):
                    if path.is_file():
                        path.unlink()
                Path(model_info.local_path).rmdir()

            model_info.is_downloaded = False
            model_info.local_path = None
            model_info.size_gb = None

    def update_last_used(self, model_id: str):
        """Update last used timestamp for a model"""
        if model_id in self.registered_models:
            self.registered_models[model_id].last_used = datetime.now()
