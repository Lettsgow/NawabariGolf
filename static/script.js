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

  resultBody.innerHTML = `<tr><td colspan="100%">⏳ 조회 중...</td></tr>`;

  try {
    const response = await fetch("/get_ttime_grouped", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start_date,
        end_date,
        hour_range: checkedHours.length > 0 ? checkedHours : null
      })
    });

    const data = await response.json();

    if (!Array.isArray(data) || data.length === 0) {
      resultBody.innerHTML = `<tr><td colspan="100%">조회된 티타임이 없습니다.</td></tr>`;
      return;
    }

    const golfClubs = [...new Set(data.map(item => item.golf))].sort();

    theadRow.innerHTML = `<th>날짜/시간대</th>`;
    golfClubs.forEach(club => {
      const th = document.createElement("th");
      th.textContent = club;
      theadRow.appendChild(th);
    });

    const grouped = {};
    data.forEach(item => {
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
    console.error("❌ 오류:", err);
    resultBody.innerHTML = `<tr><td colspan="100%">요청 실패 또는 서버 오류</td></tr>`;
  }
}
