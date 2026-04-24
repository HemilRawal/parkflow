// ParkFlow Billing - Transaction table, activity feed, quick billing
const socket = io();

// ── Fetch & Render ──────────────────────────────────────────
async function fetchSummary() {
  try {
    const res = await fetch('/api/billing/summary');
    const d = await res.json();
    document.getElementById('total-cars').textContent = d.total_cars_today;
    document.getElementById('total-revenue').textContent = '₹' + d.total_revenue_today.toLocaleString('en-IN', {minimumFractionDigits:2});
    
    // Check if element exists before setting (for pages that don't have it)
    if (document.getElementById('weekly-revenue')) {
        document.getElementById('weekly-revenue').textContent = '₹' + d.weekly_revenue.toLocaleString('en-IN', {minimumFractionDigits:2});
        document.getElementById('monthly-revenue').textContent = '₹' + d.monthly_revenue.toLocaleString('en-IN', {minimumFractionDigits:2});
    }
  } catch(e) { console.error(e); }
}

let allTransactions = [];
let maxTransactionsToShow = 10;

async function fetchTransactions() {
  try {
    const res = await fetch('/api/transactions');
    allTransactions = await res.json();
    renderTransactions();
  } catch(e) { console.error(e); }
}

function renderTransactions() {
    const tbody = document.getElementById('logs-tbody');
    if (!allTransactions.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:32px;">No transactions yet</td></tr>';
      document.getElementById('view-all-records').style.display = 'none';
      return;
    }
    
    const toShow = allTransactions.slice(0, maxTransactionsToShow);
    tbody.innerHTML = toShow.map(t => {
      return `
      <tr>
        <td class="plate">${t.plate}</td>
        <td>${t.entry_time}</td>
        <td>${t.exit_time === '---' ? '<span class="in-progress">---</span>' : t.exit_time}</td>
        <td>${t.date}</td>
        <td>${t.status === 'In Progress' ? '<span class="in-progress">In Progress</span>' : '₹' + t.total_bill.toLocaleString('en-IN', {minimumFractionDigits:2})}</td>
        <td><span class="badge ${t.extra_charges === 'NONE' ? 'none' : 'improper'}">${t.extra_charges}</span></td>
      </tr>
    `;
    }).join('');
    
    const btn = document.getElementById('view-all-records');
    if (allTransactions.length > maxTransactionsToShow) {
        btn.style.display = 'block';
        btn.textContent = `Show More (${allTransactions.length - maxTransactionsToShow} remaining)`;
    } else {
        btn.style.display = 'none';
    }
}

document.getElementById('view-all-records').addEventListener('click', () => {
    maxTransactionsToShow += 10;
    renderTransactions();
});

async function fetchActivity() {
  try {
    const res = await fetch('/api/activity');
    const logs = await res.json();
    const list = document.getElementById('activity-feed-list');
    if (!logs.length) {
      list.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:24px;font-size:13px;">No activity yet</div>';
      return;
    }
    list.innerHTML = logs.slice(0, 10).map(log => {
      let iconClass, icon, title, detail, dotClass;
      if (log.type === 'car_entered') {
        iconClass = 'entered'; icon = '➡️'; title = 'Car Entered'; dotClass = 'green';
        detail = `Plate: ${log.car_id} · ${log.slot_id}`;
      } else if (log.type === 'violation') {
        iconClass = 'violation'; icon = '🚫'; title = 'Violation/Improper Parking'; dotClass = 'red';
        detail = `Plate: ${log.car_id} · Alert: ${log.alert}`;
      } else {
        iconClass = 'exited'; icon = '💳'; title = 'Car Exited/Paid'; dotClass = 'blue';
        detail = `Plate: ${log.car_id} · Payment: ₹${log.payment ? log.payment.toLocaleString('en-IN') : '0'}`;
      }
      return `
        <div class="feed-item">
          <div class="feed-icon ${iconClass}">${icon}</div>
          <div class="feed-text">
            <h4>${title} <span class="dot ${dotClass}"></span></h4>
            <p>${detail}</p>
          </div>
          <div class="feed-time">${log.time_ago || log.timestamp}</div>
        </div>
      `;
    }).join('');
  } catch(e) { console.error(e); }
}

