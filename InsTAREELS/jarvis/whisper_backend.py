"""Explicit CUDA loading. A missing GPU never silently falls back to CPU."""
import os
from pathlib import Path
import site
import ctypes
import math

_dll_handles = []


def settings(options=None):
    """Validate capture/decoder options before opening a device or starting workers."""
    if options is not None and not isinstance(options, dict):
        raise ValueError('whisper options must be an object')
    result = {**{'device':'cuda', 'compute_type':'int8_float16', 'language':'en',
        'partial_interval_seconds':1., 'silence_seconds':.8, 'vad_threshold':.45}, **(options or {})}
    if result['device'] not in ('cuda', 'cpu'):
        raise ValueError('whisper.device must be cuda or cpu')
    if not isinstance(result['compute_type'], str) or not result['compute_type'].strip() or len(result['compute_type'])>32:
        raise ValueError('whisper.compute_type must name a CTranslate2 precision')
    if not isinstance(result['language'], str) or not result['language'].strip() or len(result['language'])>32:
        raise ValueError('whisper.language must name a language or auto')
    for name, low, high in (('partial_interval_seconds',.2,5), ('silence_seconds',.2,5), ('vad_threshold',0,1)):
        value = result[name]
        if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
            raise ValueError('whisper.'+name+' is outside its finite capture range')
    return result


class WhisperUnavailable(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


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
                raise WhisperUnavailable('cuda_libraries_missing', f"CUDA library {name} could not be loaded. Run scripts/setup/setup.ps1 to finish installing the GPU libraries.") from exc


def load_model(path, options):
    options = settings(options)
    prepare_cuda()
    import ctranslate2
    from faster_whisper import WhisperModel
    device = options.get("device", "cuda")
    if device == "cuda" and ctranslate2.get_cuda_device_count() < 1:
        raise WhisperUnavailable('cuda_unavailable', "CUDA GPU unavailable. Check the NVIDIA driver, then run setup.ps1. No CPU fallback was used.")
    if device == "cuda":
        check_cuda_libraries()
    if not (Path(path) / "model.bin").is_file():
        raise WhisperUnavailable('model_missing', "Whisper model missing. Run scripts/setup/setup.ps1 to download it once.")
    return WhisperModel(str(path), device=device,
                        compute_type=options.get("compute_type", "int8_float16"),
                        local_files_only=True, cpu_threads=4, num_workers=1)
