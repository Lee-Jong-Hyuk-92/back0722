import os
# from vertexai.preview.generative_models import GenerativeModel, Part # 이제 이 부분은 필요 없을 수도 있습니다.
import vertexai # vertexai.init()을 위해 유지
from google.cloud import aiplatform # ⭐ 이 줄을 추가합니다. aiplatform 모듈을 직접 임포트합니다.
from PIL import Image
import io
from google.cloud import storage # Google Cloud Storage 클라이언트
import json # JSON 직렬화를 위해 유지
# from google.cloud.aiplatform_v1beta1.types import Endpoint # 타입 힌트용이므로 제거해도 무방합니다.

# ✅ 환경변수로 GCP 인증 키 등록
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\302-1\Desktop\backend0709-1\meditooth-7ce9efd0794b.json"

# ✅ GCP 프로젝트 설정
PROJECT_ID = "meditooth"
LOCATION = "us-central1" # MedGemma 엔드포인트가 배포된 리전

# ✅ Vertex AI 초기화
vertexai.init(project=PROJECT_ID, location=LOCATION)

# --- 새로운 MedGemma 엔드포인트 연결 방식 ---
# ⭐ 1. MedGemma 모델이 배포된 엔드포인트 ID를 입력합니다.
# 사용자님이 제공한 스크린샷에서 확인된 엔드포인트 ID입니다.
MEDGEMMA_ENDPOINT_ID = "7198930337072676864"  # ← ✅ 이게 스크린샷에서 확인된 실제 ID

# 엔드포인트 객체 로드 (Vertex AI SDK)
# aiplatform.Endpoint를 사용하려면 google-cloud-aiplatform 패키지가 필요합니다.
# pip install google-cloud-aiplatform
try:
    medgemma_endpoint = aiplatform.Endpoint( # ⭐ vertexai.Endpoint 대신 aiplatform.Endpoint 사용
        endpoint_name=MEDGEMMA_ENDPOINT_ID,
        project=PROJECT_ID,
        location=LOCATION,
    )
    print(f"Successfully connected to MedGemma Endpoint: {medgemma_endpoint.display_name}")
except Exception as e:
    print(f"Error connecting to MedGemma Endpoint: {e}")
    print("Please ensure you have deployed MedGemma to an endpoint in Vertex AI "
          "and replaced 'YOUR_MEDGEMMA_ENDPOINT_ID_HERE' with your actual endpoint ID.")
    exit() # 엔드포인트 연결 실패 시 스크립트 종료

# ✅ 이미지 파일을 GCS에 업로드하고 URL을 반환하는 함수
def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """GCS에 파일을 업로드하고 HTTP URL 반환"""
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    # 이미지를 896x896 JPEG로 리사이징 및 인코딩
    with Image.open(source_file_name) as img:
        img = img.resize((896, 896), Image.BICUBIC)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        image_bytes = img_byte_arr.getvalue()

    blob.upload_from_string(image_bytes, content_type='image/jpeg')

    # ⭐ blob을 공개로 설정 (필수)
    blob.make_public()

    # ✅ HTTP URL 반환
    return blob.public_url

# GCS 버킷 이름 (직접 생성하거나 기존 버킷 사용)
# ⭐ 중요한: 이 버킷은 MedGemma 모델과 동일한 리전 (us-central1)에 있어야 합니다!
GCS_BUCKET_NAME = "meditooth-medgemma-images-temp" # 이전에 사용한 이름과 겹치지 않게 변경했습니다.
GCS_IMAGE_DESTINATION_PATH = "oral_image_896x896.jpeg" # GCS에 저장될 파일 이름

# 로컬 이미지 경로 (사용자님이 제공한 이미지 파일 경로)
local_image_path = r"C:\Users\302-1\Desktop\backend0709-1\images\original\121212_20250721160844223601_web_image.png"

# 이미지를 GCS에 업로드하고 URL 가져오기
print(f"Uploading image to GCS bucket: {GCS_BUCKET_NAME}/{GCS_IMAGE_DESTINATION_PATH}")
try:
    gcs_image_url = upload_blob(GCS_BUCKET_NAME, local_image_path, GCS_IMAGE_DESTINATION_PATH)
    print(f"Image uploaded to: {gcs_image_url}")
except Exception as e:
    print(f"Error uploading image to GCS. Please ensure the bucket '{GCS_BUCKET_NAME}' exists in '{LOCATION}' region "
          f"and your service account has 'Storage Object Creator' role: {e}")
    exit()

# ✅ 프롬프트와 이미지 정의 (노트북에서 본 `messages` 형식 사용)
user_prompt = "이 환자의 구강 이미지를 분석해서 충치와 잇몸 질환 가능성을 설명해줘. 다른 AI 모델을 사용했을때 잇몸염증 초기, 치석단계2 라고 나왔어"
system_instruction = "당신은 구강 이미지 분석 전문 의사입니다. 매우 자세하게 설명해 주세요."

messages = [
    {
        "role": "system",
        "content": [{"type": "text", "text": system_instruction}]
    },
    {
        "role": "user",
        "content": [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": gcs_image_url}}
        ]
    }
]

# 예측 요청을 위한 `instances` 구조
instances = [
    {
        "@requestFormat": "chatCompletions",
        "messages": messages,
        "max_tokens": 1500, # 응답 길이를 적절히 설정 (노트북에서 500 또는 1500 사용)
        "temperature": 0.4 # 현재 코드와 동일하게 유지
    },
]

# ✅ MedGemma 요청 (엔드포인트 객체 사용)
print("\nGenerating content from MedGemma Endpoint...")
try:
    result = medgemma_endpoint.predict(instances=instances)

    # ✅ 응답 파싱
    response = result.predictions["choices"][0]["message"]["content"]

    print("🦷 분석 결과:")
    print(response)

except Exception as e:
    print(f"Error during prediction: {e}")
    print("Please check your MedGemma endpoint status and permissions.")