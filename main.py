from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class AnalyzeRequest(BaseModel):
    submission_id: str
    audio_url: str
    callback_url: str

@app.get("/")
def root():
    return {"status": "Casablanca Audio Engine Running"}

@app.post("/analyze")
async def analyze(payload: AnalyzeRequest):
    return {
        "submission_id": payload.submission_id,
        "status": "complete",
        "tempo": 100,
        "energy_score": 0.75
    }
