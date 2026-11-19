import asyncio
import json

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from schemas.question import Question
from schemas.response import Response
from services.rag_service import find_relevant_laws, retrieve_with_trace
from services.ai_service import get_gemini_response
from controllers.chat import *
from dependencies.auth import get_current_user
from services.scope_service import QueryScope, classify_query, out_of_scope_message

router = APIRouter()


def _law_payload(law: dict) -> dict:
    return {
        "article": law["article"],
        "content": law["content"],
        "similarity_score": law["similarity"],
        "corpus_id": law.get("corpus_id"),
        "source_name": law.get("source_name"),
        "document_id": law.get("document_id"),
    }


def _response_payload(question: Question, answer: str, relevant_laws: list[dict], decision, trace: dict | None) -> dict:
    return {
        "question": question.message,
        "answer": answer,
        "relevant_laws": [_law_payload(law) for law in relevant_laws],
        "scope": decision.scope.value,
        "retrieval_trace": trace,
    }


def _sse(event: str, payload: dict) -> str:
    """Encode a single Server-Sent Event without leaking provider details."""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

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
        retrieval_trace = {"scope": decision.scope.value, "final": []} if question.debug else None
    else:
        if question.debug:
            relevant_laws, retrieval_trace = retrieve_with_trace(
                question.message,
                include_auxiliary_traffic=decision.use_auxiliary_traffic,
            )
            retrieval_trace["scope"] = decision.scope.value
        else:
            relevant_laws = find_relevant_laws(
                question.message,
                include_auxiliary_traffic=decision.use_auxiliary_traffic,
            )
            retrieval_trace = None
        answer = get_gemini_response(question.message, relevant_laws)
    
    answer_relevant_laws = [_law_payload(law) for law in relevant_laws]

    if user is not None:
        save_answer(user.id, answer, answer_relevant_laws)
    
    return _response_payload(question, answer, relevant_laws, decision, retrieval_trace)


@router.post("/api/chat/stream")
async def ask_question_stream(question: Question, user=Depends(get_current_user)):
    """Stream truthful RAG milestones so the UI does not fake a progress bar."""
    if not question.message.strip():
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống!")

    async def event_stream():
        if user is not None:
            save_question(user.id, question.message)

        decision = classify_query(question.message)
        yield _sse("progress", {
            "step": "scope", "state": "completed", "detail": f"Phạm vi: {decision.scope.value}",
        })

        if decision.scope == QueryScope.OUT_OF_SCOPE:
            trace = {"scope": decision.scope.value, "final": []} if question.debug else None
            payload = _response_payload(question, out_of_scope_message(), [], decision, trace)
            yield _sse("final", payload)
            return

        yield _sse("progress", {
            "step": "retrieval", "state": "active", "detail": "Đang chạy keyword và semantic search",
        })
        relevant_laws, trace = await asyncio.to_thread(
            retrieve_with_trace,
            question.message,
            decision.use_auxiliary_traffic,
        )
        trace["scope"] = decision.scope.value
        yield _sse("progress", {
            "step": "retrieval", "state": "completed",
            "detail": f"Đã tìm {len(trace.get('keyword_phrase', []))} keyword và {len(trace.get('semantic_faiss', []))} semantic candidates",
        })
        yield _sse("progress", {
            "step": "ranking", "state": "completed", "detail": f"Đã chọn {len(relevant_laws)} nguồn pháp luật",
        })
        yield _sse("progress", {
            "step": "generation", "state": "active", "detail": "Đang tạo phần diễn giải có căn cứ",
        })
        answer = await asyncio.to_thread(get_gemini_response, question.message, relevant_laws)
        yield _sse("progress", {"step": "generation", "state": "completed", "detail": "Đã hoàn tất câu trả lời"})

        payload = _response_payload(question, answer, relevant_laws, decision, trace if question.debug else None)
        if user is not None:
            save_answer(user.id, answer, payload["relevant_laws"])
        yield _sse("final", payload)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/health")
async def health_check():
    """A lightweight endpoint for local setup and deployment diagnostics."""
    return {"status": "ok", "service": "civil-law-rag"}
