from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from api.router import router
from services.gcp import setup_logger
from services.firestore import get_firestore_client

logger = setup_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Initializing Application Startup")
    app.state.db = get_firestore_client()
    logger.info("Firestore client added to app state")
    logger.info(f"Successfully Completed Application Startup")
    
    yield
    logger.info("Application shutdown")

app = FastAPI(lifespan = lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error['loc'])  # Convert all items to strings
        message = error['msg']
        error_detail = f"Error in field '{field}': {message}"
        errors.append(error_detail)
        logger.error(error_detail)  # Log the error details

    # Log the incoming request details
    # logger.info(f"Incoming request: {request.method} {request.url}")

    return JSONResponse(
        status_code=422,
        content={"detail": errors}
    )

app.include_router(router)