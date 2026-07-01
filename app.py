import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

app = FastAPI()

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_JAVASCRIPT_KEY = os.getenv("KAKAO_JAVASCRIPT_KEY")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "kakao_js_key": KAKAO_JAVASCRIPT_KEY
        }
    )


@app.get("/debug/env")
def debug_env():
    return {
        "KAKAO_REST_API_KEY_loaded": bool(KAKAO_REST_API_KEY),
        "KAKAO_REST_API_KEY_preview": KAKAO_REST_API_KEY[:6] + "..." if KAKAO_REST_API_KEY else None,
        "KAKAO_JAVASCRIPT_KEY_loaded": bool(KAKAO_JAVASCRIPT_KEY),
        "KAKAO_JAVASCRIPT_KEY_preview": KAKAO_JAVASCRIPT_KEY[:6] + "..." if KAKAO_JAVASCRIPT_KEY else None,
    }


@app.get("/api/geocode")
def geocode(address: str = Query(...)):
    if not KAKAO_REST_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="KAKAO_REST_API_KEY가 .env에서 로드되지 않았습니다."
        )

    url = "https://dapi.kakao.com/v2/local/search/address.json"

    headers = {
        "Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"
    }

    params = {
        "query": address
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10
        )
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"카카오 API 요청 중 네트워크 오류 발생: {str(e)}"
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail={
                "message": "카카오 주소 검색 API 호출 실패",
                "status_code": response.status_code,
                "response_text": response.text
            }
        )

    data = response.json()
    documents = data.get("documents", [])

    if not documents:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "주소 검색 결과가 없습니다.",
                "address": address,
                "kakao_response": data
            }
        )

    first = documents[0]

    return {
        "input_address": address,
        "x": first.get("x"),  # 경도
        "y": first.get("y"),  # 위도
        "address_name": first.get("address_name"),
        "road_address": first.get("road_address"),
        "address": first.get("address")
    }

@app.get("/api/address-suggest")
def address_suggest(query: str = Query(...)):
    if not KAKAO_REST_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="KAKAO_REST_API_KEY가 .env에서 로드되지 않았습니다."
        )

    url = "https://dapi.kakao.com/v2/local/search/address.json"

    headers = {
        "Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"
    }

    params = {
        "query": query,
        "analyze_type": "similar",
        "size": 10
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10
        )
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"카카오 주소 제안 API 요청 중 네트워크 오류 발생: {str(e)}"
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail={
                "message": "카카오 주소 제안 API 호출 실패",
                "status_code": response.status_code,
                "response_text": response.text
            }
        )

    data = response.json()

    suggestions = []

    for item in data.get("documents", []):
        road_address = item.get("road_address")
        jibun_address = item.get("address")

        suggestions.append({
            "address_name": item.get("address_name"),
            "road_address_name": road_address.get("address_name") if road_address else None,
            "jibun_address_name": jibun_address.get("address_name") if jibun_address else None,
            "x": item.get("x"),
            "y": item.get("y")
        })

    return {
        "query": query,
        "count": len(suggestions),
        "suggestions": suggestions
    }

@app.get("/api/nearby-dentists")
def nearby_dentists(
    x: float = Query(...),  # 경도
    y: float = Query(...),  # 위도
    radius: int = Query(500)
):
    if not KAKAO_REST_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="KAKAO_REST_API_KEY가 .env에서 로드되지 않았습니다."
        )

    url = "https://dapi.kakao.com/v2/local/search/keyword.json"

    headers = {
        "Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"
    }

    raw_results = []
    dentists = []
    excluded = []
    seen = set()

    # 카카오 Local API는 한 페이지당 최대 15개라서 우선 3페이지까지 조회
    for page in range(1, 4):
        params = {
            "query": "치과",
            "x": x,
            "y": y,
            "radius": radius,
            "sort": "distance",
            "page": page,
            "size": 15
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=10
            )
        except requests.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"카카오 주변 치과 검색 API 요청 중 네트워크 오류 발생: {str(e)}"
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail={
                    "message": "카카오 주변 치과 검색 API 호출 실패",
                    "status_code": response.status_code,
                    "response_text": response.text
                }
            )

        data = response.json()
        documents = data.get("documents", [])

        for item in documents:
            raw_results.append(item)

            place = {
                "place_name": item.get("place_name"),
                "address_name": item.get("address_name"),
                "road_address_name": item.get("road_address_name"),
                "phone": item.get("phone"),
                "x": item.get("x"),
                "y": item.get("y"),
                "distance": item.get("distance"),
                "place_url": item.get("place_url"),
                "category_name": item.get("category_name")
            }

            category_name = item.get("category_name") or ""

            # 순수 치과 카테고리만 포함
            is_dental_clinic = "의료,건강 > 병원 > 치과" in category_name

            # 중복 제거 기준
            unique_key = (
                item.get("place_name"),
                item.get("road_address_name") or item.get("address_name")
            )

            if is_dental_clinic and unique_key not in seen:
                dentists.append(place)
                seen.add(unique_key)
            else:
                excluded.append(place)

        meta = data.get("meta", {})
        if meta.get("is_end"):
            break

    return {
        "center": {
            "x": x,
            "y": y
        },
        "radius": radius,
        "raw_count": len(raw_results),
        "filtered_count": len(dentists),
        "excluded_count": len(excluded),
        "dentists": dentists,
        "excluded": excluded
    }

    # 카카오 Local API는 한 페이지당 최대 15개라서 3페이지까지 조회
    for page in range(1, 4):
        params = {
            "query": "치과",
            "x": x,
            "y": y,
            "radius": radius,
            "sort": "distance",
            "page": page,
            "size": 15
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=10
            )
        except requests.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"카카오 주변 치과 검색 API 요청 중 네트워크 오류 발생: {str(e)}"
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail={
                    "message": "카카오 주변 치과 검색 API 호출 실패",
                    "status_code": response.status_code,
                    "response_text": response.text
                }
            )

        data = response.json()
        documents = data.get("documents", [])

        for item in documents:
            dentists.append({
                "place_name": item.get("place_name"),
                "address_name": item.get("address_name"),
                "road_address_name": item.get("road_address_name"),
                "phone": item.get("phone"),
                "x": item.get("x"),
                "y": item.get("y"),
                "distance": item.get("distance"),
                "place_url": item.get("place_url"),
                "category_name": item.get("category_name")
            })

        meta = data.get("meta", {})
        if meta.get("is_end"):
            break

    return {
        "center": {
            "x": x,
            "y": y
        },
        "radius": radius,
        "count": len(dentists),
        "dentists": dentists
    }