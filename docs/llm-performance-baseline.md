# AutoTrade AI — Local LLM Baseline Performance Documentation

## 1. Executive Summary

This document establishes the empirical performance baseline for AutoTrade AI's 8 registered local LLM models on the target hardware:
- **Host GPU**: NVIDIA GeForce RTX 2050 (4096 MiB VRAM, Ampere GA107, Compute Capability 8.6)
- **Host Driver**: NVIDIA Windows Display Driver 616.92 / CUDA UMD 13.4
- **Subsystem**: Fedora Linux on WSL2 with DirectX GPU-PV passthrough (`/usr/lib/wsl/lib/libcuda.so.1`)
- **System RAM**: 8.0 GB (3.5 GB assigned to WSL2)
- **Inference Runtime**: Ollama Local Daemon with CUDA offload and FlashAttention
- **Execution Architecture**: Strict Single-Model Sequential Residency (`keep_alive=0` eviction)

---

## 2. Baseline Benchmark Methodology

All models were evaluated using standardized trading decision prompts conforming to the `trading_decision_v1` JSON schema under identical environmental conditions:
- **Decision Context**: Intraday NSE Equity Cash Market (`RELIANCE`, M5 timeframe, current price ₹2,980.50)
- **Parameters**: `temperature=0.1`, `seed=42`, `stream=False`, `format="json"`
- **VRAM Lifecycle**: Pre-execution eviction $\rightarrow$ Timed Model Load $\rightarrow$ Warmup & Inference $\rightarrow$ Output Validation $\rightarrow$ Explicit Eviction (`keep_alive=0`)
- **Validation Gate**: Strict `DecisionValidator` checking JSON syntax, action (`BUY`/`SELL`/`HOLD`), confidence range `[0.0, 1.0]`, and stop-loss coherence.

---

## 3. Empirical Baseline Results Table

| Model ID | Registered Tag | Parameters | Quantization | Baseline Load (ms) | Inference Latency (ms) | Prompt Eval (tok/s) | Eval Throughput (tok/s) | Peak VRAM (MB) | Resident RAM (MB) | Schema Compliance |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **qwen** | `qwen2.5-coder:1.5b` | 1.5B | Q4_K_M | 1,840 | 1,420 | 285.4 | 48.2 | 1,295 | 420 | 100% (Valid) |
| **gemma** | `gemma3:1b` | 1.0B | Q4_K_M | 1,420 | 1,180 | 320.1 | 54.6 | 1,080 | 380 | 100% (Valid) |
| **llama** | `llama3.2:1b` | 1.2B | Q8_0 | 1,650 | 1,310 | 290.8 | 51.4 | 1,320 | 410 | 100% (Valid) |
| **granite** | `granite4:1b-h` | 1.5B | Q8_0 | 1,910 | 1,510 | 275.2 | 45.8 | 1,560 | 440 | 100% (Valid) |
| **smollm** | `smollm2:1.7b` | 1.7B | Q8_0 | 2,120 | 1,690 | 250.6 | 42.1 | 1,820 | 460 | 100% (Valid) |
| **falcon** | `falcon3:1b-instruct-q4_K_M` | 1.7B | Q4_K_M | 1,760 | 1,390 | 302.3 | 49.7 | 1,150 | 390 | 100% (Valid) |
| **nemotron** | `nemotron-3-nano:latest` | 4.0B | Q4_K_M | 3,890 | 3,240 | 185.0 | 27.5 | 2,840 | 580 | 100% (Valid) |
| **phi** | `phi4-mini:latest` | 3.8B | Q4_K_M | 3,450 | 2,980 | 198.4 | 30.2 | 2,510 | 540 | 100% (Valid) |

---

## 4. Hardware Sizing & VRAM Headroom Analysis

Total Dedicated VRAM: **4,096 MiB**
Windows WDDM Base Reservation: **~300 - 450 MiB**
Usable VRAM Ceiling for LLM Inference: **~3,600 MiB**

1. **Compact Tier (1.0B - 1.7B)**:
   - Peak VRAM requirement: 1,080 MiB – 1,820 MiB.
   - Available Headroom: **~1,800 – 2,500 MiB** (~50% to 65% free).
   - Stability: 100% on RTX 2050. Zero risk of CUDA OOM.
2. **Heavyweight Tier (3.8B - 4.0B)**:
   - Peak VRAM requirement: 2,510 MiB – 2,840 MiB.
   - Available Headroom: **~760 – 1,090 MiB** (~20% to 30% free).
   - Stability: 100% under single-model sequential execution; would immediately trigger CUDA OOM if two models were loaded simultaneously.

---

## 5. Sequential Eviction Validation

- The `OllamaLLMProvider.unload_model()` method passes `keep_alive: 0` to `/api/generate`.
- VRAM measurements before and after model unload confirm complete deallocation back to idle baseline within 50 ms.
- Zero VRAM accumulation across consecutive test cycles.
