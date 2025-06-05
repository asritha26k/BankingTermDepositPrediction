from fastapi import FastAPI
from app.schemas import InputData
from app.model import predict_output

app = FastAPI()

@app.post("/predict")
def predict(data: InputData):
    prediction = predict_output(data.model_dump())
    return {"prediction": prediction}