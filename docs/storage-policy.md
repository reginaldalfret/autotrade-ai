# Storage Policy & Environment Architecture

## Permitted Storage Drives
- **D: Drive (`/mnt/d`) [PRIMARY / DEFAULT]**:
  - Preferred location for all AutoTrade AI code, configs, datasets, databases, logs, virtual environments, experiment results, and reports.
  - Project root: `D:\Trading LLM\MobiTradeAI` (`/mnt/d/Trading LLM/MobiTradeAI`).
  - Python virtual environment: `/mnt/d/Trading LLM/MobiTradeAI/.venv`.
  - Database: `D:\Trading LLM\MobiTradeAI\database\mobitrade.db`.
  - Cache & Data: `D:\Trading LLM\MobiTradeAI\data\`.
  - Reports: `D:\Trading LLM\MobiTradeAI\reports\`.

- **E: Drive (`/mnt/e`) [PERMITTED / SECONDARY]**:
  - Permitted when technically necessary or appropriate.
  - **Fedora WSL2 VHDX Root**: Lives at `E:\WSL\Distros\Fedora` (MUST NOT be migrated).
  - Secondary model caches or large binary storage if drive D: capacity requires it.

## Strictly Prohibited Storage
- **C: Drive**:
  - Absolutely prohibited for AutoTrade AI persistent project storage.
  - NO source code, virtual environments, datasets, databases, logs, reports, experiment results, model files, model caches, or application caches on `C:`.
