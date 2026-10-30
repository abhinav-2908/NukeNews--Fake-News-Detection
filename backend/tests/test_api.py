from fastapi.testclient import TestClient
import app.services.analyzer as analyzer
from app.main import app

async def no_sources(_query):
    return []

async def no_llm(*_args):
    return None

def test_health_and_local_analysis(monkeypatch):
    monkeypatch.setattr(analyzer, "search", no_sources)
    monkeypatch.setattr(analyzer, "verify", no_llm)
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        models = client.get("/api/models").json()
        assert models["classifier"] == "ready"
        result = client.post("/api/analyze/text", json={"title":"", "text":"This is a sufficiently long news claim for analysis."})
        assert result.status_code == 200
        body = result.json()
        assert body["verdict"] == "INCONCLUSIVE"
        assert body["classifier"]["status"] == "ready"
        assert body["limitations"]
        assert client.get("/api/history").status_code == 200

def test_image_text_can_be_previewed_then_submitted(monkeypatch):
    from io import BytesIO
    from PIL import Image, ImageDraw
    monkeypatch.setattr(analyzer, "search", no_sources)
    monkeypatch.setattr(analyzer, "verify", no_llm)
    image=Image.new('RGB',(900,180),'white')
    ImageDraw.Draw(image).text((25,50),'Fact check this important news report',fill='black')
    buffer=BytesIO(); image.save(buffer,format='PNG')
    with TestClient(app) as client:
        extracted=client.post('/api/extract/image',files={'file':('news.png',buffer.getvalue(),'image/png')})
        assert extracted.status_code==200
        preview=extracted.json()
        assert 'important' in preview['text'].lower()
        result=client.post('/api/analyze/text',json={'text':preview['text'],'input_type':'image','extraction':preview['extraction']})
        assert result.status_code==200
        assert result.json()['input_type']=='image'
