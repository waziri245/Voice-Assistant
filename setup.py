from setuptools import setup, find_packages

setup(
    name="voice_assistant",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        # List your dependencies here (same as requirements.txt)
        # Or you can read requirements.txt:
        line.strip() for line in open('requirements.txt') if line.strip()
    ],
)