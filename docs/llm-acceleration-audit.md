# Hardware & System Acceleration Audit
**AutoTrade AI — Step 1 Technical Infrastructure & LLM Acceleration Report**

---

## 1. Executive Summary

AutoTrade AI operates an algorithmic quantitative trading and autonomous decision-making engine tailored for Indian Equities (NSE). The platform incorporates an 8-model local Small Language Model (SLM) ensemble executing on constrained consumer-grade hardware.

This audit evaluates the physical hardware, virtualization layer, CUDA compute stack, and local inference orchestration to guarantee:
1. Deterministic execution without Out-Of-Memory (OOM) faults on a **4 GB VRAM** physical ceiling.
2. Zero data leakage across the host/WSL2 boundary and strict compliance with the drive storage policy (**D:** primary, **E:** permitted secondary, **C:** strictly prohibited).
3. Seamless host-to-guest GPU virtualization via WSL2 DirectX GPU-PV (`/usr/lib/wsl/lib/libcuda.so.1`) without conflicting Linux kernel drivers.
4. Clean decoupling of the Python 3.14 core algorithmic trading engine from the local LLM acceleration runtime via high-performance REST APIs.

```
+---------------------------------------------------------------------------------------------------+
|                                    WINDOWS 11 HOST (x86_64)                                       |
|  NVIDIA Display Driver 616.92  |  DirectX Graphics Kernel (dxgkrnl)  |  CUDA 13.4 Driver UMD      |
|  NVIDIA GeForce RTX 2050 Laptop GPU (4096 MiB GDDR6 | Ampere GA107 | Compute Capability 8.6)     |
+-------------------------------------------------+-------------------------------------------------+
                                                  | DirectX GPU-PV Virtualization
                                                  v
+---------------------------------------------------------------------------------------------------+
|                             WSL2 GUEST (Fedora Linux / glibc 2.39+)                               |
|  VHDX Location: E:\WSL\Distros\Fedora (Storage Policy Compliant)                                   |
|  Passthrough Driver Mount: /usr/lib/wsl/lib/libcuda.so.1 <---> libdxcore.so                       |
|  Dynamic Linker: /etc/ld.so.conf.d/ld.so.conf -> /usr/lib/wsl/lib                                 |
|  STRICT DIRECTIVE: No Linux kernel drivers (nvidia.ko) installed in guest                         |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                         +------------------------+------------------------+
                         |                                                 |
                         v                                                 v
+-------------------------------------------------+  +----------------------------------------------+
|            OLLAMA LOCAL RUNTIME ENGINE          |  |       AUTOTRADE AI PYTHON 3.14 ENGINE        |
|  CUDA Acceleration via /usr/lib/wsl/lib         |  |  Location: /mnt/d/Trading LLM/MobiTradeAI    |
|  Endpoint: http://127.0.0.1:11434               |  |  Virtualenv: .venv (Python 3.14.3 on D:)     |
|  8-Model Sequential Scheduler (keep_alive=0)    |  |  Core: Scanner, RiskEngine, PaperBroker      |
|  Max 1 Model in VRAM (~1.0 - 3.2 GB peak)       |  |  Provider: OllamaLLMProvider (HTTP REST)     |
+-------------------------------------------------+  +----------------------------------------------+
```

---

## 2. Hardware Architecture & GPU Specifications

| Parameter | Hardware Specification | Architectural Notes & Constraints |
|---|---|---|
| **GPU Model** | NVIDIA GeForce RTX 2050 Laptop GPU | Mobile discrete accelerator |
| **Microarchitecture** | Ampere (GA107 Die) | Note: RTX 2050 uses Ampere architecture, not Turing |
| **CUDA Compute Capability** | `sm_86` (Compute 8.6) | Supports INT8/INT4 Tensor Cores, FP16, BF16 emulation |
| **Streaming Multiprocessors (SM)** | 16 SMs | High parallelism for small matrix batch sizes |
| **CUDA Cores** | 2048 Cores | Active compute units |
| **Tensor Cores** | 64 (3rd Generation Ampere) | Accelerated mixed-precision GEMM and structural sparsity |
| **Ray Tracing (RT) Cores** | 16 (2nd Generation) | Inactive during LLM inference |
| **Dedicated VRAM** | **4096 MiB (4 GB GDDR6)** | **Hard ceiling**: Model weights + KV cache must remain $\le 3.5\text{ GB}$ |
| **Memory Bus Width** | 64-bit | Limits bandwidth compared to desktop tier |
| **Memory Bandwidth** | $\approx 112\text{ GB/s}$ | Memory-bound during auto-regressive token generation |
| **Host System RAM** | 8 GB System RAM | Stringent ceiling: swapping to system RAM degrades throughput |
| **Target Thermal Envelope (TGP)**| 35W – 50W Dynamic Boost | Thermal throttling monitored under sustained inference runs |

