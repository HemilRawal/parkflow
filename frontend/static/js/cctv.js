// ParkFlow CCTV - Filter tabs for camera categories
document.addEventListener('DOMContentLoaded', () => {
  const tabs = document.querySelectorAll('.filter-tab');
  const cards = document.querySelectorAll('.camera-card');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const filter = tab.dataset.filter;

      cards.forEach(card => {
        if (filter === 'all' || card.dataset.type === filter) {
          card.style.display = 'block';
        } else {
          card.style.display = 'none';
        }
      });
  });
});

async function fetchCameraHealth() {
  try {
    const res = await fetch('/api/camera_health');
    const healthData = await res.json();
    
    // Update individual health badges
    for (const [camId, health] of Object.entries(healthData)) {
      const badge = document.getElementById(`health-${camId}`);
      if (badge) {
        badge.textContent = `${health}% HEALTH`;
        if (health === 0) {
          badge.classList.add('offline');
        } else {
          badge.classList.remove('offline');
        }
      }
    }
    
    // Update summary health panel if it exists
    const onlineCount = Object.values(healthData).filter(h => h > 0).length;
    const totalCount = Object.keys(healthData).length;
    const healthBar = document.querySelector('.health-panel strong');
    const fill = document.querySelector('.health-panel .fill');
    
    if (healthBar && fill) {
      healthBar.textContent = `${onlineCount}/${totalCount}`;
      const pct = (onlineCount / totalCount) * 100;
      fill.style.width = `${pct}%`;
      fill.style.background = pct < 100 ? 'var(--red)' : 'var(--green)';
    }
    
  } catch (e) { console.error('Camera health fetch error:', e); }
}

setInterval(fetchCameraHealth, 3000);
fetchCameraHealth();
