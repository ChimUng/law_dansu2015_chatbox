import logging
from typing import List
from core.config import settings


logger = logging.getLogger(__name__)

def get_gemini_response(question: str, relevant_laws: List[dict]) -> str:
    if not settings.GEMINI_API_KEY:
        return (
            "Đã tìm được các điều luật liên quan, nhưng máy chủ chưa cấu hình "
            "GEMINI_API_KEY để tạo phần diễn giải. Bạn vẫn có thể xem các nguồn bên dưới."
        )
    if not relevant_laws:
        return (
            "Rất tiếc, tôi không tìm thấy điều luật nào liên quan đến câu hỏi của bạn trong dữ liệu hiện tại. "
            "Bạn có thể tham khảo thêm tại https://thuvienphapluat.vn/van-ban/Quyen-dan-su/Bo-luat-dan-su-2015-296215.aspx"
        )
    
    laws_text = "\n".join(
        [f"- [{law.get('source_name', 'Nguồn pháp luật')}] {law['article']}: {law['content']}"
        for law in relevant_laws]
    )
    
    prompt = (
        "Giả sử bạn tên là Luật, một luật sư chuyên về luật dân sự Việt Nam với hơn 5 năm kinh nghiệm, hãy trả lời câu hỏi dựa trên các điều luật được tôi cung cấp dưới đây và không cần phải chào tôi hay giới thiệu về bạn. "
        "Cung cấp câu trả lời chính xác, ngắn gọn, dễ hiểu, đúng trọng tâm và chỉ dựa vào các điều luật liên quan. "
        "Phải nêu Điều luật và tên nguồn khi kết luận. Không dùng kiến thức bên ngoài các nguồn được cung cấp. "
        "Nếu nguồn không đủ để kết luận, hãy nói rõ giới hạn đó.\n\n"
        f"Câu hỏi: {question}\n\n"
        f"Điều luật liên quan:\n{laws_text}\n\n"
        "Trả lời:"
    )
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        ai_model = genai.GenerativeModel(settings.GEMINI_MODEL_NAME)
        response = ai_model.generate_content(prompt)
        return response.text.strip()
    except Exception as error:
        # Do not expose the API key to the browser. The terminal gets the
        # provider detail needed to diagnose a wrong model, key, or quota.
        logger.exception("Gemini generation failed: %s", error)
        return (
            "Đã tìm được điều luật liên quan, nhưng Gemini chưa tạo được phần "
            "diễn giải. Hãy xem nguồn bên dưới và kiểm tra lỗi Gemini ở terminal."
        )
