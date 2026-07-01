import os
from pathlib import Path
import xml.etree.ElementTree as ET

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
DATA_GO_KR_SERVICE_KEY = os.getenv("DATA_GO_KR_SERVICE_KEY")


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

@app.get("/api/hira/nonpayment-item-codes")
def hira_nonpayment_item_codes(
    keyword: str = Query("임플란트"),
    max_pages: int = Query(20)
):
    if not DATA_GO_KR_SERVICE_KEY:
        raise HTTPException(
            status_code=500,
            detail="DATA_GO_KR_SERVICE_KEY가 .env에서 로드되지 않았습니다."
        )

    url = "https://apis.data.go.kr/B551182/nonPaymentDamtInfoService/getNonPaymentItemCodeList"

    matched_items = []
    raw_count = 0

    for page in range(1, max_pages + 1):
        params = {
            "ServiceKey": DATA_GO_KR_SERVICE_KEY,
            "pageNo": page,
            "numOfRows": 100
        }

        try:
            response = requests.get(
                url,
                params=params,
                timeout=15
            )
        except requests.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"HIRA 비급여 항목코드 API 요청 중 네트워크 오류 발생: {str(e)}"
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail={
                    "message": "HIRA 비급여 항목코드 API 호출 실패",
                    "status_code": response.status_code,
                    "response_text": response.text[:1000]
                }
            )

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "HIRA 응답 XML 파싱 실패",
                    "response_text": response.text[:1000]
                }
            )

        result_code = root.findtext(".//resultCode")
        result_msg = root.findtext(".//resultMsg")

        if result_code and result_code not in ["00", "0"]:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "HIRA API 오류 응답",
                    "result_code": result_code,
                    "result_msg": result_msg,
                    "response_text": response.text[:1000]
                }
            )

        items = root.findall(".//item")

        if not items:
            break

        for item in items:
            raw_count += 1

            parsed = {
                child.tag: child.text
                for child in list(item)
            }

            searchable_text = " ".join(
                str(value)
                for value in parsed.values()
                if value
            )

            if keyword in searchable_text:
                matched_items.append(parsed)

        total_count_text = root.findtext(".//totalCount")

        try:
            total_count = int(total_count_text) if total_count_text else None
        except ValueError:
            total_count = None

        if total_count is not None and page * 100 >= total_count:
            break

    return {
        "keyword": keyword,
        "raw_checked_count": raw_count,
        "matched_count": len(matched_items),
        "items": matched_items
    }
