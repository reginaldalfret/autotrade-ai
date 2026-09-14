# AutoTrade AI — Development Environment & Storage Architecture

**Environment Status**: ACTIVE & EMPIRICALLY VERIFIED  
**Date**: September 14, 2026  
**Operating System**: Fedora Linux on WSL2 (Native ext4 Linux Filesystem)  
**Host System**: Windows 11 Host + NVIDIA RTX 2050 (4 GB VRAM)  

---

## 1. Storage Topology & Drive Mapping

AutoTrade AI strictly enforces separation of concerns across filesystem boundaries to maximize I/O throughput and guarantee stability:

| Role | Canonical Path | Filesystem | Purpose |
| :--- | :--- | :--- | :--- |
| **Active Project Repository** | `~/projects/AutoTradeAI` | Fedora Linux (ext4) | Active codebase, `.git`, `.venv`, tests, and development SQLite database (`database/mobitrade.db`). |
| **Fedora Virtual Disk Root** | `E:\WSL\Distros\Fedora` | Windows NTFS (`ext4.vhdx`) | Backing disk image hosting the native Linux filesystem. |
| **Large Datasets Archive** | `D:\Trading LLM\AutoTradeData` (`/mnt/d/Trading LLM/AutoTradeData`) | Windows NTFS (9P Mount) | Multi-gigabyte historical market datasets and bulk ticks. |
| **Rollback & Migration Backup**| `D:\Trading LLM\MobiTradeAI_MIGRATION_BACKUP` | Windows NTFS | Static archive of pre-migration working directory. |
| **System Drive (C:)** | `C:\` | Windows NTFS | **STRICTLY PROHIBITED**: Zero persistent AutoTrade project data. |

---

## 2. Why Fedora Native Filesystem (`~/projects/AutoTradeAI`)?

1. **Massive I/O Performance**: File operations, virtual environment execution, and test execution run natively on Linux `ext4` rather than translating across the Windows 9P mount layer (`/mnt/d/`). Regression test execution improved from **51.78s to 8.60s (over 6x faster)**.
2. **Native POSIX Semantics**: Elimination of CRLF/LF file conversion issues, file locking collisions, and permission anomalies.
3. **Seamless Linux Tooling**: Native integration with Python 3.14 virtual environments, Ollama Unix socket / local HTTP loopback, and DirectX GPU-PV virtualization.

---

## 3. Environment & Hardware Specifications

- **Python Runtime**: Python 3.14.3 virtualenv located at `~/projects/AutoTradeAI/.venv`
- **GPU Virtualization**: DirectX GPU-PV passthrough via `/usr/lib/wsl/lib/libcuda.so.1` (Zero Linux kernel drivers installed in WSL2)
- **Local LLM Runtime**: Ollama Local Daemon (`http://127.0.0.1:11434`)
- **Git Repository**: `https://github.com/reginaldalfret/autotrade-ai.git` on branch `main`
- **Git Identity**: `reginaldalfret <reginaldalfret@gmail.com>`

---

## 4. Daily Development Commands

Always activate the native virtual environment before executing project commands:

```bash
cd ~/projects/AutoTradeAI
source .venv/bin/activate

# Check hardware and GPU acceleration
mobitrade llm hardware

# Query 8-model tournament registry
mobitrade llm models

# Verify cryptographic audit chain
mobitrade audit verify

# Review simulated paper trading portfolio
mobitrade paper status

# Run full regression test suite
pytest -q
```
