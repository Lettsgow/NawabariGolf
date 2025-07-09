window.onload = () => {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const formatted = tomorrow.toISOString().split("T")[0];
  document.getElementById("start_date").value = formatted;
  document.getElementById("end_date").value = formatted;
};

function getTimeNumber(hourStr) {
  const match = hourStr.match(/(\d{1,2})시대/);
  return match ? parseInt(match[1], 10) : 0;
}

function getSortedKeys(grouped) {
  return Object.keys(grouped).sort((a, b) => {
    const [dateA, hourA] = a.split(" ");
    const [dateB, hourB] = b.split(" ");
    const fullDateA = new Date(`2025-${dateA.replace("/", "-")}`);
    const fullDateB = new Date(`2025-${dateB.replace("/", "-")}`);
    if (fullDateA.getTime() !== fullDateB.getTime()) {
      return fullDateA - fullDateB;
    }
    return getTimeNumber(hourA) - getTimeNumber(hourB);
  });
}

function formatToManWon(price) {
  return `${(price / 10000).toFixed(1)}만`;
}

async function getGroupedTeeTime() {
  const start_date = document.getElementById("start_date").value;
  const end_date = document.getElementById("end_date").value;
  const resultBody = document.getElementById("result-body");
  const theadRow = document.querySelector("thead tr");
  const checkedHours = Array.from(document.querySelectorAll(".hour-checkbox:checked"))
    .map(cb => parseInt(cb.value));

  const favoriteClubs = getFavoriteClubs();

  console.log("📤 요청 보내는 중:", {
    start_date,
    end_date,
    hour_range: checkedHours,
    favorite_clubs: favoriteClubs
  });

  resultBody.innerHTML = `<tr><td colspan="100%">⏳ 조회 중...</td></tr>`;

  try {
    const response = await fetch("/get_ttime_grouped", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start_date,
        end_date,
        hour_range: checkedHours.length > 0 ? checkedHours : null,
        favorite_clubs: favoriteClubs
      })
    });

    const data = await response.json();

    console.log("✅ 서버 응답:", data);

    const filteredData = data; // ✅ 서버에서 이미 필터링 했으므로 여기선 그대로 사용

    if (!Array.isArray(filteredData) || filteredData.length === 0) {
      resultBody.innerHTML = `<tr><td colspan="100%">조회된 티타임이 없습니다.</td></tr>`;
      return;
    }

    const golfClubs = [...new Set(filteredData.map(item => item.golf))].sort();

    theadRow.innerHTML = `<th>날짜/시간대</th>`;
    golfClubs.forEach(club => {
      const th = document.createElement("th");
      th.textContent = club;
      theadRow.appendChild(th);
    });

    const grouped = {};
    filteredData.forEach(item => {
      const key = `${item.date} ${item.hour}`;
      if (!grouped[key]) grouped[key] = {};
      grouped[key][item.golf] = { price: item.price, benefit: item.benefit };
    });

    const minPriceMap = {};
    for (let key in grouped) {
      const prices = Object.values(grouped[key]).map(p => p.price);
      minPriceMap[key] = Math.min(...prices);
    }

    resultBody.innerHTML = "";
    const sortedKeys = getSortedKeys(grouped);

    let lastDate = null;
    sortedKeys.forEach(key => {
      const [date] = key.split(" ");
      const priceMap = grouped[key];
      if (!Object.keys(priceMap).length) return;

      const tr = document.createElement("tr");
      if (date !== lastDate) {
        tr.classList.add("new-date");
        lastDate = date;
      }

      const tdLabel = document.createElement("td");
      tdLabel.textContent = key;
      tr.appendChild(tdLabel);

      golfClubs.forEach(club => {
        const td = document.createElement("td");
        const item = priceMap[club];
        if (item) {
          if (item.price === minPriceMap[key]) td.classList.add("highlight");

          td.innerHTML = `
            <div>${formatToManWon(item.price)}</div>
            ${item.benefit ? `<div class="benefit-inline">🎁 ${item.benefit}</div>` : ""}
          `;
        } else {
          td.textContent = "-";
        }
        tr.appendChild(td);
      });

      resultBody.appendChild(tr);
    });

  } catch (err) {
    console.error("❌ 요청 실패 또는 서버 오류:", err);
    resultBody.innerHTML = `<tr><td colspan="100%">요청 실패 또는 서버 오류</td></tr>`;
  }
}

// ⚙️ 모달 열기/닫기
document.getElementById("settings-button").onclick = openModal;
function openModal() {
  document.getElementById("settings-modal").style.display = "block";
  loadGolfClubList();
}
function closeModal() {
  document.getElementById("settings-modal").style.display = "none";
}

// 📋 전체 구장 리스트 서버에서 받아오기
async function loadGolfClubList() {
  const container = document.getElementById("golfclub-list");
  container.innerHTML = "불러오는 중...";
  try {
    const res = await fetch("/get_all_golfclubs");
    const clubs = await res.json();
    const saved = getFavoriteClubs();
    container.innerHTML = "";
    clubs.forEach(name => {
      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = name;
      if (saved.includes(name)) checkbox.checked = true;
      label.appendChild(checkbox);
      label.appendChild(document.createTextNode(name));
      container.appendChild(label);
    });
  } catch (e) {
    console.error("❌ 골프장 리스트 불러오기 실패:", e);
    container.innerHTML = "불러오기 실패";
  }
}

// 💾 저장
function saveFavorites() {
  const checked = Array.from(document.querySelectorAll("#golfclub-list input[type='checkbox']:checked"))
    .map(cb => cb.value);
  localStorage.setItem("favorite_clubs", JSON.stringify(checked));
  console.log("💾 저장된 선호 골프장:", checked);
  closeModal();
  getGroupedTeeTime(); // 바로 재조회
}

// 📦 저장된 선호 구장 불러오기
function getFavoriteClubs() {
  try {
    const raw = localStorage.getItem("favorite_clubs") || "[]";
    const parsed = JSON.parse(raw);
    console.log("📦 불러온 선호 골프장:", parsed);
    return parsed;
  } catch (e) {
    console.error("❌ 로컬스토리지 파싱 오류:", e);
    return [];
  }
}
