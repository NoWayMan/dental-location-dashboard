let map;
let marker;
let circle;

let suggestionTimer = null;
let currentSuggestions = [];
let dentistMarkers = [];
let dentistMarkerItems = [];
let currentSelectedPoint = null;
let activeInfoWindow = null;

document.addEventListener("DOMContentLoaded", function () {
  const mapContainer = document.getElementById("map");

  const defaultPosition = new kakao.maps.LatLng(37.5665, 126.9780);

  const mapOption = {
    center: defaultPosition,
    level: 4
  };

  map = new kakao.maps.Map(mapContainer, mapOption);

  marker = new kakao.maps.Marker({
    position: defaultPosition,
    map: map
  });

  circle = new kakao.maps.Circle({
    center: defaultPosition,
    radius: 500,
    strokeWeight: 2,
    strokeOpacity: 0.8,
    strokeStyle: "solid",
    fillOpacity: 0.15
  });

  circle.setMap(map);

  const searchButton = document.getElementById("search-button");
  const addressInput = document.getElementById("address-input");
  const radiusSelect = document.getElementById("radius-select");

  const latText = document.getElementById("lat-text");
  const lngText = document.getElementById("lng-text");
  const addressText = document.getElementById("address-text");

  const suggestionList = document.getElementById("suggestion-list");

  const dentistCount = document.getElementById("dentist-count");
  const dentistCountDesc = document.getElementById("dentist-count-desc");
  const selectedRadiusText = document.getElementById("selected-radius-text");
  const excludedCount = document.getElementById("excluded-count");
  const dentistListSummary = document.getElementById("dentist-list-summary");
  const dentistList = document.getElementById("dentist-list");
  const competitionLevel = document.getElementById("competition-level");
  const competitionDesc = document.getElementById("competition-desc");

  addressInput.addEventListener("input", function () {
    const query = addressInput.value.trim();

    clearTimeout(suggestionTimer);

    if (!query) {
      currentSuggestions = [];
      suggestionList.textContent = "주소를 입력하면 후보 주소가 표시됩니다.";
      return;
    }

    suggestionTimer = setTimeout(function () {
      fetchAddressSuggestions(query);
    }, 300);
  });

  searchButton.addEventListener("click", async function () {
    const query = addressInput.value.trim();

    if (!query) {
      alert("주소를 입력해주세요.");
      return;
    }

    if (currentSuggestions.length > 0) {
      moveToSelectedAddress(currentSuggestions[0]);
      return;
    }

    await fetchAddressSuggestions(query, true);
  });

  addressInput.addEventListener("keydown", async function (event) {
    if (event.key === "Enter") {
      event.preventDefault();

      const query = addressInput.value.trim();

      if (!query) {
        alert("주소를 입력해주세요.");
        return;
      }

      if (currentSuggestions.length > 0) {
        moveToSelectedAddress(currentSuggestions[0]);
        return;
      }

      await fetchAddressSuggestions(query, true);
    }
  });

  radiusSelect.addEventListener("change", function () {
    const radius = Number(radiusSelect.value);

    circle.setRadius(radius);
    selectedRadiusText.textContent = formatRadius(radius);

    if (currentSelectedPoint) {
      fetchNearbyDentists(
        currentSelectedPoint.lng,
        currentSelectedPoint.lat,
        radius
      );
    }
  });

  async function fetchAddressSuggestions(query, moveFirst = false) {
    try {
      const response = await fetch(`/api/address-suggest?query=${encodeURIComponent(query)}`);
      const data = await response.json();

      if (!response.ok) {
        console.error("주소 후보 검색 실패:", data);
        suggestionList.textContent = "주소 후보 검색에 실패했습니다.";
        return;
      }

      currentSuggestions = data.suggestions || [];
      renderSuggestions(currentSuggestions);

      if (moveFirst && currentSuggestions.length > 0) {
        moveToSelectedAddress(currentSuggestions[0]);
      }

    } catch (error) {
      console.error("주소 후보 검색 중 오류:", error);
      suggestionList.textContent = "주소 후보 검색 중 오류가 발생했습니다.";
    }
  }

  function renderSuggestions(suggestions) {
    suggestionList.innerHTML = "";

    if (!suggestions || suggestions.length === 0) {
      suggestionList.textContent = "검색된 주소 후보가 없습니다.";
      return;
    }

    suggestions.forEach(function (item, index) {
      const div = document.createElement("div");
      div.className = "suggestion-item";

      const mainAddress =
        item.road_address_name ||
        item.address_name ||
        item.jibun_address_name ||
        "주소 정보 없음";

      const subAddress =
        item.jibun_address_name && item.jibun_address_name !== mainAddress
          ? item.jibun_address_name
          : "";

      div.innerHTML = `
        <div class="suggestion-main">${index + 1}. ${escapeHtml(mainAddress)}</div>
        <div class="suggestion-sub">${escapeHtml(subAddress)}</div>
      `;

      div.addEventListener("click", function () {
        moveToSelectedAddress(item);
      });

      suggestionList.appendChild(div);
    });
  }

  function moveToSelectedAddress(item) {
    const lat = Number(item.y);
    const lng = Number(item.x);
    const radius = Number(radiusSelect.value);

    currentSelectedPoint = {
      lat: lat,
      lng: lng
    };

    const position = new kakao.maps.LatLng(lat, lng);

    map.setCenter(position);
    setMapLevelByRadius(radius);

    marker.setPosition(position);

    circle.setPosition(position);
    circle.setRadius(radius);

    const selectedAddress =
      item.road_address_name ||
      item.address_name ||
      item.jibun_address_name ||
      addressInput.value.trim();

    latText.textContent = lat;
    lngText.textContent = lng;
    addressText.textContent = selectedAddress;
    selectedRadiusText.textContent = formatRadius(radius);

    addressInput.value = selectedAddress;

    fetchNearbyDentists(lng, lat, radius);

    console.log("선택 주소:", item);
  }

  async function fetchNearbyDentists(lng, lat, radius) {
    dentistCount.textContent = "조회중";
    dentistCountDesc.textContent = "카카오 Local API로 주변 치과를 조회 중입니다.";
    excludedCount.textContent = "-";
    dentistListSummary.textContent = "조회 중입니다.";
    dentistList.textContent = "주변 치과를 조회 중입니다.";

    clearDentistMarkers();

    try {
      const response = await fetch(
        `/api/nearby-dentists?x=${encodeURIComponent(lng)}&y=${encodeURIComponent(lat)}&radius=${encodeURIComponent(radius)}`
      );

      const data = await response.json();

      if (!response.ok) {
        console.error("주변 치과 조회 실패:", data);
        dentistCount.textContent = "-";
        dentistCountDesc.textContent = "주변 치과 조회에 실패했습니다.";
        dentistList.textContent = "주변 치과 조회에 실패했습니다.";
        return;
      }

      renderDentistAnalysis(data);
      renderDentistMarkers(data.dentists || []);
      renderDentistList(data.dentists || []);

      console.log("주변 치과 조회 성공:", data);

    } catch (error) {
      console.error("주변 치과 조회 중 오류:", error);
      dentistCount.textContent = "-";
      dentistCountDesc.textContent = "주변 치과 조회 중 오류가 발생했습니다.";
      dentistList.textContent = "주변 치과 조회 중 오류가 발생했습니다.";
    }
  }

    function renderDentistAnalysis(data) {
    const filteredCount = data.filtered_count ?? 0;
    const rawCount = data.raw_count ?? 0;
    const excluded = data.excluded_count ?? 0;
    const radius = data.radius ?? Number(radiusSelect.value);

    dentistCount.textContent = filteredCount;
    excludedCount.textContent = excluded;
    selectedRadiusText.textContent = formatRadius(radius);

    dentistCountDesc.textContent =
      `전체 검색 ${rawCount}개 중 실제 치과 카테고리 ${filteredCount}개를 집계했습니다.`;

    dentistListSummary.textContent =
      `반경 ${formatRadius(radius)} 내 치과 ${filteredCount}개`;

    const competition = getCompetitionLevel(filteredCount);

    competitionLevel.textContent = competition.level;
    competitionDesc.textContent = competition.desc;
  }

  function renderDentistMarkers(dentists) {
    dentists.forEach(function (dentist, index) {
      const lat = Number(dentist.y);
      const lng = Number(dentist.x);

      const position = new kakao.maps.LatLng(lat, lng);

      const dentistMarker = new kakao.maps.Marker({
        position: position,
        map: map,
        title: dentist.place_name
      });

      kakao.maps.event.addListener(dentistMarker, "click", function () {
        openDentistInfoWindow(dentistMarker, dentist);
      });

      dentistMarkers.push(dentistMarker);

      dentistMarkerItems.push({
        marker: dentistMarker,
        dentist: dentist,
        index: index
      });
    });
  }

  function clearDentistMarkers() {
    dentistMarkers.forEach(function (dentistMarker) {
      dentistMarker.setMap(null);
    });

    dentistMarkers = [];
    dentistMarkerItems = [];

    if (activeInfoWindow) {
      activeInfoWindow.close();
      activeInfoWindow = null;
    }
  }

  function renderDentistList(dentists) {
    dentistList.innerHTML = "";

    if (!dentists || dentists.length === 0) {
      dentistList.textContent = "반경 내 조회된 치과가 없습니다.";
      return;
    }

    dentists.forEach(function (dentist, index) {
      const div = document.createElement("div");
      div.className = "dentist-item";

      const address = dentist.road_address_name || dentist.address_name || "주소 정보 없음";
      const phone = dentist.phone || "전화번호 없음";
      const distance = dentist.distance ? `${dentist.distance}m` : "거리 정보 없음";

      div.innerHTML = `
        <div class="dentist-name">${index + 1}. ${escapeHtml(dentist.place_name || "이름 없음")}</div>
        <div class="dentist-meta">
          <span>${escapeHtml(distance)}</span>
          <span>${escapeHtml(phone)}</span>
        </div>
        <div class="dentist-address">${escapeHtml(address)}</div>
        ${
          dentist.place_url
            ? `<a class="dentist-link" href="${dentist.place_url}" target="_blank" rel="noopener noreferrer">카카오맵에서 보기</a>`
            : ""
        }
      `;
      div.addEventListener("click", function () {
        const markerItem = dentistMarkerItems[index];

        if (!markerItem) {
          return;
        }

        const lat = Number(dentist.y);
        const lng = Number(dentist.x);
        const position = new kakao.maps.LatLng(lat, lng);

        map.setCenter(position);
        map.setLevel(3);

        openDentistInfoWindow(markerItem.marker, dentist);
      });

      dentistList.appendChild(div);
    });
  }

  function setMapLevelByRadius(radius) {
    if (radius <= 300) {
      map.setLevel(3);
    } else if (radius <= 500) {
      map.setLevel(4);
    } else if (radius <= 1000) {
      map.setLevel(5);
    } else {
      map.setLevel(6);
    }
  }

    function getCompetitionLevel(count) {
    if (count >= 25) {
      return {
        level: "매우 높음",
        desc: "동일 반경 내 치과가 매우 밀집해 있어 신규 개원 시 강한 차별화 전략이 필요합니다."
      };
    }

    if (count >= 15) {
      return {
        level: "높음",
        desc: "반경 내 경쟁 치과가 많은 편입니다. 진료과목, 가격, 접근성 차별화가 중요합니다."
      };
    }

    if (count >= 7) {
      return {
        level: "보통",
        desc: "일정 수준의 경쟁이 존재합니다. 주변 수요와 상권 특성을 함께 검토해야 합니다."
      };
    }

    if (count >= 1) {
      return {
        level: "낮음",
        desc: "반경 내 치과 수가 적은 편입니다. 단, 유동인구와 배후수요 확인이 필요합니다."
      };
    }

    return {
      level: "매우 낮음",
      desc: "반경 내 치과 검색 결과가 없습니다. 수요 부족 지역인지 추가 검토가 필요합니다."
    };
  }

  function formatRadius(radius) {
    if (radius >= 1000) {
      return `${radius / 1000}km`;
    }

    return `${radius}m`;
  }

  function escapeHtml(value) {
    if (value === null || value === undefined) {
      return "";
    }

    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

    function openDentistInfoWindow(dentistMarker, dentist) {
    if (activeInfoWindow) {
      activeInfoWindow.close();
    }

    const content = `
      <div style="padding:10px; min-width:220px; font-size:13px;">
        <strong>${escapeHtml(dentist.place_name || "")}</strong><br>
        <span>${escapeHtml(dentist.road_address_name || dentist.address_name || "")}</span><br>
        <span>거리: ${escapeHtml(dentist.distance || "-")}m</span>
      </div>
    `;

    activeInfoWindow = new kakao.maps.InfoWindow({
      content: content
    });

    activeInfoWindow.open(map, dentistMarker);
  }

});