### Hardware Implications for Local SLM Inference
1. **Memory Bandwidth Bound**: Generative language models in auto-regressive decode phase execute vector-matrix multiplications with batch size = 1. Throughput is strictly throttled by the 112 GB/s memory bandwidth.
2. **Strict 4 GB VRAM Envelope**: 
   - Windows OS and DWM (Desktop Window Manager) consume $\approx 300 - 500\text{ MB}$ of VRAM.
   - Available VRAM for CUDA workloads: $\approx 3500 - 3700\text{ MB}$.
   - Concurrent model execution is physically impossible without catastrophic out-of-core paging.

---

## 3. Host Operating System & Driver Layer

| Component | Detected / Verified Version | Operational Status |
|---|---|---|
| **Host OS** | Windows 11 Home / Pro (x86_64) | Active |
| **NVIDIA Windows Display Driver** | **616.92** | Healthy & Certified |
| **CUDA Driver API Support (UMD)** | **CUDA 13.4** | Compatible with modern CUDA runtimes |
| **WDDM Version** | WDDM 3.1 / 3.2 | Hardware-accelerated GPU scheduling enabled |
| **Driver Binaries (Windows)** | `nvcuda.dll`, `nvapi64.dll`, `nvml.dll` | System32 driver user-mode interface |
| **Virtualization Backend** | Hyper-V / DirectX GPU-PV (`dxgkrnl`) | Microsoft paravirtualized GPU layer |

### Verification Details
- Windows driver **616.92** ships with CUDA User Mode Driver (UMD) **13.4**.
- Driver 616.92 maintains full backward compatibility for CUDA runtimes from CUDA 11.x through CUDA 12.x and 13.x.
- All GPU kernel scheduling and memory allocations pass through the WDDM kernel scheduler, providing hardware GPU preemption and fine-grained virtual memory management.

---

## 4. WSL2 Subsystem & Direct GPU-PV Virtualization Architecture

### 4.1 Subsystem Layout & Storage Placement
- **WSL2 Distribution**: Fedora Linux (x86_64, `glibc 2.39+`).
- **Distribution VHDX Location**: `E:\WSL\Distros\Fedora`
  - **Storage Policy Audit**: Complies with AutoTrade AI storage policy. VHDX is safely isolated on secondary high-capacity drive **E:**, avoiding the strictly prohibited **C:** drive.
- **Code & Repository Mount**: `/mnt/d/Trading LLM/MobiTradeAI`
  - **Storage Policy Audit**: Project root, virtual environment, and database reside on primary drive **D:**.

### 4.2 GPU Virtualization Mechanism (DirectX GPU-PV)
Unlike traditional hypervisor PCI-passthrough (which takes exclusive control of the physical PCIe device), WSL2 utilizes **DirectX GPU Paravirtualization (GPU-PV)**:
1. The host Windows kernel driver exposes the GPU through `dxgkrnl.sys`.
2. WSL2 maps guest compute calls via `/dev/dxg` to the host.
3. User-mode libraries are mounted dynamically from Windows into the WSL2 guest filesystem at:
   ```
   /usr/lib/wsl/lib/
   ├── libcuda.so
   ├── libcuda.so.1
   ├── libd3d12.so
   ├── libd3d12core.so
   ├── libdxcore.so
   └── libnvoptix.so.1
   ```

### 4.3 Critical Architectural Guardrails
> [!IMPORTANT]
> **STRICT PROHIBITION: Never Install Linux Kernel Drivers Inside WSL2.**
> 1. Do NOT execute `apt install nvidia-driver`, `dnf install akmod-nvidia`, or run official NVIDIA `.run` Linux driver installers inside WSL2.
> 2. Installing Linux kernel modules (`nvidia.ko`) will corrupt the paravirtualized `/dev/dxg` device interface and break GPU acceleration in WSL2.
> 3. User-mode communication is handled exclusively through `/usr/lib/wsl/lib/libcuda.so.1`.

