import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import db, create_document, get_documents
from pydantic import BaseModel

import re
import uuid

app = FastAPI(title="OG Drawing Intelligence API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Oil & Gas Drawing Intelligence API is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = os.getenv("DATABASE_NAME") or "❌ Not Set"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# Simple in-app storage path (ephemeral). In real deployments, use object storage.
STORAGE_DIR = "./uploads"
os.makedirs(STORAGE_DIR, exist_ok=True)


# ---------- Utility extraction functions (deterministic MVP) ----------
TAG_PATTERN = re.compile(r"\b([A-Z]{1,3}-?\d{1,4}[A-Z]?)\b")  # e.g., P-101, V203, LT-101A


def guess_filetype(filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    mapping = {
        "pdf": "pdf", "dxf": "dxf", "dwg": "dwg", "tiff": "tiff",
        "tif": "tiff", "step": "step", "stp": "step", "ifc": "ifc",
        "obj": "obj", "nwd": "nwd", "nwc": "nwc"
    }
    return mapping.get(ext, "other")


# ---------- API Models ----------
class ProjectCreate(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    revision: Optional[str] = None


class DocumentRequest(BaseModel):
    project_id: str
    doc_type: str  # tag-index | bom | summary


# ---------- Endpoints ----------
@app.post("/api/projects")
def create_project(payload: ProjectCreate):
    project_id = create_document("project", payload)
    return {"project_id": project_id}


@app.get("/api/projects")
def list_projects():
    items = get_documents("project", {}, limit=100)
    # Normalize ObjectId to str if present (db helper returns raw docs)
    for it in items:
        if "_id" in it:
            it["_id"] = str(it["_id"])
    return {"projects": items}


@app.post("/api/uploads")
async def upload_file(
    project_id: str = Form(...),
    file: UploadFile = File(...)
):
    # Persist file to local storage
    fid = str(uuid.uuid4())
    safe_name = f"{fid}_{file.filename}"
    path = os.path.join(STORAGE_DIR, safe_name)
    with open(path, "wb") as f:
        f.write(await file.read())

    filetype = guess_filetype(file.filename)
    size_bytes = os.path.getsize(path)

    upload_doc = {
        "project_id": project_id,
        "filename": file.filename,
        "filepath": path,
        "filetype": filetype,
        "size_bytes": size_bytes,
    }
    upload_id = create_document("upload", upload_doc)

    # MVP extraction: scan filename for tag-like strings
    found_tags = TAG_PATTERN.findall(file.filename.upper())
    for tag in found_tags:
        item = {
            "project_id": project_id,
            "upload_id": upload_id,
            "kind": "tag",
            "label": tag,
            "attributes": {"source": "filename"},
            "page": None,
            "confidence": 0.4,
        }
        create_document("extractionitem", item)

    return {"upload_id": upload_id, "filetype": filetype, "size": size_bytes}


@app.get("/api/uploads")
def list_uploads(project_id: Optional[str] = None):
    filt: Dict[str, Any] = {"project_id": project_id} if project_id else {}
    items = get_documents("upload", filt, limit=200)
    for it in items:
        if "_id" in it:
            it["_id"] = str(it["_id"])
    return {"uploads": items}


@app.get("/api/extractions")
def list_extractions(project_id: Optional[str] = None):
    filt: Dict[str, Any] = {"project_id": project_id} if project_id else {}
    items = get_documents("extractionitem", filt, limit=1000)
    for it in items:
        if "_id" in it:
            it["_id"] = str(it["_id"])
    return {"items": items}


@app.post("/api/documents/generate")
def generate_document(req: DocumentRequest):
    # Aggregate extraction items for the project
    items = get_documents("extractionitem", {"project_id": req.project_id}, limit=5000)

    if req.doc_type == "tag-index":
        tags = sorted({it.get("label") for it in items if it.get("kind") == "tag" and it.get("label")})
        rows = [{"tag": t} for t in tags]
        draft = {
            "project_id": req.project_id,
            "doc_type": "tag-index",
            "title": "Tag Index (Draft)",
            "items": rows,
            "meta": {"count": len(rows)},
        }
        did = create_document("documentdraft", draft)
        return {"document_id": did, "document": draft}

    if req.doc_type == "bom":
        # naive BOM based on extracted 'bom' kind items (future enhancement)
        parts: Dict[str, int] = {}
        for it in items:
            if it.get("kind") == "bom" and it.get("label"):
                parts[it["label"]] = parts.get(it["label"], 0) + 1
        rows = [{"item": k, "qty": v} for k, v in sorted(parts.items())]
        draft = {
            "project_id": req.project_id,
            "doc_type": "bom",
            "title": "Bill of Materials (Draft)",
            "items": rows,
            "meta": {"line_items": len(rows)},
        }
        did = create_document("documentdraft", draft)
        return {"document_id": did, "document": draft}

    if req.doc_type == "summary":
        draft = {
            "project_id": req.project_id,
            "doc_type": "summary",
            "title": "Transmittal Summary (Draft)",
            "items": [],
            "meta": {},
        }
        did = create_document("documentdraft", draft)
        return {"document_id": did, "document": draft}

    raise HTTPException(status_code=400, detail="Unsupported doc_type")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
