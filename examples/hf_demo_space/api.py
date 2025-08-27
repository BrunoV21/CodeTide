from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Request
from chainlit.utils import mount_chainlit
from pathlib import Path
import os

ROOT_PATH = os.getenv("API_ROOT_PATH", "./")
app = FastAPI(title="AgentTide", description="Precision-Driven Software Engineering Agent")

# Mount static files directory for assets (logo, CSS, JS, etc.)
app.mount("/static", StaticFiles(directory=F"{ROOT_PATH}/public"), name="static")

templates = Jinja2Templates(directory=F"{ROOT_PATH}/static")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):    
    """Serve the AgentTide landing page"""
    demo_base_url = os.getenv("DEMO_BASE_URL", "")
    return RedirectResponse(url=f"{demo_base_url}/landing_page")

@app.get("/landing_page", response_class=HTMLResponse)
async def landing_page(request: Request):    
    """Serve the AgentTide landing page"""
    demo_base_url = os.getenv("DEMO_BASE_URL", "")
    return templates.TemplateResponse(
        "landing_page.html", 
        {"request": request, "DEMO_BASE_URL": demo_base_url}
    )
    
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "AgentTide"}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon"""
    favicon_path = Path(F"{ROOT_PATH}/public/favicon.ico")
    if favicon_path.exists():
        return FileResponse(favicon_path)
    else:
        # Return 204 No Content if favicon doesn't exist
        return HTMLResponse(status_code=204)

@app.get("/logo_dark.png", include_in_schema=False)
async def logo_dark():
    """Serve favicon"""
    favicon_path = Path(F"{ROOT_PATH}/public/logo_dark.png")
    if favicon_path.exists():
        return FileResponse(favicon_path)
    else:
        # Return 204 No Content if favicon doesn't exist
        return HTMLResponse(status_code=204)

@app.get("/codetide-banner.png", include_in_schema=False)
async def codetide_banner():
    """Serve favicon"""
    favicon_path = Path(F"{ROOT_PATH}/public/codetide-banner.png")
    if favicon_path.exists():
        return FileResponse(favicon_path)
    else:
        # Return 204 No Content if favicon doesn't exist
        return HTMLResponse(status_code=204)

@app.get("/agent-tide-demo.gif", include_in_schema=False)
async def agent_tide_deo_gif():
    """Serve favicon"""
    favicon_path = Path(F"{ROOT_PATH}/public/agent-tide-demo.gif")
    if favicon_path.exists():
        return FileResponse(favicon_path)
    else:
        # Return 204 No Content if favicon doesn't exist
        return HTMLResponse(status_code=204)

mount_chainlit(app=app, target=F"{ROOT_PATH}/app.py", path="/tide")

if __name__ == "__main__":
    from dotenv import load_dotenv
    import uvicorn

    load_dotenv()
    uvicorn.run(app, host="0.0.0.0", port=7860)
