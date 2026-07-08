# UML: Slice 1.1 - Universe Loader

Status:    APPROVED
Phase:     P1 Datenlayer
Slice:     1.1 Universe Loader
Approved:  2026-07-08

Mapped Requirements:
- NFR-Sec-1: keine Secrets in Universe-Listen

Stories:
- US-P1.1: Standard-Listen importieren

## Structure

```mermaid
classDiagram
    class UniverseCLI {
        +load(preset: str) void
        +list() void
    }
    class UniverseLoader {
        -store: UniverseStore
        -presets: PresetRepository
        +load(preset: str) int
        +list() list~Preset~
    }
    class PresetRepository {
        -config_path: Path
        +get(name: str) Preset
        +all() list~Preset~
    }
    class UniverseStore {
        -data_dir: Path
        +save(preset: Preset) Path
        +exists(preset_name: str) bool
    }
    class Preset {
        +name: str
        +description: str
        +tickers: list~str~
    }
    class UniversePresetConfig {
        <<yaml>>
        +sp500: Preset
        +dax40: Preset
        +etfs: Preset
    }

    UniverseCLI --> UniverseLoader
    UniverseLoader --> PresetRepository
    UniverseLoader --> UniverseStore
    UniverseStore ..> Preset
    PresetRepository ..> UniversePresetConfig
    PresetRepository ..> Preset
```

## Flow

```mermaid
flowchart TD
    A([User runs: python -m quant_trader.universe load --preset sp500]) --> B[CLI parses args]
    B --> C{Valid preset name?}
    C -->|no| D[Error: universe.preset_unknown + list available]
    D --> Z([Exit 1])
    C -->|yes| E[UniverseLoader.load preset]
    E --> F{Store has file?}
    F -->|yes| G[Skip / Log: universe.exists]
    G --> H([Exit 0])
    F -->|no| I[PresetRepository.get preset]
    I --> J[UniverseStore.save as CSV]
    J --> K[Log: universe.loaded, count=N]
    K --> H
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant CLI as UniverseCLI
    participant L as UniverseLoader
    participant PR as PresetRepository
    participant S as UniverseStore
    participant Log as structlog

    U->>CLI: load --preset sp500
    CLI->>L: load(sp500)
    L->>PR: get(sp500)
    PR-->>L: Preset(name, tickers)
    L->>S: exists(sp500)?
    alt file missing
        S-->>L: False
        L->>S: save(preset)
        S-->>L: path
        L->>Log: universe.loaded(name=sp500, count=503)
    else file exists
        S-->>L: True
        L->>Log: universe.exists(name=sp500)
    end
    L-->>CLI: ok
    CLI-->>U: exit 0
```