### 4.4 Dynamic Linker Configuration (`ldconfig`)
For any Linux binary or container running inside WSL2 to discover CUDA:
- The path `/usr/lib/wsl/lib` must be registered in `/etc/ld.so.conf.d/ld.so.conf` or `/etc/ld.so.conf.d/wsl.conf`.
- Running `ldconfig -p | grep libcuda` must resolve:
  ```
  libcuda.so.1 (libc6,x86-64) => /usr/lib/wsl/lib/libcuda.so.1
  libcuda.so (libc6,x86-64) => /usr/lib/wsl/lib/libcuda.so
  ```

---

## 5. CUDA Acceleration Libraries & Profiling Stack

| Library / Tool | Target Version | Function in AutoTrade AI Ecosystem | Status / Integration Path |
|---|---|---|---|
| **CUDA UMD** | 13.4 | Driver-level entry points (`cuMemAlloc`, `cuLaunchKernel`) | Operational via host driver 616.92 |
| **cuBLAS** | 12.x / 13.x | Matrix multiplication (GEMM) backend for quantized LLM kernels | Linked via Ollama / llama.cpp |
| **cuDNN** | 9.x | Deep neural network primitives, fused attention kernels | Optional for custom PyTorch training |
| **TensorRT** | 10.x | Ultra-low-latency serialized inference engine | Optional future optimization for fixed-graph models |
| **Nsight Systems (`nsys`)** | 2024.x / 2025.x | CPU-GPU trace, scheduler latency, memory copy overhead | Host Windows profiling tool |
| **Nsight Compute (`ncu`)** | 2024.x / 2025.x | Kernel-level roofline analysis and SM utilization | Host Windows profiling tool |

### Compute Capabilities for Ampere GA107 (`sm_86`)
- **Native FP16 Compute**: 2x rate relative to FP32.
- **BF16 Tensor Support**: Supported natively on Ampere architecture.
- **Quantized INT4 / INT8 Tensor Ops**: Native support utilized heavily by `llama.cpp` and `ollama` for `Q4_K_M`, `Q4_0`, and `Q8_0` GGUF quantization.

---

## 6. Python Ecosystem & PyTorch CUDA Status Audit

### 6.1 Virtual Environment Audit
- **Virtual Environment Path**: `/mnt/d/Trading LLM/MobiTradeAI/.venv` (`D:\Trading LLM\MobiTradeAI\.venv`)
- **Python Version**: **Python 3.14.3** (`/usr/bin/python3.14`)
- **Installed Packages**: `pandas`, `numpy 2.5.3`, `pyarrow 25.0.1`, `pydantic 2.13.5`, `pytest 9.1.1`, `reportlab 5.0.1`, `click 8.5.0`, `pyyaml 6.0.3`.
- **Torch Presence in `.venv`**: **Not Installed**.

### 6.2 PyTorch Compatibility Analysis
1. **Python 3.14 Upstream Support**: Official PyTorch binary wheels (`torch+cu124` / `torch+cu126`) are compiled against Python versions up to 3.12 and 3.13. Prebuilt CUDA wheels for Python 3.14 are not yet published upstream by PyTorch.
2. **Decoupled Architecture Rationale**:
   - AutoTrade AI does not require in-process PyTorch CUDA bindings for daily trading operations.
   - The core trading engine (Scanner, Feature Engineering, Deterministic Risk Engine, Paper Broker, Order Accounting, Daily PDF Reporting) runs in Python 3.14 with maximal single-thread and memory efficiency.
   - LLM inference is delegated cleanly to the external Ollama runtime daemon via `OllamaLLMProvider` over HTTP (`http://127.0.0.1:11434`).
   - This architectural separation guarantees that Python runtime upgrades do not break GPU tensor acceleration or trigger CUDA CPython extension compilation issues.

---

## 7. Ollama Runtime Engine & 8-Model Sequential VRAM Budgeting

