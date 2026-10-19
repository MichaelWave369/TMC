from fastapi import FastAPI

from app.api.routes import router as api_router
from app.ui.routes import router as ui_router

app = FastAPI(title='TMC — Total Memory Core v1.0.0')
app.include_router(api_router, prefix='/api')
app.include_router(ui_router, prefix='/ui')


@app.get('/')
def root():
    return {'name': 'TMC — Total Memory Core', 'version': '1.0.0', 'owner': 'MichaelWave369', 'ui': '/ui', 'api': '/docs'}
