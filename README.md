# basketBacktestRepo

Basket backtesting workspace for signal-driven stock basket strategies.

## Project Layout

- `basket_backtest_v3_fixed.py`: main backtest script with configurable output directory
- `basket_backtest_v2_fixed.py`: earlier fixed backtest variant
- `basket_backtest_v3_equal_weight.py`: equal-weight basket variant
- `basket_backtest_open_entry.py`: open-entry variant
- `basket_backtest_open_to_close.py`: open-to-close variant
- `us_data_downloader.py`: Yahoo Finance downloader for US stock and ETF daily price history
- `us_options_data_puller.py`: Yahoo Finance option-chain downloader for supported US symbols
- `inputs/signalStrategy/btst.csv`: signal input file
- `inputs/prices/all_stocks_nse_prices.csv`: price input file
- `outputs/`: generated backtest result CSVs

## Run

From the project root:

```bash
python3 basket_backtest_v3_fixed.py \
  inputs/signalStrategy/btst.csv \
  inputs/prices/all_stocks_nse_prices.csv \
  --output-dir outputs
```

## Options

Useful flags:

- `--target`
- `--stop-loss`
- `--max-hold-days`
- `--max-basket-size`
- `--start-date`
- `--end-date`
- `--enable-stock-level-exit`
- `--output-dir`

See full help with:

```bash
python3 basket_backtest_v3_fixed.py --help
```

## US Market Data Utilities

Download daily price history:

```bash
python3 us_data_downloader.py
```

Download options chains for a supported US symbol:

```bash
python3 us_options_data_puller.py
```
