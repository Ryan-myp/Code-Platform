import uvicorn
from fastapi import FastAPI

app = FastAPI(title="My App", description="沙箱测试应用")


@app.get("/")
def root():
    return {"message": "Hello from My App!", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/test")
def test_endpoint():
    return {"result": "success"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
