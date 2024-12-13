from typing import Optional, List
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from model_manager import ModelManager


class LocalLLMEngine:
    def __init__(
        self,
        default_model: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    ):
        """
        Initialize the LLM Engine
        Args:
            default_model: Default model ID to use
        """
        self.default_model = default_model
        # Active model tracking
        self.current_model_id: Optional[str] = None
        self.model = None
        self.tokenizer = None
        self.pipeline = None

    async def load_model(
        self,
        model_manager: ModelManager,
        model_id: Optional[str] = None,
        device_map: str = "auto",
        torch_dtype: Optional[torch.dtype] = torch.float16,
        load_in_8bit: bool = False,
        load_in_4bit: bool = False
    ):
        """Load a model into memory"""
        model_id = model_id or self.default_model

        # Check if we need to load a new model
        if self.current_model_id == model_id and self.model is not None:
            return

        # Ensure model is downloaded
        model_manager.download_model(model_id)

        # Update last used timestamp
        model_manager.update_last_used(model_id)

        print(f"Loading model {model_id}...")

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            cache_dir=model_manager.cache_dir,
            trust_remote_code=True
        )

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Prepare model loading kwargs
        model_kwargs = {
            "device_map": device_map,
            "torch_dtype": torch_dtype,
            "trust_remote_code": True
        }

        if load_in_8bit:
            model_kwargs["load_in_8bit"] = True
        elif load_in_4bit:
            model_kwargs["load_in_4bit"] = True

        # Load model
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            cache_dir=model_manager.cache_dir,
            **model_kwargs
        )

        # Create pipeline
        self.pipeline = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            device_map=device_map,
            torch_dtype=torch_dtype,
            trust_remote_code=True
        )

        self.current_model_id = model_id
        print(f"Model {model_id} loaded successfully!")

    async def generate(
        self,
        model_manager: ModelManager,
        prompt: str,
        model_id: Optional[str] = None,
        max_new_tokens: int = 100,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        num_return_sequences: int = 1,
        **kwargs
    ) -> List[str]:
        """
        Generate text based on prompt

        Args:
            prompt: Input text
            model_id: Optional model override
            max_new_tokens: Maximum new tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            top_k: Top-k sampling parameter
            num_return_sequences: Number of sequences to return
            **kwargs: Additional generation parameters

        Returns:
            List of generated sequences
        """
        # Load model if needed
        if model_id and model_id != self.current_model_id:
            await self.load_model(model_manager, model_id)
        elif self.model is None:
            await self.load_model(model_manager)

        try:
            outputs = self.pipeline(
                prompt,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                num_return_sequences=num_return_sequences,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                **kwargs
            )

            return [output['generated_text'] for output in outputs]

        except Exception as e:
            print(f"Error during generation: {str(e)}")
            raise

    def cleanup(self):
        """Clean up resources"""
        if self.model:
            del self.model
        if self.pipeline:
            del self.pipeline
        torch.cuda.empty_cache()
        self.model = None
        self.pipeline = None
        self.current_model_id = None
