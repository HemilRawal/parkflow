// ParkFlow Dashboard - Real-time parking grid & metrics
const socket = io();
let allSlots = [];

// ── Fetch & Render ──────────────────────────────────────────
async function fetchMetrics() {
  try {
    const res = await fetch('/api/metrics');
    const data = await res.json();
    document.getElementById('metric-capacity').textContent = data.capacity;
    document.getElementById('metric-occupied').textContent = data.occupied;
    document.getElementById('metric-empty').textContent = data.empty;

    const occPct = data.capacity > 0 ? (data.occupied / data.capacity * 100) : 0;
    const empPct = data.capacity > 0 ? (data.empty / data.capacity * 100) : 0;
    document.getElementById('bar-occupied').style.width = occPct + '%';
    document.getElementById('bar-empty').style.width = empPct + '%';

    const badge = document.getElementById('nearest-badge');
    if (data.nearest_slot) {
      badge.textContent = '● Nearest Available Slot: ' + data.nearest_slot + ' is open';
    } else {
      badge.textContent = '● All slots occupied';
      badge.style.background = '#fef2f2';
      badge.style.color = '#dc2626';
      badge.style.borderColor = '#fecaca';
    }


  } catch (e) { console.error('Metrics fetch error:', e); }
}

async function fetchSlots() {
  try {
    const res = await fetch('/api/slots');
    allSlots = await res.json();
    renderGrid(allSlots);
  } catch (e) { console.error('Slots fetch error:', e); }
}

function renderGrid(slots) {
  const grid = document.getElementById('parking-grid');
  grid.innerHTML = '';

  // Group by row letter
  const rows = {};
  slots.forEach(s => {
    const row = s.id.split('-')[0];
    if (!rows[row]) rows[row] = [];
    rows[row].push(s);
  });

  // Find nearest
  const metrics = { nearest: null };
  for (const s of slots) {
    if (s.status === 'empty') { metrics.nearest = s.id; break; }
  }

  Object.keys(rows).sort().forEach(rowKey => {
    const rowDiv = document.createElement('div');
    rowDiv.className = 'parking-row';

    const label = document.createElement('div');
    label.className = 'row-label';
    label.textContent = rowKey;
    rowDiv.appendChild(label);

    rows[rowKey].sort((a, b) => a.id.localeCompare(b.id)).forEach(slot => {
      const el = document.createElement('div');
      el.className = 'slot';
      el.textContent = slot.id;
      el.id = 'slot-' + slot.id;

      if (slot.status === 'occupied') {
        el.classList.add(slot.is_improper ? 'improper' : 'occupied');
        el.title = `${slot.car_id || ''} — ${slot.is_improper ? 'IMPROPER' : 'Occupied'}`;
      } else if (slot.status === 'offline') {
        el.classList.add('offline');
        el.title = 'Camera Offline - Status Unknown';
      } else {
        el.classList.add('available');
        el.title = 'Available';
      }

      if (slot.id === metrics.nearest) {
        el.classList.add('nearest');
        el.title = 'Nearest Available';
      }

      rowDiv.appendChild(el);
    });
    grid.appendChild(rowDiv);
  });
}

// ── Activity Feed ──────────────────────────────────────────
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
      } else if (log.type === 'system_alert') {
        iconClass = 'violation'; icon = '⚠️'; title = 'System Alert'; dotClass = 'red';
        detail = log.alert;
      } else {
        iconClass = 'exited'; icon = '💳'; title = 'Car Exited/Paid'; dotClass = 'blue';
        detail = `Plate: ${log.car_id} · Payment: ₹${log.payment ? log.payment.toLocaleString('en-IN') : '0'}`;
      }
      return `
        <div class="feed-item" style="display:flex; gap:16px; align-items:center; padding:12px 0; border-bottom:1px solid var(--border);">
          <div class="feed-icon ${iconClass}" style="width:40px; height:40px; border-radius:50%; display:flex; align-items:center; justify-content:center; background:#f0f0f0;">${icon}</div>
          <div class="feed-text" style="flex:1;">
            <h4 style="margin:0 0 4px 0; font-size:14px; font-weight:600;">${title}</h4>
            <p style="margin:0; font-size:13px; color:var(--text-muted);">${detail}</p>
          </div>
          <div class="feed-time" style="font-size:12px; color:var(--text-light);">${log.time_ago || log.timestamp}</div>
        </div>
      `;
    }).join('');
  } catch(e) { console.error(e); }
}

// ── WebSocket ───────────────────────────────────────────────
socket.on('slot_update', (slots) => {
  allSlots = slots;
  renderGrid(slots);
  fetchMetrics();
});

socket.on('car_entered', (data) => {
  console.log('Car entered:', data);
  fetchMetrics();
  fetchActivity();
});

socket.on('car_exited', (data) => {
  console.log('Car exited:', data);
  fetchMetrics();
  fetchActivity();
});



socket.on('video_ended', () => {
  console.log('Video processing complete');
});

// ── Init ────────────────────────────────────────────────────
fetchMetrics();
fetchSlots();
fetchActivity();
setInterval(() => { fetchMetrics(); fetchActivity(); }, 3000);
