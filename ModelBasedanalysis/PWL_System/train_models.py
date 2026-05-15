import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, roc_auc_score
import json

def train_and_save_models(file_path):
    df = pd.read_csv(file_path)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')

    # 1. Define Features
    features = ['gap_to_pwl_pct', 'overnight_move_pct', 'mom_3d', 'volatility_5d']
    
    # Drop rows with NaN features (usually the first few days)
    df = df.dropna(subset=features)
    
    # 2. Chronological Split (approx 85% Train, 15% Test)
    split_idx = int(len(df) * 0.85)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    print(f"Training on: {train_df['Date'].min().date()} to {train_df['Date'].max().date()}")
    print(f"Testing on: {test_df['Date'].min().date()} to {test_df['Date'].max().date()}")

    # --- MODEL 1: BREACH PROBABILITY ---
    X_train_1 = train_df[features]
    y_train_1 = train_df['target_1_breach']
    X_test_1 = test_df[features]
    y_test_1 = test_df['target_1_breach']

    model_1 = xgb.XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
    model_1.fit(X_train_1, y_train_1)
    
    # --- MODEL 2: FOLLOW-THROUGH (Condition: Breach happened) ---
    train_breaches = train_df[train_df['target_1_breach'] == 1].dropna(subset=['target_2_fall'])
    test_breaches = test_df[test_df['target_1_breach'] == 1].dropna(subset=['target_2_fall'])
    
    X_train_2 = train_breaches[features]
    y_train_2 = train_breaches['target_2_fall']
    X_test_2 = test_breaches[features]
    y_test_2 = test_breaches['target_2_fall']

    model_2 = xgb.XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
    model_2.fit(X_train_2, y_train_2)

    # --- MODEL 3: EV / RISK-REWARD (Condition: Breach happened) ---
    train_ev = train_df[train_df['target_1_breach'] == 1].dropna(subset=['target_3_ev'])
    test_ev = test_df[test_df['target_1_breach'] == 1].dropna(subset=['target_3_ev'])
    
    X_train_3 = train_ev[features]
    y_train_3 = train_ev['target_3_ev']
    X_test_3 = test_ev[features]
    y_test_3 = test_ev['target_3_ev']

    model_3 = xgb.XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
    model_3.fit(X_train_3, y_train_3)

    # 3. Save Models
    model_1.save_model("model_target_1_breach.json")
    model_2.save_model("model_target_2_fall.json")
    model_3.save_model("model_target_3_ev.json")
    print("\nModels saved to disk.")

    # 4. Evaluation Report
    report = []
    
    def evaluate(model, X, y, name):
        preds = model.predict(X)
        probs = model.predict_proba(X)[:, 1]
        acc = accuracy_score(y, preds)
        auc = roc_auc_score(y, probs)
        return {"Target": name, "Accuracy": acc, "ROC-AUC": auc, "Sample Size": len(y)}

    report.append(evaluate(model_1, X_test_1, y_test_1, "T1: Breach Probability"))
    report.append(evaluate(model_2, X_test_2, y_test_2, "T2: 2% Follow-through"))
    report.append(evaluate(model_3, X_test_3, y_test_3, "T3: Win/Loss Race"))

    print("\n--- MODEL PERFORMANCE REPORT (TEST SET) ---")
    report_df = pd.DataFrame(report)
    print(report_df.to_string(index=False))

if __name__ == "__main__":
    train_and_save_models('mvp_features_targets.csv')
