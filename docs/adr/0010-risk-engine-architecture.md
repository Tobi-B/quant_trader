# ADR 0010: Risk-Engine-Architektur (Commission, Slippage, Stop-Loss)

Status:     proposed
Datum:      2026-07-14
Phase:      P4 Risk Management
Supersedes: -
Superseded by: -

## Context

Der bestehende BacktestEngine (Slice 3.1) simuliert Trades ohne
Kosten oder Risiko-Limits. Real existieren zwei Kostenkomponenten
(Commission, Slippage) und ein Downside-Limit (Stop-Loss). Diese
mussen in Phase 4 ergaenzt werden, damit Netto-Returns realistisch
sind und der Trader Downside-Szenarien analysieren kann.

Phase 4 wird als **ein grosser Slice (4.1)** umgesetzt, der alle drei
Features umfasst. Begruendung:
- Commission + Slippage sind beide Cost-Komponenten mit kleinem Scope
- Stop-Loss ist eng mit der Fill-/Portfolio-Logik verknuepft
- Alle drei brauchen eine `BacktestConfig`-Erweiterung und
  Engine-Iteration-Wiring; gemeinsame Tests sind natuerlich

## Decision

### 1. Commission (US-P4.1)

**Modell**: IBKR-Tiered-Lite, vereinfacht:
- `commission_per_trade: float` (Default 0.0, IBKR-Default 1.0 USD)
- `commission_per_share: float` (Default 0.0, IBKR-Default 0.01 USD)
- Pro Fill: `commission = max(per_trade, qty * per_share)`
- Buchung: `cash -= (qty * price + commission)` bei BUY,
  `cash += (qty * price - commission)` bei SELL
- `Fill.fee` (existierendes Feld) traegt die Commission pro Fill
- `Trade.pnl` beruecksichtigt Entry- + Exit-Commission

### 2. Slippage (US-P4.2)

**Modell**: Linear-Perzent, auf den Open-Preis (Fill-Mode NEXT_OPEN):
- `slippage_pct: float` (Default 0.0, z.B. 0.1 fuer 0.1%)
- BUY: `fill_price = bar.open * (1 + slippage_pct / 100)`
- SELL: `fill_price = bar.open * (1 - slippage_pct / 100)`
- Slippage ist **im Fill-Preis** enthalten, nicht als separater Fee
- Bei `FillMode.SAME_CLOSE` analog auf Close-Preis anwenden

### 3. Stop-Loss (US-P4.3)

**Modell**: Fixed-Percentage-vom-Entry:
- `stop_loss_pct: float | None` (Default None = aus)
- Pro Bar (vor `strategy.on_bar`): check ob offene Long-Position
  den Entry-Preis um mehr als `stop_loss_pct` unterschritten hat
- Trigger: Bar-Open < Entry-Price * (1 - stop_loss_pct / 100)
- Bei Trigger: SELL-Fill zum Open-Preis (abzueglich Slippage)
- Stop-Loss-Trade hat `reason` (z.B. via separate Log-Message, da
  `Trade`-Dataclass aktuell kein `reason`-Feld hat; alternative:
  ueber `Trade.pnl`-Marker oder neuer Marker)
- Reihenfolge pro Bar: Stop-Loss-Checks aller Positionen ->
  Strategy-Signals -> Pending-Fills

### 4. Backward-Compat

- Alle drei Features haben `Default 0.0` / `Default None`
- Bestehende 355 Tests bleiben unveraendert gruen
- `BacktestConfig` ist frozen dataclass; neue Felder mit Defaults
  via `field(default=...)` oder direkt in `__init__` ergaenzt

### 5. Architektur

- `BacktestConfig` (frozen): neue Felder `commission_per_trade`,
  `commission_per_share`, `slippage_pct`, `stop_loss_pct`
- `Fill` (frozen): `fee: float = 0.0` (existiert bereits)
- `FillSimulator`: bekommt `slippage_pct`-Parameter, passt Fill-Preis an
- `BacktestEngine._run_single` / `_run_multi`: integriert
  Stop-Loss-Check vor `strategy.on_bar`
- `BacktestEngine._apply_fill`: integriert Commission-Berechnung
  und -Abzug
- `BacktestEngine` loggt `backtest.stop_loss` (Warnung) bei Trigger

## Consequences

**Positiv**
- Realistische Netto-Returns durch Commission + Slippage
- Downside-Limit durch Stop-Loss testbar
- Backward-Compat: alte Tests bleiben unveraendert gruen
- Alle drei Features konfigurierbar via `BacktestConfig`
- Defaults entsprechen IBKR (Industrie-Standard)

**Negativ**
- Commission-Modell ist vereinfacht (kein tiered pricing)
- Slippage ist linear (kein volume-impact)
- Stop-Loss nur Long-Positionen, kein Trailing
- Stop-Loss-Reason nicht direkt im `Trade`-Dataclass (nur via Log)

**Neutral**
- Phase 4 als 1 grosser Slice (vs. 3 separate) reduziert
  Commit-/Review-Aufwand, aber groesserer Diff pro Commit
- Kein neuer ADR-Status; existierende Architektur bleibt

## Alternatives Considered

- **3 separate Slices (4.1/4.2/4.3)**: User-Praeferenz war "1 grosser
  Slice" fuer schnelleren Durchsatz, abgelehnt
- **Tiered Commission (Volume-basiert)**: Out-of-Scope fuer P4;
  spaeterer Refactor billig, abgelehnt
- **Trailing-Stop-Loss**: Out-of-Scope (US-P4.3 explizit)
- **Stop-Loss auf Portfolio-Ebene (max DD)**: Phase 5/6, abgelehnt
- **Intraday-Stop (Low-basierend)**: Out-of-Scope (Phase 1 Intraday
  unterstuetzt 60m/15m, aber Stop nur auf Open)
- **Risk-Engine als separates Modul (`risk/engine.py`)**: Diskutiert,
  aber Commission/Slippage gehoert eng zur Fill-Logik (Phase 3),
  Stop-Loss zur Engine-Iteration. Bleibt in `backtest/engine.py`,
  nicht in neuem `risk/`.

## References

- `src/quant_trader/backtest/types.py` (BacktestConfig, Fill)
- `src/quant_trader/backtest/fill.py` (FillSimulator)
- `src/quant_trader/backtest/engine.py` (BacktestEngine, _apply_fill)
- `docs/userstories/p4-risk/risk.md` (US-P4.1, US-P4.2, US-P4.3)
- `docs/prd/p4-risk/risk-engine.md` (Slice-PRD)
- `docs/uml/p4-risk/risk-engine.md` (Mermaid Structure/Flow/Sequence)
- Slice 3.1 PRD (Commission/Slippage als Out-of-Scope markiert)
- NFR-Perf-1, NFR-Data-2
