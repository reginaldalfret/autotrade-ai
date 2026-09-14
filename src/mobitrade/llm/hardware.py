"""
AutoTrade AI - Hardware & GPU Environment Detection Module.

Inspects GPU hardware (e.g. NVIDIA GeForce RTX 2050 4GB VRAM), CUDA compute
capability (8.6), driver version, WSL2 GPU passthrough (/usr/lib/wsl/lib/libcuda.so.1),
Ollama runtime connection status and GPU support, llama.cpp binaries,
and system memory. Recommends appropriate execution backend and model limits.
"""

import os
import sys
import shutil
import platform
import subprocess
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, List

# Known NVIDIA architectures for compute capability resolution fallback
KNOWN_GPU_COMPUTE_CAPABILITIES = {
    "2050": "8.6",
    "3050": "8.6",
    "3060": "8.6",
    "3070": "8.6",
    "3080": "8.6",
    "3090": "8.6",
    "4050": "8.9",
    "4060": "8.9",
    "4070": "8.9",
    "4080": "8.9",
    "4090": "8.9",
    "A100": "8.0",
    "H100": "9.0",
    "T4": "7.5",
    "V100": "7.0",
}


def _find_nvidia_smi() -> Optional[str]:
    """Locate nvidia-smi executable on Windows or Linux."""
    # Check standard PATH first
    which_path = shutil.which("nvidia-smi")
    if which_path:
        return which_path

    if sys.platform == "win32":
        candidate_paths = [
            Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe",
            Path(r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"),
            Path(r"C:\Windows\System32\nvidia-smi.exe"),
        ]
        for p in candidate_paths:
            if p.exists():
                return str(p)
    else:
        linux_candidates = [
            Path("/usr/bin/nvidia-smi"),
            Path("/usr/local/cuda/bin/nvidia-smi"),
            Path("/usr/lib/wsl/lib/nvidia-smi"),
        ]
        for p in linux_candidates:
            if p.exists():
                return str(p)

    return None


def get_gpu_vram_mb() -> Dict[str, float]:
    """
    Query real-time GPU VRAM (total, free, used) in MiB.
    Returns zeros if no NVIDIA GPU is found.
    """
    smi = _find_nvidia_smi()
    if smi:
        try:
            cmd = [
                smi,
                "--query-gpu=memory.total,memory.free,memory.used",
                "--format=csv,noheader,nounits",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split("\n")[0].split(",")]
                if len(parts) >= 3:
                    return {
                        "total": float(parts[0]),
                        "free": float(parts[1]),
                        "used": float(parts[2]),
                    }
        except Exception:
            pass

    # Fallback to PyTorch if available
    try:
        import torch
        if torch.cuda.is_available():
            dev = 0
            total = torch.cuda.get_device_properties(dev).total_memory / (1024.0 * 1024.0)
            reserved = torch.cuda.memory_reserved(dev) / (1024.0 * 1024.0)
            allocated = torch.cuda.memory_allocated(dev) / (1024.0 * 1024.0)
            free = total - reserved
            return {
                "total": round(total, 2),
                "free": round(max(0.0, free), 2),
                "used": round(allocated, 2),
            }
    except Exception:
        pass

    return {"total": 0.0, "free": 0.0, "used": 0.0}


def get_system_ram_mb() -> Dict[str, float]:
    """
    Inspect system RAM (total, available, used, percent) in MiB.
    Uses psutil if available, otherwise native OS interfaces.
    """
    try:
        import psutil
        vm = psutil.virtual_memory()
        total = vm.total / (1024.0 * 1024.0)
        available = vm.available / (1024.0 * 1024.0)
        used = vm.used / (1024.0 * 1024.0)
        return {
            "total": round(total, 2),
            "available": round(available, 2),
            "used": round(used, 2),
            "percent": float(vm.percent),
        }
    except ImportError:
        pass

    # Windows native fallback via ctypes
    if sys.platform == "win32":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total = stat.ullTotalPhys / (1024.0 * 1024.0)
                avail = stat.ullAvailPhys / (1024.0 * 1024.0)
                used = total - avail
                pct = float(stat.dwMemoryLoad)
                return {
                    "total": round(total, 2),
                    "available": round(avail, 2),
                    "used": round(used, 2),
                    "percent": round(pct, 1),
                }
        except Exception:
            pass

    # Linux native fallback via /proc/meminfo
    if sys.platform.startswith("linux") and os.path.exists("/proc/meminfo"):
        try:
            mem_info: Dict[str, float] = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        mem_info[key] = float(val) / 1024.0  # kB to MB
            total = mem_info.get("MemTotal", 0.0)
            avail = mem_info.get("MemAvailable", mem_info.get("MemFree", 0.0))
            used = max(0.0, total - avail)
            pct = round((used / total * 100.0) if total > 0 else 0.0, 1)
            return {
                "total": round(total, 2),
                "available": round(avail, 2),
                "used": round(used, 2),
                "percent": pct,
            }
        except Exception:
            pass

    # Default fallback
    return {"total": 8192.0, "available": 4096.0, "used": 4096.0, "percent": 50.0}


def is_wsl2() -> bool:
    """Detect whether execution is running inside a WSL2 container."""
    if not sys.platform.startswith("linux"):
        return False
    # Check /proc/version or osrelease for microsoft/wsl
    proc_version = Path("/proc/version")
    if proc_version.exists():
        try:
            content = proc_version.read_text().lower()
            if "microsoft" in content or "wsl" in content:
                return True
        except Exception:
            pass
    # Check WSL lib directory
    if Path("/usr/lib/wsl/lib").exists():
        return True
    return False


def check_wsl2_gpu_passthrough() -> Dict[str, Any]:
    """Check for WSL2 libcuda passthrough library."""
    wsl_detected = is_wsl2()
    libcuda_candidates = [
        "/usr/lib/wsl/lib/libcuda.so.1",
        "/usr/lib/wsl/lib/libcuda.so",
        "/usr/lib/wsl/drivers/libcuda.so.1",
    ]
    detected_path = None
    for cand in libcuda_candidates:
        if os.path.exists(cand):
            detected_path = cand
            break

    return {
        "is_wsl2": wsl_detected,
        "passthrough_detected": detected_path is not None,
        "libcuda_path": detected_path,
    }


def check_ollama_runtime(base_url: str = "http://127.0.0.1:11434") -> Dict[str, Any]:
    """Inspect local Ollama runtime daemon connectivity and GPU capability."""
    endpoint = base_url.rstrip("/")
    status = {
        "connected": False,
        "base_url": endpoint,
        "version": None,
        "gpu_support": False,
        "running_models": [],
        "available_models": [],
    }

    # 1. Version check
    try:
        req = urllib.request.Request(f"{endpoint}/api/version", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                status["connected"] = True
                status["version"] = data.get("version")
    except Exception:
        # Try /api/tags as alternate connectivity check
        try:
            req = urllib.request.Request(f"{endpoint}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    status["connected"] = True
        except Exception:
            return status

    if not status["connected"]:
        return status

    # 2. List loaded models from /api/ps
    try:
        req = urllib.request.Request(f"{endpoint}/api/ps", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("models", [])
                status["running_models"] = [m.get("name") for m in models]
                # Check if any model runs on GPU
                for m in models:
                    size_vram = m.get("size_vram", 0)
                    if size_vram and size_vram > 0:
                        status["gpu_support"] = True
    except Exception:
        pass

    # 3. List installed tags from /api/tags
    try:
        req = urllib.request.Request(f"{endpoint}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                status["available_models"] = [m.get("name") for m in data.get("models", [])]
    except Exception:
        pass

    # If connected and GPU is present, Ollama utilizes CUDA by default
    gpu_mem = get_gpu_vram_mb()
    if gpu_mem["total"] > 0:
        status["gpu_support"] = True

    return status


def find_llamacpp_binaries() -> Dict[str, Any]:
    """
    Search for llama.cpp binaries in PATH, project bin directory,
    and standard installation locations.
    """
    project_root = Path(__file__).resolve().parents[3]
    search_dirs = [
        Path(r"D:\Trading LLM\MobiTradeAI\bin"),
        project_root / "bin",
        Path.home() / "llama.cpp" / "build" / "bin",
        Path(r"C:\Program Files\llama.cpp"),
    ]
    if "LLAMA_CPP_BIN" in os.environ:
        search_dirs.insert(0, Path(os.environ["LLAMA_CPP_BIN"]))

    binary_names = ["llama-cli", "llama-server", "main", "server", "llama-bench"]
    if sys.platform == "win32":
        binary_names = [f"{b}.exe" for b in binary_names] + binary_names

    detected_binaries: Dict[str, str] = {}

    # Check PATH
    for b in binary_names:
        which_p = shutil.which(b)
        if which_p and b not in detected_binaries:
            detected_binaries[b] = which_p

    # Check directory locations
    checked_paths = []
    for d in search_dirs:
        checked_paths.append(str(d))
        if d.exists() and d.is_dir():
            for b in binary_names:
                candidate = d / b
                if candidate.exists() and candidate.is_file():
                    detected_binaries[b] = str(candidate)

    primary_bin = None
    for priority in ["llama-cli.exe", "llama-cli", "main.exe", "main", "llama-server.exe", "llama-server"]:
        if priority in detected_binaries:
            primary_bin = detected_binaries[priority]
            break

    return {
        "detected": primary_bin is not None,
        "primary_binary": primary_bin,
        "binaries": detected_binaries,
        "search_paths_checked": checked_paths,
    }


def detect_gpu_environment(mock: Optional[bool] = None) -> Dict[str, Any]:
    """
    Inspect the system's GPU, CUDA capability, WSL2 environment, Ollama daemon,
    llama.cpp binaries, and system RAM.

    Returns a standardized dictionary containing:
    - gpu: device name, total/free/used VRAM, driver version, compute capability
    - wsl2: WSL2 detection, libcuda.so.1 passthrough status
    - ollama: daemon connection, version, GPU support, model inventory
    - llamacpp: binary detection status and paths
    - system_memory: total/available/used RAM and percent
    - recommendations: recommended runtime, backend, concurrency, and sizing
    """
    # Allow mock override for offline verification and automated tests
    is_mock = mock if mock is not None else (
        os.environ.get("MOBITRADE_MOCK_HARDWARE", "0").lower() in ("1", "true", "yes")
    )

    if is_mock:
        return {
            "gpu": {
                "available": True,
                "device_name": "NVIDIA GeForce RTX 2050",
                "total_vram_mb": 4096.0,
                "free_vram_mb": 3200.0,
                "used_vram_mb": 896.0,
                "driver_version": "551.76",
                "cuda_compute_capability": "8.6",
                "cuda_available": True,
            },
            "wsl2": {
                "is_wsl2": False,
                "passthrough_detected": False,
                "libcuda_path": None,
            },
            "ollama": {
                "connected": True,
                "base_url": "http://127.0.0.1:11434",
                "version": "0.5.1",
                "gpu_support": True,
                "running_models": [],
                "available_models": [
                    "nemotron-3-nano:latest",
                    "qwen2.5-coder:1.5b",
                    "gemma3:1b",
                    "llama3.2:1b",
                    "granite4:1b-h",
                    "phi4-mini:latest",
                    "smollm2:1.7b",
                    "falcon3:1b-instruct-q4_K_M",
                ],
            },
            "llamacpp": {
                "detected": True,
                "primary_binary": r"D:\Trading LLM\MobiTradeAI\bin\llama-cli.exe",
                "binaries": {"llama-cli.exe": r"D:\Trading LLM\MobiTradeAI\bin\llama-cli.exe"},
                "search_paths_checked": [r"D:\Trading LLM\MobiTradeAI\bin"],
            },
            "system_memory": {
                "total_ram_mb": 8192.0,
                "available_ram_mb": 5120.0,
                "used_ram_mb": 3072.0,
                "percent_used": 37.5,
            },
            "os_environment": {
                "platform": "Windows",
                "release": "10.0.22631",
                "is_windows": True,
                "is_linux": False,
                "is_wsl2": False,
            },
            "recommendations": {
                "recommended_runtime": "Ollama Local Daemon (CUDA accelerated)",
                "recommended_backend": "cuda",
                "concurrency_policy": "Sequential Execution (Strictly ONE model in VRAM at a time)",
                "max_recommended_model_size": "1.0B - 3.8B parameters (Q4_K_M/Q8) <= 3.5 GB VRAM footprint",
                "notes": [
                    "GPU NVIDIA GeForce RTX 2050 detected with 4096 MiB VRAM.",
                    "CUDA Compute Capability 8.6 (Ampere GA107) supports FP16/INT8/INT4 Tensor Cores.",
                    "Single-model sequential residency is strictly required to prevent OOM on 4 GB VRAM.",
                ],
            },
        }

    # 1. Real GPU inspection
    gpu_info = {
        "available": False,
        "device_name": "None",
        "total_vram_mb": 0.0,
        "free_vram_mb": 0.0,
        "used_vram_mb": 0.0,
        "driver_version": "None",
        "cuda_compute_capability": "None",
        "cuda_available": False,
    }

    smi_bin = _find_nvidia_smi()
    if smi_bin:
        try:
            # Query GPU properties via nvidia-smi
            query_fields = "name,memory.total,memory.free,memory.used,driver_version,compute_cap"
            cmd = [smi_bin, f"--query-gpu={query_fields}", "--format=csv,noheader,nounits"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            if res.returncode != 0:
                # Fallback without compute_cap in case query not supported
                query_fields = "name,memory.total,memory.free,memory.used,driver_version"
                cmd = [smi_bin, f"--query-gpu={query_fields}", "--format=csv,noheader,nounits"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)

            if res.returncode == 0 and res.stdout.strip():
                first_line = res.stdout.strip().split("\n")[0]
                tokens = [t.strip() for t in first_line.split(",")]
                if len(tokens) >= 5:
                    gpu_info["available"] = True
                    gpu_info["cuda_available"] = True
                    gpu_info["device_name"] = tokens[0]
                    gpu_info["total_vram_mb"] = float(tokens[1])
                    gpu_info["free_vram_mb"] = float(tokens[2])
                    gpu_info["used_vram_mb"] = float(tokens[3])
                    gpu_info["driver_version"] = tokens[4]
                    if len(tokens) >= 6 and tokens[5] and tokens[5] != "[N/A]":
                        gpu_info["cuda_compute_capability"] = tokens[5]
                    else:
                        # Infer compute capability from device name
                        for key, cap in KNOWN_GPU_COMPUTE_CAPABILITIES.items():
                            if key in tokens[0]:
                                gpu_info["cuda_compute_capability"] = cap
                                break
        except Exception:
            pass

    # PyTorch fallback if nvidia-smi did not succeed
    if not gpu_info["available"]:
        try:
            import torch
            if torch.cuda.is_available():
                dev_name = torch.cuda.get_device_name(0)
                cap = torch.cuda.get_device_capability(0)
                props = torch.cuda.get_device_properties(0)
                total_mb = props.total_memory / (1024.0 * 1024.0)
                gpu_info["available"] = True
                gpu_info["cuda_available"] = True
                gpu_info["device_name"] = dev_name
                gpu_info["total_vram_mb"] = round(total_mb, 2)
                gpu_info["cuda_compute_capability"] = f"{cap[0]}.{cap[1]}"
                vram_now = get_gpu_vram_mb()
                gpu_info["free_vram_mb"] = vram_now["free"]
                gpu_info["used_vram_mb"] = vram_now["used"]
        except Exception:
            pass

    # 2. WSL2 detection
    wsl_info = check_wsl2_gpu_passthrough()

    # 3. Ollama runtime inspection
    ollama_info = check_ollama_runtime()

    # 4. llama.cpp binaries
    llamacpp_info = find_llamacpp_binaries()

    # 5. System RAM
    ram_info = get_system_ram_mb()

    # 6. Recommendations synthesis
    notes: List[str] = []
    if gpu_info["available"]:
        notes.append(
            f"GPU '{gpu_info['device_name']}' detected with {gpu_info['total_vram_mb']:.0f} MiB VRAM."
        )
        if gpu_info["cuda_compute_capability"] != "None":
            notes.append(f"CUDA Compute Capability {gpu_info['cuda_compute_capability']} verified.")
        if gpu_info["total_vram_mb"] <= 4500:
            notes.append(
                "Hardware constraint: 4 GB VRAM budget strictly requires sequential single-model execution."
            )
    else:
        notes.append("No NVIDIA GPU detected. Inference will execute on CPU fallback.")

    if ollama_info["connected"]:
        notes.append(f"Ollama local daemon connected (v{ollama_info.get('version', 'unknown')}).")
        recommended_runtime = "Ollama Local Daemon (CUDA accelerated)" if gpu_info["available"] else "Ollama (CPU)"
        recommended_backend = "cuda" if gpu_info["available"] else "cpu"
    elif llamacpp_info["detected"]:
        notes.append(f"llama.cpp binary available at {llamacpp_info['primary_binary']}.")
        recommended_runtime = "llama.cpp (cuBLAS/CUDA)" if gpu_info["available"] else "llama.cpp (CPU)"
        recommended_backend = "cuda" if gpu_info["available"] else "cpu"
    else:
        recommended_runtime = "Ollama Local Daemon (Start via 'ollama serve')"
        recommended_backend = "cuda" if gpu_info["available"] else "cpu"
        notes.append("Notice: No live local inference engine currently responding. Launch Ollama.")

    return {
        "gpu": gpu_info,
        "wsl2": wsl_info,
        "ollama": ollama_info,
        "llamacpp": llamacpp_info,
        "system_memory": {
            "total_ram_mb": ram_info["total"],
            "available_ram_mb": ram_info["available"],
            "used_ram_mb": ram_info["used"],
            "percent_used": ram_info["percent"],
        },
        "os_environment": {
            "platform": platform.system(),
            "release": platform.release(),
            "is_windows": sys.platform == "win32",
            "is_linux": sys.platform.startswith("linux"),
            "is_wsl2": wsl_info["is_wsl2"],
        },
        "recommendations": {
            "recommended_runtime": recommended_runtime,
            "recommended_backend": recommended_backend,
            "concurrency_policy": "Sequential Execution (Strictly ONE model in VRAM at a time)",
            "max_recommended_model_size": "1.0B - 3.8B parameters (Q4_K_M/Q8) <= 3.5 GB VRAM footprint",
            "notes": notes,
        },
    }
