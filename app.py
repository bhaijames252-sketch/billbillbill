from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.config import engine
from models.mysql_models import Base
from routes.price_routes import router as price_router
from routes.wallet_routes import router as wallet_router
from routes.resource_routes import router as resource_router
from routes.billing_routes import router as billing_router

app = FastAPI(
    title="BillingCloud API",
    description="Cloud Billing Engine API - Manage pricing, wallets, resources and billing",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning: Failed to create tables: {e}")

app.include_router(price_router, prefix="/api/v1")
app.include_router(wallet_router, prefix="/api/v1")
app.include_router(resource_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "healthy", "service": "billingcloud"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
