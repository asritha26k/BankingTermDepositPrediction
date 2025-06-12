# app/model.py
import joblib
import pandas as pd
import os
from pathlib import Path

# --- Define paths ---
CURRENT_SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_ASSETS_DIR = CURRENT_SCRIPT_DIR.parent / "model"
FULL_PIPELINE_PATH = MODEL_ASSETS_DIR / "full_pipeline.pkl" # Using the full pipeline

# --- Load the actual, pre-trained model pipeline ---
try:
    full_pipeline = joblib.load(FULL_PIPELINE_PATH)
    print(f"ML Full Pipeline loaded successfully from '{FULL_PIPELINE_PATH}'.")
except FileNotFoundError:
    print("FATAL ERROR: full_pipeline.pkl not found.")
    print("Please ensure your pre-trained full_pipeline.pkl is in the /model directory.")
    full_pipeline = None
except Exception as e:
    print(f"An unexpected error occurred while loading the full pipeline: {e}")
    raise RuntimeError(f"Failed to load ML full pipeline: {e}")

# --- No need for NUMERIC_COLS, CATEGORICAL_COLS_FOR_GET_DUMMIES, TRAINING_COLUMNS as separate lists now ---
# The pipeline handles all internal feature management.

# --- Prediction Function ---
def predict_with_pipeline(input_df: pd.DataFrame):
    """
    Makes predictions using the loaded full ML pipeline.
    """
    if full_pipeline is None:
        raise RuntimeError("ML Full Pipeline is not loaded. Cannot perform prediction.")

    # The full_pipeline expects raw input features.
    # No manual get_dummies, reindex, or scaling needed here.
    # The pipeline handles it all internally.

    print(f"\nDEBUG (predict): Input DataFrame columns entering predict_with_pipeline: {input_df.columns.tolist()}")
    print(f"DEBUG (predict): Input DataFrame dtypes before prediction:\n{input_df.dtypes}")
    print(f"DEBUG (predict): Input DataFrame shape before prediction: {input_df.shape}")

    try:
        predictions = full_pipeline.predict(input_df)
        probabilities = full_pipeline.predict_proba(input_df)[:, 1]

        print(f"DEBUG (predict): Prediction successful!")
        print(f"DEBUG (predict): Raw predictions: {predictions.tolist()}")
        print(f"DEBUG (predict): Probabilities: {probabilities.tolist()}")

    except Exception as e:
        print(f"ERROR: Failed during full_pipeline.predict(). Exact error: {e}")
        raise RuntimeError(f"Prediction failed with full pipeline: {e}")

    return predictions.tolist(), probabilities.tolist()