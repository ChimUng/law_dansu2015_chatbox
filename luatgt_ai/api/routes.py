from fastapi import APIRouter, HTTPException, Depends
from schemas.question import Question
from schemas.response import Response
from services.rag_service import find_relevant_laws
from services.ai_service import get_gemini_response
from controllers.chat import *
from dependencies.auth import get_current_user
from services.scope_service import QueryScope, classify_query, out_of_scope_message

router = APIRouter()

@router.post("/api/chat", response_model=Response)
async def ask_question(question: Question, user=Depends(get_current_user)):
    if not question.message.strip():
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống!")

    if user is not None:
        save_question(user.id, question.message)
    
    decision = classify_query(question.message)
    if decision.scope == QueryScope.OUT_OF_SCOPE:
        relevant_laws = []
        answer = out_of_scope_message()
    else:
        relevant_laws = find_relevant_laws(
            question.message,
            include_auxiliary_traffic=decision.use_auxiliary_traffic,
        )
        answer = get_gemini_response(question.message, relevant_laws)
    
    answer_relevant_laws = [
            {
                "article": law["article"],
                "content": law["content"],
                "similarity_score": law["similarity"],
                "corpus_id": law.get("corpus_id"),
                "source_name": law.get("source_name"),
                "document_id": law.get("document_id"),
            }
            for law in relevant_laws
        ]

    if user is not None:
        save_answer(user.id, answer, answer_relevant_laws)
    
    response = {
        "question": question.message,
        "answer": answer,
        "relevant_laws": [
            {
                "article": law["article"],
                "content": law["content"],
                "similarity_score": law["similarity"],
                "corpus_id": law.get("corpus_id"),
                "source_name": law.get("source_name"),
                "document_id": law.get("document_id"),
            }
            for law in relevant_laws
        ],
        "scope": decision.scope.value,
    }
    return response


@router.get("/api/health")
async def health_check():
    """A lightweight endpoint for local setup and deployment diagnostics."""
    return {"status": "ok", "service": "civil-law-rag"}
