from fastapi import FastAPI

app = FastAPI(
    title="Obsidian Portafolio API"
)

@app.get("/")
def read_root():
    return {
        "message": "Bienvenid@ a la API de Obsidian Portafolio",
        "status": "running"
    }
