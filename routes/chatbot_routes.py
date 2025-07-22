from flask import Blueprint, request, jsonify, current_app as app
from pymongo import MongoClient
import time

chatbot_bp = Blueprint('chatbot', __name__)

@chatbot_bp.route('/chatbot', methods=['POST'])
def chatbot_reply():
    start_time = time.time()

    data = request.json
    user_message = data.get('message')
    patient_id = data.get('patient_id')

    # ✅ MongoDB에서 환자 진료 기록 조회
    mongo_client = app.extensions.get("mongo_client")
    db = mongo_client.get_collection("inference_results")
    record = db.find_one({"user_id": patient_id})

    record_text = f"환자 기록: {record}" if record else "환자 기록 없음"

    # ✅ 이미 초기화된 Gemini 모델 사용
    gemini_model = app.extensions.get("gemini_model")
    chat = gemini_model.start_chat()

    prompt = f"""
    환자 기록은 다음과 같습니다:\n{record_text}\n\n
    환자가 다음과 같은 질문을 했습니다:\n"{user_message}"\n
    이에 대해 친절하게 설명해주세요.
    """

    response = chat.send_message(prompt)
    reply = response.text

    elapsed_time = round(time.time() - start_time, 2)
    app.logger.info(f"[⏱️ chatbot_reply] 응답 시간: {elapsed_time}초")
    print(f"[⏱️ chatbot_reply] 응답 시간: {elapsed_time}초")

    return jsonify({'response': reply, 'elapsed_time': elapsed_time})