// ── Quick Checkout / Manual Checkout ───────────────────────────
document.getElementById('btn-calculate').addEventListener('click', async () => {
  const plate = document.getElementById('plate-input').value.trim();
  const resultDiv = document.getElementById('quick-billing-result');
  const checkoutBtn = document.getElementById('btn-checkout');
  
  if (!plate) {
      resultDiv.innerHTML = '<span style="color:var(--red);">Please enter a plate/car ID</span>';
      checkoutBtn.style.display = 'none';
      return;
  }
  
  const carId = plate.toUpperCase().replace('PLT-', 'CAR-');
  
  // Find in allTransactions if it's currently In Progress
  const activeTxn = allTransactions.find(t => t.car_id === carId && t.status === 'In Progress');
  
  if (activeTxn) {
      resultDiv.innerHTML = `Car: <b>${carId}</b> <br> Time Elapsed: <b>${activeTxn.duration_sec}s</b> <br> Current Bill: <b style="color:var(--green);">₹${activeTxn.total_bill}</b>`;
      checkoutBtn.style.display = 'block';
  } else {
      resultDiv.innerHTML = '<span style="color:var(--red);">Car not found in active sessions.</span>';
      checkoutBtn.style.display = 'none';
  }
});

document.getElementById('btn-checkout').addEventListener('click', async () => {
  const plate = document.getElementById('plate-input').value.trim();
  const resultDiv = document.getElementById('quick-billing-result');
  const checkoutBtn = document.getElementById('btn-checkout');
  
  try {
      const res = await fetch('/api/checkout', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({plate: plate})
      });
      const data = await res.json();
      if (data.success) {
          resultDiv.innerHTML = `<span style="color:var(--green);">Successfully collected ₹${data.bill.total_bill} and checked out!</span>`;
          checkoutBtn.style.display = 'none';
          document.getElementById('plate-input').value = '';
          fetchSummary(); fetchTransactions(); fetchActivity();
      } else {
          resultDiv.innerHTML = `<span style="color:var(--red);">${data.error}</span>`;
      }
  } catch(e) {
      resultDiv.innerHTML = '<span style="color:var(--red);">Checkout failed</span>';
  }
});

// ── Manual Vehicle Entry ────────────────────────────────────
document.getElementById('btn-manual-entry').addEventListener('click', async () => {
    const plate = document.getElementById('manual-entry-plate').value.trim();
    const resultDiv = document.getElementById('manual-entry-result');
    if (!plate) {
        resultDiv.innerHTML = '<span style="color:var(--red);">Please enter a plate number</span>';
        return;
    }
    
    try {
        const res = await fetch('/api/manual_entry', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({plate: plate})
        });
        const data = await res.json();
        if (data.success) {
            resultDiv.innerHTML = `<span style="color:var(--green);">Vehicle ${plate} registered successfully!</span>`;
            document.getElementById('manual-entry-plate').value = '';
            fetchSummary(); fetchTransactions(); fetchActivity();
        } else {
            resultDiv.innerHTML = `<span style="color:var(--red);">${data.error}</span>`;
        }
    } catch(e) {
        resultDiv.innerHTML = '<span style="color:var(--red);">Failed to register vehicle</span>';
    }
});

// ── Export CSV ──────────────────────────────────────────────
document.getElementById('btn-export').addEventListener('click', async () => {
  const res = await fetch('/api/transactions');
  const txns = await res.json();
  const headers = ['Plate,Entry,Exit,Date,Bill,Charges'];
  const rows = txns.map(t => `${t.plate},${t.entry_time},${t.exit_time},${t.date},${t.total_bill},${t.extra_charges}`);
  const csv = headers.concat(rows).join('\n');
  const blob = new Blob([csv], {type:'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'parkflow_transactions.csv';
  a.click();
});

// ── WebSocket ───────────────────────────────────────────────
socket.on('car_entered', () => { fetchActivity(); fetchSummary(); fetchTransactions(); });
socket.on('car_exited', () => { fetchActivity(); fetchSummary(); fetchTransactions(); });

// ── Init ────────────────────────────────────────────────────
fetchSummary();
fetchTransactions();
fetchActivity();
setInterval(() => { fetchSummary(); fetchTransactions(); fetchActivity(); }, 5000);