@app.get("/api/hira/implant-prices-by-hospital")
def hira_implant_prices_by_hospital(
    hospital_name: str = Query(...),
    item_code: str = Query("H1100"),
    sido_cd: str = Query(None),
    sggu_cd: str = Query(None),
    max_pages: int = Query(10)
):
    if not DATA_GO_KR_SERVICE_KEY:
        raise HTTPException(
            status_code=500,
            detail="DATA_GO_KR_SERVICE_KEY가 .env에서 로드되지 않았습니다."
        )

    url = "https://apis.data.go.kr/B551182/nonPaymentDamtInfoService/getNonPaymentItemHospDtlList"

    matched_items = []
    raw_items = []
    total_count = None

    for page in range(1, max_pages + 1):
        params = {
            "ServiceKey": DATA_GO_KR_SERVICE_KEY,
            "pageNo": page,
            "numOfRows": 100,
            "yadmNm": hospital_name
        }

        if sido_cd:
            params["sidoCd"] = sido_cd

        if sggu_cd:
            params["sgguCd"] = sggu_cd

        try:
            response = requests.get(
                url,
                params=params,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )
        except requests.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"HIRA 의원별 비급여 API 요청 중 네트워크 오류 발생: {str(e)}"
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail={
                    "message": "HIRA 의원별 비급여 API 호출 실패",
                    "status_code": response.status_code,
                    "response_text": response.text[:1000]
                }
            )

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "HIRA 응답 XML 파싱 실패",
                    "response_text": response.text[:1000]
                }
            )

        result_code = root.findtext(".//resultCode")
        result_msg = root.findtext(".//resultMsg")

        if result_code and result_code not in ["00", "0"]:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "HIRA API 오류 응답",
                    "result_code": result_code,
                    "result_msg": result_msg,
                    "response_text": response.text[:1000]
                }
            )

        total_count_text = root.findtext(".//totalCount")

        try:
            total_count = int(total_count_text) if total_count_text else None
        except ValueError:
            total_count = None

        items = root.findall(".//item")

        if not items:
            break

        for item in items:
            parsed = {
                child.tag: child.text
                for child in list(item)
            }

            raw_items.append(parsed)

            npay_cd = parsed.get("npayCd") or ""
            npay_kor_nm = parsed.get("npayKorNm") or ""
            yadm_npay_cd_nm = parsed.get("yadmNpayCdNm") or ""

            searchable_text = " ".join([
                npay_cd,
                npay_kor_nm,
                yadm_npay_cd_nm
            ])

            is_implant_item = (
                item_code in searchable_text
                or "임플란트" in searchable_text
                or "치과임플란트" in searchable_text
            )

            if is_implant_item:
                matched_items.append({
                    "hospital_name": parsed.get("yadmNm"),
                    "hospital_type_code": parsed.get("clCd"),
                    "hospital_type_name": parsed.get("clCdNm"),
                    "sido_code": parsed.get("sidoCd"),
                    "sido_name": parsed.get("sidoCdNm"),
                    "sggu_code": parsed.get("sgguCd"),
                    "sggu_name": parsed.get("sgguCdNm"),
                    "nonpayment_code": parsed.get("npayCd"),
                    "nonpayment_name": parsed.get("npayKorNm"),
                    "hospital_nonpayment_name": parsed.get("yadmNpayCdNm"),
                    "current_amount": parse_int_or_none(parsed.get("curAmt")),
                    "current_amount_text": parsed.get("curAmt"),
                    "start_date": parsed.get("adtFrDd"),
                    "end_date": parsed.get("adtEndDd"),
                    "url": parsed.get("urlAddr"),
                    "raw": parsed
                })

        if total_count is not None and page * 100 >= total_count:
            break

    prices = [
        item["current_amount"]
        for item in matched_items
        if item.get("current_amount") is not None
    ]

    summary = None

    if prices:
        sorted_prices = sorted(prices)
        price_count = len(sorted_prices)

        if price_count % 2 == 1:
            median_price = sorted_prices[price_count // 2]
        else:
            median_price = (
                sorted_prices[price_count // 2 - 1] +
                sorted_prices[price_count // 2]
            ) / 2

        summary = {
            "price_count": price_count,
            "min_price": min(sorted_prices),
            "max_price": max(sorted_prices),
            "avg_price": round(sum(sorted_prices) / price_count),
            "median_price": round(median_price)
        }

    return {
        "hospital_name_query": hospital_name,
        "item_code": item_code,
        "total_count": total_count,
        "raw_count": len(raw_items),
        "matched_count": len(matched_items),
        "summary": summary,
        "items": matched_items
    }


def parse_int_or_none(value):
    if value is None:
        return None

    try:
        return int(str(value).replace(",", "").strip())
    except ValueError:
        return None
    
@app.get("/api/hira/implant-hospital-search")
def hira_implant_hospital_search(
    sido_cd: str = Query("110000"),
    sggu_cd: str = Query(None),
    hospital_keyword: str = Query(None),
    item_code: str = Query("H1100"),
    max_pages: int = Query(30)
):
    if not DATA_GO_KR_SERVICE_KEY:
        raise HTTPException(
            status_code=500,
            detail="DATA_GO_KR_SERVICE_KEY가 .env에서 로드되지 않았습니다."
        )

    url = "https://apis.data.go.kr/B551182/nonPaymentDamtInfoService/getNonPaymentItemHospDtlList"

    matched_items = []
    raw_items = []
    total_count = None

    normalized_keyword = normalize_text(hospital_keyword) if hospital_keyword else None

    for page in range(1, max_pages + 1):
        params = {
            "ServiceKey": DATA_GO_KR_SERVICE_KEY,
            "pageNo": page,
            "numOfRows": 100,
            "sidoCd": sido_cd
        }

        if sggu_cd:
            params["sgguCd"] = sggu_cd

        try:
            response = requests.get(
                url,
                params=params,
                timeout=20,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )
        except requests.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"HIRA 임플란트 병원검색 API 요청 중 네트워크 오류 발생: {str(e)}"
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail={
                    "message": "HIRA 임플란트 병원검색 API 호출 실패",
                    "status_code": response.status_code,
                    "response_text": response.text[:1000]
                }
            )

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "HIRA 응답 XML 파싱 실패",
                    "response_text": response.text[:1000]
                }
            )

        result_code = root.findtext(".//resultCode")
        result_msg = root.findtext(".//resultMsg")

        if result_code and result_code not in ["00", "0"]:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "HIRA API 오류 응답",
                    "result_code": result_code,
                    "result_msg": result_msg,
                    "response_text": response.text[:1000]
                }
            )

        total_count_text = root.findtext(".//totalCount")

        try:
            total_count = int(total_count_text) if total_count_text else None
        except ValueError:
            total_count = None

        items = root.findall(".//item")

        if not items:
            break

        for item in items:
            parsed = {
                child.tag: child.text
                for child in list(item)
            }

            raw_items.append(parsed)

            yadm_nm = parsed.get("yadmNm") or ""
            npay_cd = parsed.get("npayCd") or ""
            npay_kor_nm = parsed.get("npayKorNm") or ""
            yadm_npay_cd_nm = parsed.get("yadmNpayCdNm") or ""

            searchable_item_text = " ".join([
                npay_cd,
                npay_kor_nm,
                yadm_npay_cd_nm
            ])

            is_implant_item = (
                item_code in searchable_item_text
                or "임플란트" in searchable_item_text
                or "치과임플란트" in searchable_item_text
            )

            if not is_implant_item:
                continue

            if normalized_keyword:
                normalized_hospital_name = normalize_text(yadm_nm)

                if normalized_keyword not in normalized_hospital_name:
                    continue

            matched_items.append({
                "hospital_name": parsed.get("yadmNm"),
                "hospital_type_code": parsed.get("clCd"),
                "hospital_type_name": parsed.get("clCdNm"),
                "sido_code": parsed.get("sidoCd"),
                "sido_name": parsed.get("sidoCdNm"),
                "sggu_code": parsed.get("sgguCd"),
                "sggu_name": parsed.get("sgguCdNm"),
                "nonpayment_code": parsed.get("npayCd"),
                "nonpayment_name": parsed.get("npayKorNm"),
                "hospital_nonpayment_name": parsed.get("yadmNpayCdNm"),
                "current_amount": parse_int_or_none(parsed.get("curAmt")),
                "current_amount_text": parsed.get("curAmt"),
                "start_date": parsed.get("adtFrDd"),
                "end_date": parsed.get("adtEndDd"),
                "url": parsed.get("urlAddr"),
                "raw": parsed
            })

        if total_count is not None and page * 100 >= total_count:
            break

    prices = [
        item["current_amount"]
        for item in matched_items
        if item.get("current_amount") is not None
    ]

    summary = build_price_summary(prices)

    return {
        "sido_cd": sido_cd,
        "sggu_cd": sggu_cd,
        "hospital_keyword": hospital_keyword,
        "item_code": item_code,
        "total_count": total_count,
        "raw_count": len(raw_items),
        "matched_count": len(matched_items),
        "summary": summary,
        "items": matched_items[:200]
    }

