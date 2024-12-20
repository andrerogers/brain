from setuptools import setup, find_packages

setup(
    name="brain",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "torch",
        "transformers",
        "accelerate",
        "bitsandbytes",
        "huggingface-hub"
    ],
)
