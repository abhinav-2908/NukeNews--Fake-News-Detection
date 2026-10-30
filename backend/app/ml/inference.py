from pathlib import Path
import joblib
from app.core.config import settings

class Classifier:
    def __init__(self):
        self.pipeline = None
        path = (Path(__file__).resolve().parents[3] / settings.model_path).resolve()
        if path.exists():
            try: self.pipeline = joblib.load(path)
            except Exception: self.pipeline = None
    def predict(self, text: str) -> dict:
        if self.pipeline is None:
            return {"status":"unavailable", "prediction":None, "probabilities":None, "model_version":None,
                    "message":"No trained model found. Add ISOT CSVs and run scripts/train.py."}
        try:
            predicted = int(self.pipeline.predict([text])[0])
            names = {1:"REAL", 0:"FAKE"}
            probs = self.pipeline.predict_proba([text])[0].tolist() if hasattr(self.pipeline,"predict_proba") else None
            classes = getattr(self.pipeline,"classes_",[])
            return {"status":"ready", "prediction":names.get(predicted,"UNKNOWN"),
                    "probabilities":{names.get(int(c),str(c)):float(p) for c,p in zip(classes,probs)} if probs else None,
                    "model_version":"selected-joblib"}
        except Exception as exc:
            return {"status":"error", "prediction":None, "probabilities":None, "message":str(exc)}
classifier = Classifier()
