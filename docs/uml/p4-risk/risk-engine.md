# UML: Slice 4.1 - Risk-Engine (Commission + Slippage + Stop-Loss)

Status:    APPROVED
Phase:     P4 Risk Management
Slice:     4.1 Risk-Engine
Approved:  2026-07-14

Mapped Requirements:
- NFR-Perf-1: Backtest <30s (minimal Overhead)
- NFR-Data-2: Adj. Close (nicht direkt betroffen, aber via Engine-Pipeline)
- NFR-Ux-1: klare Logs (backtest.stop_loss WARNING)

Stories:
- US-P4.1: Commission pro Trade (IBKR-Stil)
- US-P4.2: Slippage pro Trade
- US-P4.3: Stop-Loss pro Position

Erweitert die bestehende BacktestEngine (Slice 3.1) um Cost- und
Risk-Komponenten. Bestehende Klassen `BacktestEngine`, `FillSimulator`,
`BacktestConfig` werden modifiziert; `Portfolio`, `Trade`,
`EquitySnapshot` bleiben unveraendert.

## Structure

```mermaid
classDiagram
    class BacktestConfig {
        +initial_cash: float
        +fill_mode: FillMode
        +sizer: object
        +commission_per_trade: float = 0.0
        +commission_per_share: float = 0.0
        +slippage_pct: float = 0.0
        +stop_loss_pct: float | None = None
    }
    class BacktestEngine {
        -_commission_per_trade: float
        -_commission_per_share: float
        -_stop_loss_pct: float | None
        +run(bars_by_ticker) BacktestResult
        -_check_stop_losses(bar, portfolio, open_positions, pending) list~Signal~
        -_apply_fill(fill, portfolio, open_positions, trades)
    }
    class FillSimulator {
        -_mode: FillMode
        -_slippage_pct: float
        +schedule(signal, bars, idx) PendingFill
        +resolve(pending) Fill
    }
    class Fill {
        +ticker: str
        +timestamp: datetime
        +price: float
        +qty: int
        +action: str
        +fee: float = 0.0
    }
    class StopLossChecker {
        <<logic>>
        +check(bar, open_positions, slippage_pct) list~Signal~
    }
    class CommissionCalculator {
        <<logic>>
        +calculate(qty, per_trade, per_share) float
    }
    class Trade {
        +ticker: str
        +entry_date: date
        +entry_price: float
        +exit_date: date
        +exit_price: float
        +pnl: float
        +pnl_pct: float
    }

    BacktestEngine --> BacktestConfig
    BacktestEngine --> FillSimulator
    BacktestEngine --> StopLossChecker : nutzt Logik inline
    BacktestEngine --> CommissionCalculator : nutzt Logik inline
    FillSimulator --> Fill
    BacktestEngine --> Trade
    BacktestConfig --> BacktestEngine : injected via ctor
```

## Flow

```mermaid
flowchart TD
    A([Engine.run start]) --> B[Init: commission, slippage, stop_loss aus config]
    B --> C{fuer jede Bar}
    C --> D[Stop-Loss-Check pro offene Position]
    D --> E{Open < entry * 1 - stop_loss_pct/100?}
    E -->|yes| F[Signal SELL reason=stop_loss enqueuen]
    F --> G[log backtest.stop_loss WARNING]
    E -->|no| H[kein Signal]
    H --> I[strategy.on_bar bar, portfolio]
    G --> I
    I --> J[Signale -> pending_fills via FillSimulator mit Slippage]
    J --> K[pending_fills whose execute_on <= current_bar]
    K --> L{Action?}
    L -->|BUY| M[Commission berechnen max per_trade, qty*per_share]
    M --> N[Cash -= qty*price + commission, open position]
    L -->|SELL| O[Commission berechnen]
    O --> P[Cash += qty*price - commission, close position, Trade erfassen]
    N --> Q[EquitySnapshot]
    P --> Q
    Q --> R{mehr Bars?}
    R -->|yes| C
    R -->|no| S[BacktestResult mit trades, equity_curve]
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant E as BacktestEngine
    participant SLC as StopLossChecker (inline)
    participant S as Strategy
    participant FS as FillSimulator (mit Slippage)
    participant CC as CommissionCalculator (inline)
    participant P as Portfolio
    participant Log as structlog

    U->>E: run(strategy, bars, BacktestConfig commission=1.0, per_share=0.01, slippage=0.1, stop_loss=5.0)
    E->>Log: backtest.start mit risk config
    
    loop fuer jede Bar
        E->>SLC: check_stop_losses(bar, open_positions, stop_loss_pct=5.0)
        alt Open < entry * 0.95
            SLC-->>E: list[Signal SELL reason=stop_loss]
            E->>Log: backtest.stop_loss ticker, entry, trigger
        else kein Trigger
            SLC-->>E: []
        end
        
        E->>S: on_bar(bar, portfolio)
        S-->>E: list[Signal]
        E->>FS: schedule(signals) (mit slippage_pct)
        FS-->>E: pending_fills mit angepasstem Preis
        
        E->>CC: calculate(qty, per_trade=1.0, per_share=0.01)
        CC-->>E: commission = max(1.0, qty*0.01)
        
        E->>P: open/close position + commission
        P-->>E: updated cash, positions
        E->>E: append EquitySnapshot
    end
    
    E->>Log: backtest.complete mit total_commission, stop_loss_count
    E-->>U: BacktestResult (trades, equity_curve)
```

## Notes

- **Backward-Compat**: `commission_per_trade=0.0`, `commission_per_share=0.0`,
  `slippage_pct=0.0`, `stop_loss_pct=None` (Defaults) ergeben identisches
  Verhalten zu Slice 3.1.
- **Stop-Loss-Timing**: Check **vor** `strategy.on_bar`; so verhindert
  der Stop-Loss, dass die Strategie an einem Tag neue Signale generiert,
  an dem die Position bereits geschlossen wurde.
- **Stop-Loss-Trigger**: nur Long-Positionen (Phase 4 hat kein Short).
- **Slippage-Anwendung**: in `FillSimulator.resolve()`, symmetrisch
  fuer BUY (+) und SELL (-).
- **Commission-Buchung**: in `BacktestEngine._apply_fill()`, sowohl
  Entry als auch Exit, `Fill.fee` traegt Commission pro Fill.
- **Trade.pnl**: inkludiert Entry- und Exit-Commission automatisch
  (durch Cash-Buchung in `_apply_fill`).
- **Logging**: `backtest.stop_loss` WARNING mit Ticker, Entry-Price,
  Trigger-Price fuer jedes getriggerte Stop-Loss-Event.
