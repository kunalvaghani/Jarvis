"""Explicit CUDA loading. A missing GPU never silently falls back to CPU."""
import os
from pathlib import Path
import site
import ctypes

_dll_handles = []


def prepare_cuda():
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    if os.name != "nt" or _dll_handles:
        return
    paths = []
    for package_dir in site.getsitepackages():
        nvidia = Path(package_dir) / "nvidia"
        for folder in nvidia.glob("*/bin"):
            paths.append(str(folder))
            _dll_handles.append(os.add_dll_directory(str(folder)))
    if paths:
        os.environ["PATH"] = os.pathsep.join(paths + [os.environ.get("PATH", "")])


def check_cuda_libraries():
    if os.name == "nt":
        for name in ("cublas64_12.dll", "cublasLt64_12.dll", "cudnn64_9.dll", "cudnn_ops64_9.dll", "cudnn_cnn64_9.dll"):
            try:
                ctypes.WinDLL(name)
            except OSError as exc:
                raise RuntimeError(f"CUDA library {name} could not be loaded. Run setup.ps1 to finish installing the GPU libraries. {exc}") from exc


def load_model(path, options):
    prepare_cuda()
    import ctranslate2
    from faster_whisper import WhisperModel
    device = options.get("device", "cuda")
    if device == "cuda" and ctranslate2.get_cuda_device_count() < 1:
        raise RuntimeError("CUDA GPU unavailable. Check the NVIDIA driver, then run setup.ps1. No CPU fallback was used.")
    if device == "cuda":
        check_cuda_libraries()
    if not (Path(path) / "model.bin").is_file():
        raise RuntimeError("Whisper model missing. Run setup.ps1 to download it once.")
    return WhisperModel(str(path), device=device,
                        compute_type=options.get("compute_type", "int8_float16"),
                        local_files_only=True, cpu_threads=4, num_workers=1)
