import joblib
import pandas as pd

model = joblib.load("model/logistic_model.pkl")
scaler = joblib.load("model/scaler.pkl")
label_encoders = joblib.load("model/label_encoders.pkl")

categorical_cols = ['job', 'marital', 'education', 'default', 'housing',
                    'loan', 'contact', 'month', 'day_of_week', 'poutcome']

def predict_output(input_dict):
    df = pd.DataFrame([input_dict])

    for col in categorical_cols:
        le = label_encoders[col]
        df[col] = le.transform(df[col].astype(str))

    X_scaled = scaler.transform(df)
    pred = model.predict(X_scaled)[0]
    return pred