def normalize_text(value):
    if value is None:
        return ""

    remove_words = [
        "의료법인",
        "재단법인",
        "학교법인",
        "사회복지법인",
        "치과의원",
        "치과병원",
        "의원",
        "병원",
        "강남점",
        "역삼점",
        "서울",
        "주식회사",
        "(주)",
        " ",
        "(",
        ")",
        "-",
        "_",
        "."
    ]

    text = str(value).lower().strip()

    for word in remove_words:
        text = text.replace(word.lower(), "")

    return text


def build_price_summary(prices):
    valid_prices = [
        price
        for price in prices
        if price is not None
    ]

    if not valid_prices:
        return None

    sorted_prices = sorted(valid_prices)
    count = len(sorted_prices)

    if count % 2 == 1:
        median_price = sorted_prices[count // 2]
    else:
        median_price = (
            sorted_prices[count // 2 - 1] +
            sorted_prices[count // 2]
        ) / 2

    return {
        "price_count": count,
        "min_price": min(sorted_prices),
        "max_price": max(sorted_prices),
        "avg_price": round(sum(sorted_prices) / count),
        "median_price": round(median_price)
    }

def parse_int_or_none(value):
    if value is None:
        return None

    try:
        return int(str(value).replace(",", "").strip())
    except ValueError:
        return None