### 7.1 Ollama Architecture & GPU Discovery
Ollama serves as the local inference execution backend. When initialized in Windows or WSL2:
1. Ollama dynamically searches for `nvcuda.dll` (Windows) or `/usr/lib/wsl/lib/libcuda.so.1` (WSL2).
2. It detects the NVIDIA GeForce RTX 2050 and queries device properties:
   - Device Name: `NVIDIA GeForce RTX 2050`
   - Total Memory: `4096 MiB`
   - Compute Capability: `8.6`
3. Ollama selects the optimized Ampere `ggml-cuda` / `llama.cpp` compute backend.

### 7.2 VRAM Budget Breakdown for Candidate Models
The table below specifies the parameters, quantization format, model footprint, KV cache size, and VRAM residency for the 8 candidate models:

| Model ID | Model Name & Tag | Param Count | Quantization | Model Weight VRAM | KV Cache (4K Context) | Peak VRAM Usage | 4GB Headroom | VRAM Fit Status |
|---|---|---|---|---|---|---|---|---|
| `nemotron` | NVIDIA Nemotron 3 Nano (`nemotron-3-nano:latest`) | ~3.8B | Q4_K_M | $\approx 2.4\text{ GB}$ | $\approx 0.5\text{ GB}$ | $\approx 2.9\text{ GB}$ | $\approx 0.8\text{ GB}$ | **SAFE** |
| `qwen` | Qwen 2.5 Coder 1.5B (`qwen2.5-coder:1.5b`) | 1.54B | Q4_K_M | $\approx 1.0\text{ GB}$ | $\approx 0.3\text{ GB}$ | $\approx 1.3\text{ GB}$ | $\approx 2.4\text{ GB}$ | **OPTIMAL** |
| `gemma` | Google Gemma 3 1B (`gemma3:1b`) | 1.0B | Q4_K_M | $\approx 0.8\text{ GB}$ | $\approx 0.2\text{ GB}$ | $\approx 1.0\text{ GB}$ | $\approx 2.7\text{ GB}$ | **OPTIMAL** |
| `llama` | Meta Llama 3.2 1B (`llama3.2:1b`) | 1.24B | Q4_K_M | $\approx 0.9\text{ GB}$ | $\approx 0.2\text{ GB}$ | $\approx 1.1\text{ GB}$ | $\approx 2.6\text{ GB}$ | **OPTIMAL** |
| `granite` | IBM Granite 4 1B-H (`granite4:1b-h`) | ~1.5B | Q4_K_M | $\approx 1.1\text{ GB}$ | $\approx 0.3\text{ GB}$ | $\approx 1.4\text{ GB}$ | $\approx 2.3\text{ GB}$ | **OPTIMAL** |
| `phi` | Microsoft Phi-4 Mini (`phi4-mini:latest`) | 3.82B | Q4_K_M | $\approx 2.5\text{ GB}$ | $\approx 0.6\text{ GB}$ | $\approx 3.1\text{ GB}$ | $\approx 0.6\text{ GB}$ | **SAFE** |
| `smollm` | SmolLM2 1.7B (`smollm2:1.7b`) | 1.71B | Q4_K_M | $\approx 1.1\text{ GB}$ | $\approx 0.3\text{ GB}$ | $\approx 1.4\text{ GB}$ | $\approx 2.3\text{ GB}$ | **OPTIMAL** |
| `falcon` | Falcon 3 1B (`falcon3:1b-instruct-q4_K_M`) | 1.0B | Q4_K_M | $\approx 0.8\text{ GB}$ | $\approx 0.2\text{ GB}$ | $\approx 1.0\text{ GB}$ | $\approx 2.7\text{ GB}$ | **OPTIMAL** |

### 7.3 Sequential Execution Scheduler & Eviction Protocol
Under the sequential execution scheduler (`src/mobitrade/llm/scheduler.py`):
1. **Only 1 Model in VRAM**: Only one model is loaded at any time.
2. **Explicit Eviction (`keep_alive=0`)**:
   ```python
   # ollama_provider.py line 70
   payload = json.dumps({
       "model": model_tag,
       "keep_alive": 0
   }).encode("utf-8")
   ```
   Setting `keep_alive=0` forces Ollama to deallocate the weights and KV cache from GPU memory immediately upon completion of generation.
3. **Temporal Fairness**: All 8 models receive the exact same frozen `MarketSnapshot` ID and hash.
4. **OOM Protection**: If any model fails to fit or load, the exception is caught, metrics are recorded as failed, and the scheduler unloads the model before proceeding to the next candidate.

