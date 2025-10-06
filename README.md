# Kortex

Kortex is a voice-activated desktop assistant for Windows. It uses local, on-device models for speech-to-text, language understanding, and text-to-speech to provide a private and responsive AI assistant experience.

## Tech Stack

* **Language**: Python
* **GUI**: PyQt5
* **Speech-to-Text (STT)**: Vosk
* **Text-to-Speech (TTS)**: Piper
* **Language Model (LLM)**: Ollama (running a model like Granite, Phi-3, or Llama 3)
* **Database**: SQLite for persistent memory (notes, reminders)
* **Core Libraries**: PyAudio, Requests, PyYAML, PyAutoGUI

## Setup Process

1. **Install Python**: Ensure you have Python 3.10 or newer installed. You can download it from [python.org](https://www.python.org/). Make sure to check "Add Python to PATH" during installation.

2. **Install Ollama**: Download and install Ollama for Windows from [ollama.com](https://ollama.com/).

3. **Clone the Repository**:

    ```shell
    git clone https://github.com/KHROTU/kortex.git
    cd kortex
    ```

4. **Create a Conda Environment** (Recommended):

    ```shell
    # If you don't have conda, install Miniconda/Anaconda first:
    # https://docs.conda.io/en/latest/miniconda.html
    conda create -n kortex python=3.10 -y
    conda activate kortex
    ```

    Note: pip will be available in the conda environment; proceed with the project's dependency install step to install requirements into this environment.

5. **Install Dependencies**:

    ```shell
    pip install -r requirements.txt
    ```

6. **Download an LLM**: Pull a small, efficient model suitable for tool use. We recommend `granite4:micro`.

    ```shell
    ollama pull granite4:micro
    ```

7. **Run the Application**:

    ```shell
    python -m kortex.main
    ```

8. **Initial Configuration**:
    * The first time you run Kortex, a system tray icon will appear. Right-click it and select "Settings".
    * **STT/TTS**: Go to the Speech-to-Text and Text-to-Speech tabs to download the necessary voice and language models.
    * **LLM**: The application should auto-detect your Ollama models. Ensure `granite4:micro` (or your chosen model) is selected.
    * **Services**: To use tools like weather, currency conversion, or location finding, you must enable them and provide your own free API keys. Follow the links in the settings panel to get them.
    * **Restart**: After configuring, right-click the tray icon and select "Restart Kortex" to apply all changes.

## How to Use

1. **Wake Word**: Activate Kortex by saying "Hey Kortex" or just "Kortex". The GUI will appear, indicating it's listening.
2. **Give a Command**: After the confirmation sound ("Yes?"), state your command clearly. For example:
    * "What time is it?"
    * "Open calculator."
    * "What's the weather like in Paris?"
    * "Set a timer for 5 minutes."
    * "Make a note that I parked on level 3."
3. **Interaction**: Kortex will process the command, perform the action, and provide a spoken response. The GUI will disappear when the interaction is complete.

## System Requirements

These specifications are estimates for running small 3-4B parameter models locally.

| Specification      | Minimum                             | Recommended                           |
|--------------------|-------------------------------------|---------------------------------------|
| **CPU**            | Intel Core i5 8th Gen / Ryzen 5 2600| Intel Core i7 9th Gen / Ryzen 7 3700X |
| **RAM**            | 8 GB                                | 16 GB                                 |
| **Storage**        | 10 GB SSD (for models)              | 20 GB NVMe SSD                        |
| **GPU (Optional)** | NVIDIA GTX 1050 (4GB)               | NVIDIA RTX 3060 (8GB+)                |

A dedicated GPU is not required but will significantly improve the LLM's response speed (Tokens per Second).

## Performance Estimates

These estimates are for Granite 4.0 Micro (3.4B parameters) in Q4_K_M quantization via Ollama on CPU-only (or iGPU where applicable), based on benchmarks for similar 3-4B models like Phi-3 Mini. Performance varies with prompt length, RAM (recommend 8+ GB), and cooling; GPUs accelerate via CUDA. Granite's hybrid architecture may yield 10-20% better efficiency than pure transformers. For i7/Ryzen 7, higher core counts boost multi-threaded prompt evaluation.

| Hardware | Equivalent Model | TPS (Tokens/s) | Latency (TTFT, s) |
|----------|------------------|----------------|-------------------|
| Intel Core i5 8th Gen (e.g., i5-8250U) | AMD Ryzen 5 2600 | ~6 | ~2.5 |
| Intel Core i5 9th Gen (e.g., i5-9300H) | AMD Ryzen 5 3600 | ~6.5 | ~2.2 |
| Intel Core i5 10th Gen (e.g., i5-10210U) | AMD Ryzen 5 5600 | ~7 | ~2.0 |
| Intel Core i7 8th Gen (e.g., i7-8550U) | AMD Ryzen 7 2700 | ~8 | ~2.3 |
| Intel Core i7 9th Gen (e.g., i7-9750H) | AMD Ryzen 7 3700X | ~8.5 | ~2.0 |
| Intel Core i7 10th Gen (e.g., i7-10710U) | AMD Ryzen 7 5700X | ~9 | ~1.8 |
| NVIDIA GTX 1050 (4GB) | - | ~25 | ~0.5 |
| Intel UHD Graphics (8th-10th Gen iGPU) | - | ~4 | ~3.0 |
