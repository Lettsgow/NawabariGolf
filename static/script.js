// ✅ JS: 티타임 테이블 렌더링 (로그 추가 + 티스캐너 우선 + 아이콘 색상 수정)

const hourCheckboxes = document.querySelectorAll(".hour-checkbox");
const startDateInput = document.getElementById("start_date");
const endDateInput = document.getElementById("end_date");
const resultBody = document.getElementById("result-body");
const settingsModal = document.getElementById("settings-modal");
const golfclubList = document.getElementById("golfclub-list");

window.onload = () => {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const formatted = tomorrow.toISOString().split("T")[0];
  startDateInput.value = formatted;
  endDateInput.value = formatted;
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
  return `${(price / 10000).toFixed(1)}`;
}

async function getGroupedTeeTime() {
  const start_date = startDateInput.value;
  const end_date = endDateInput.value;
  const checkedHours = Array.from(hourCheckboxes).filter(cb => cb.checked).map(cb => parseInt(cb.value));
  const favoriteClubs = getFavoriteClubs();

  console.log("📤 티타임 요청 시작", { start_date, end_date, checkedHours, favoriteClubs });
  resultBody.innerHTML = `<tr><td colspan="100%">⏳ 조회 중...</td></tr>`;

  try {
    const response = await fetch("/get_ttime_grouped", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start_date, end_date, hour_range: checkedHours.length ? checkedHours : null, favorite_clubs: favoriteClubs })
    });

    const data = await response.json();
    console.log("✅ 티타임 응답 도착", data);
    renderTeeTimeTable(data);
  } catch (err) {
    console.error("❌ 요청 실패 또는 서버 오류:", err);
    resultBody.innerHTML = `<tr><td colspan="100%">요청 실패 또는 서버 오류</td></tr>`;
  }
}

function renderTeeTimeTable(data) {
  const grouped = {};
  const golfNames = new Set();

  for (const item of data) {
    const key = `${item.date} ${item.hour}`;
    if (!grouped[key]) grouped[key] = {};
    if (!grouped[key][item.golf] || grouped[key][item.golf].source === "golfpang") {
      grouped[key][item.golf] = item; // teescan 우선
    }
    golfNames.add(item.golf);
  }

  console.log("🧩 그룹핑된 데이터", grouped);

  const sortedGolfNames = Array.from(golfNames).sort();
  const sortedKeys = getSortedKeys(grouped);

  const thead = document.querySelector("thead tr");
  thead.innerHTML = `<th>날짜/시간대</th>` + sortedGolfNames.map(name => `<th>${name}</th>`).join("");
  resultBody.innerHTML = "";

  let lastDate = null;
  for (const key of sortedKeys) {
    const [date] = key.split(" ");
    const priceMap = grouped[key];
    if (!Object.keys(priceMap).length) continue;

    const tr = document.createElement("tr");
    if (date !== lastDate) {
      tr.classList.add("new-date");
      lastDate = date;
    }
    const tdLabel = document.createElement("td");
    tdLabel.textContent = key;
    tr.appendChild(tdLabel);

    let minPrice = Infinity;
    Object.values(priceMap).forEach(p => { if (p.price < minPrice) minPrice = p.price });

    sortedGolfNames.forEach(name => {
      const td = document.createElement("td");
      const item = priceMap[name];
      if (item) {
        if (item.price === minPrice) td.classList.add("highlight");
        const iconColor = item.source === "teescan" ? "red" : "blue";
        const icon = `<span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:${iconColor};color:white;font-size:10px;line-height:14px;text-align:center;margin-right:3px;font-weight:bold;">${item.source === "teescan" ? "T" : "G"}</span>`;
        td.innerHTML = `<div class="price-cell" data-url="${item.url}" style="cursor:pointer;">${icon}${formatToManWon(item.price)}</div>`;
      } else {
        td.textContent = "-";
      }
      tr.appendChild(td);
    });
    resultBody.appendChild(tr);
  }
}

// ⚙️ 설정 모달
function openModal() { settingsModal.style.display = "block"; }
function closeModal() { settingsModal.style.display = "none"; }
function saveFavorites() {
  const checkboxes = golfclubList.querySelectorAll("input[type='checkbox']");
  const selected = Array.from(checkboxes).filter(cb => cb.checked).map(cb => cb.value);
  localStorage.setItem("favorite_clubs", JSON.stringify(selected));
  console.log("💾 선호 골프장 저장됨:", selected);
  closeModal();
  getGroupedTeeTime();
}

document.getElementById("settings-button").addEventListener("click", () => {
  fetch("/get_all_golfclubs")
    .then(res => res.json())
    .then(clubs => {
      console.log("📦 전체 골프장 리스트:", clubs);
      golfclubList.innerHTML = "";
      const favorites = getFavoriteClubs();
      clubs.forEach(name => {
        const checked = favorites.includes(name) ? "checked" : "";
        golfclubList.innerHTML += `<label><input type="checkbox" value="${name}" ${checked}> ${name}</label>`;
      });
      openModal();
    });
});

function getFavoriteClubs() {
  try {
    const favs = JSON.parse(localStorage.getItem("favorite_clubs") || "[]");
    console.log("📦 불러온 선호 골프장:", favs);
    return favs;
  } catch {
    return [];
  }
}

// 셀 클릭 시 새 창
resultBody.addEventListener("click", e => {
  const target = e.target.closest(".price-cell");
  if (target && target.dataset.url) {
    window.open(target.dataset.url, "_blank");
  }
});
