from fastapi import APIRouter, Depends, HTTPException, status

from ...engine import BaseEngine
from ..dependencies import get_engine
from ..models.schemas import DocumentInput, DocumentResponse

router = APIRouter()


@router.post(
    "/",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add documents to the RAG system"
)
async def add_documents(
    input_data: DocumentInput,
    engine: BaseEngine = Depends(get_engine)
):
    if not input_data.documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No documents provided"
        )

    try:
        await engine.add_documents(input_data.documents)
        return {
            "status": "success",
            "message": f"Added {len(input_data.documents)} documents",
            "count": len(input_data.documents)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add documents: {str(e)}"
        )
