# QQQ Previous Week Low (PWL) Analysis System

This project implements a machine learning pipeline to analyze QQQ price behavior around the Previous Week Low (PWL). Historically, the PWL serves as a significant level of support and resistance; a breach often leads to a substantial downward move.

## Core Objectives
1. **Breach Probability:** Predict the likelihood of QQQ falling below the PWL on a given day based on the market open.
2. **Follow-through Prediction:** Estimate the probability of a further 2% drop within 5 days after a breach.
3. **Risk/Reward Race:** Determine the probability of reaching a -2% profit target before a +2% stop-loss recovery.

## System Components
- `auto_trader.py`: Orchestrates the end-to-end pipeline (Data Sync -> Feature Engineering -> Model Training -> Prediction).
- `predict.py`: Performs real-time inference using saved XGBoost models.
- `train_models.py`: Trains three specialized XGBoost classifiers for each objective.
- `step1_2_prepare_data.py`: Handles data sanitization and technical feature engineering.
- `generate_stats.py`: Provides definitive historical "Base Rate" statistics.

## Usage
Run the automated pipeline from the `ModelBasedanalysis` directory:
```bash
python3 PWL_System/auto_trader.py [OptionalOpenPrice]
```
- If `[OptionalOpenPrice]` is provided, the system uses it for prediction.
- If omitted, the system attempts to auto-fetch today's open price or prompts for input.

## Model Performance (Tested on 2025-2026 Data)
- **T1 (Breach Probability):** ~95% Accuracy (0.98 ROC-AUC)
- **T2 (2% Follow-through):** ~64% Accuracy
- **T3 (Win/Loss Race):** ~73% Accuracy (73.7% Historical Win Rate)

## Historical Context
A detailed breakdown of historical performance since 2018 can be found in `PWL_System/historical_statistics.md`.