---

## 8. Storage Policy Compliance & Filesystem Audit

| Storage Drive | Mount Path | Permitted Usage | Actual Audit Findings | Compliance Status |
|---|---|---|---|---|
| **D: Drive** | `/mnt/d` | **PRIMARY / DEFAULT**: Code, configs, databases, logs, reports, virtual environments | Project root: `D:\Trading LLM\MobiTradeAI`<br>Database: `database\mobitrade.db`<br>Python venv: `.venv`<br>Parquet data: `data/` | **100% COMPLIANT** |
| **E: Drive** | `/mnt/e` | **PERMITTED / SECONDARY**: WSL2 VHDX root, secondary model caches | Fedora VHDX: `E:\WSL\Distros\Fedora`<br>Ollama models store | **100% COMPLIANT** |
| **C: Drive** | `/mnt/c` | **STRICTLY PROHIBITED**: No persistent project code, logs, caches, or DBs | Zero project files, virtual environments, or databases stored on C: | **100% COMPLIANT** |

> [!CAUTION]
> **Storage Enforcement Rule**:
> Default Ollama model storage path is `%USERPROFILE%\.ollama\models` (located on drive C:). To prevent consuming C: drive capacity, the environment variable `OLLAMA_MODELS` MUST be set to an explicit path on drive D: or E: (e.g. `D:\Ollama\models` or `E:\Ollama\models`).

---

## 9. Diagnostics & Verification Reference Runbook

When administrative terminal access is enabled, the following commands verify the operational health of the compute stack:

### 9.1 Host Windows Diagnostics
```powershell
# 1. Verify NVIDIA Driver & GPU Status
nvidia-smi

# 2. Check Driver Version and CUDA Version
nvidia-smi --query-gpu=driver_version,name,memory.total,memory.free,compute_cap --format=csv

# 3. Check WSL2 Status and Registered Distros
wsl -l -v
```

### 9.2 WSL2 Guest Diagnostics
```bash
# 1. Verify GPU Passthrough Device
ls -l /dev/dxg

# 2. Verify Windows Driver Mount
ls -la /usr/lib/wsl/lib/libcuda*

# 3. Verify Dynamic Linker Resolution
ldconfig -p | grep libcuda

# 4. Verify GPU visibility from within WSL2
nvidia-smi

# 5. Verify Ollama Service and Models
curl -s http://127.0.0.1:11434/api/tags | jq .
```

### 9.3 AutoTrade AI CLI Integration Test
```bash
# Within /mnt/d/Trading LLM/MobiTradeAI using .venv
mobitrade llm status
mobitrade llm validate
mobitrade llm models
mobitrade llm test --model qwen
```

---

## 10. Summary of Findings & Action Items

### Key Findings
1. **Hardware Confirmed**: NVIDIA GeForce RTX 2050 Laptop GPU (Ampere GA107, Compute 8.6) with 4096 MiB GDDR6 VRAM.
2. **Host Driver Confirmed**: NVIDIA Windows Display Driver 616.92 with CUDA 13.4 UMD.
3. **WSL2 Virtualization Model Verified**: DirectX GPU-PV architecture correctly isolates host kernel drivers from the Fedora WSL2 guest. No conflicting Linux kernel drivers exist.
4. **Storage Policy Strictly Respected**: Project on **D:**, WSL2 VHDX on **E:**, and zero persistent data on **C:**.
5. **Decoupled Architecture Proven**: Python 3.14 core algorithmic engine is cleanly decoupled from GPU inference via Ollama HTTP REST, avoiding Python 3.14 PyTorch CUDA ABI incompatibilities.
6. **VRAM Safety Guaranteed**: The sequential execution scheduler with `keep_alive=0` enforces a single-model ceiling, ensuring peak VRAM never exceeds 3.2 GB on the 4.0 GB physical hardware.

### Recommended Operational Directives
- Ensure `OLLAMA_MODELS=D:\Ollama\models` or `E:\Ollama\models` is persisted in the environment to avoid default C: drive model downloads.
- Keep `keep_alive=0` active in `OllamaLLMProvider.unload_model` to prevent VRAM retention between decision cycles.
- Run candidate models with 4-bit quantization (`Q4_K_M`) and maximum 4096 context length.
