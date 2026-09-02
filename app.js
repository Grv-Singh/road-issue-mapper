let map;
let markers = [];
let issuesData = [];

const TYPE_CONFIG = {
  pothole_shock: { label: 'POTHOLE JOLT', color: '#ef4444', badgeBg: 'rgba(239, 68, 68, 0.15)' },
  garbage_or_debris: { label: 'GARBAGE / DEBRIS', color: '#f97316', badgeBg: 'rgba(249, 115, 22, 0.15)' },
  manual_flag: { label: 'MANUAL FLAG', color: '#a855f7', badgeBg: 'rgba(168, 85, 247, 0.15)' },
  route_audit: { label: 'STREET SURVEY', color: '#38bdf8', badgeBg: 'rgba(56, 189, 248, 0.15)' }
};

function initMap() {
  map = L.map('map').setView([26.8897, 75.7930], 14);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    maxZoom: 19
  }).addTo(map);
}

async function fetchTelemetry() {
  try {
    const res = await fetch('/api/telemetry');
    if (!res.ok) throw new Error('Not local');
    const data = await res.json();
    
    const conn = document.getElementById('connStatus');
    if (data.status === 'online') {
      conn.textContent = 'Camera Online';
      conn.className = 'status-badge online';
    } else {
      conn.textContent = 'Camera Offline';
      conn.className = 'status-badge offline';
    }

    if (data.battery !== null && data.battery !== undefined) {
      document.getElementById('battery').textContent = `${data.battery}%`;
    }

    if (data.gps && data.gps.lat && data.gps.lng) {
      document.getElementById('gpsStatus').textContent = `Locked (${data.gps.provider || 'GPS'})`;
      document.getElementById('coords').textContent = `${data.gps.lat.toFixed(5)}, ${data.gps.lng.toFixed(5)}`;
      const speedKmH = (data.gps.speed * 3.6).toFixed(1);
      document.getElementById('speed').textContent = `${speedKmH} km/h`;
    }
  } catch (err) {
    const conn = document.getElementById('connStatus');
    conn.textContent = 'Public Mode (GitHub Pages)';
    conn.className = 'status-badge online';
    document.getElementById('gpsStatus').textContent = 'Cloud Synced';
  }
}

async function fetchIssues() {
  try {
    const res = await fetch(`data/issues.json?t=${Date.now()}`);
    const issues = await res.json();
    issuesData = issues;

    document.getElementById('issueCount').textContent = issues.length;
    renderSidebar(issues);
    renderMapMarkers(issues);
  } catch (err) {
    console.error('Issues fetch error', err);
  }
}

function renderMapMarkers(issues) {
  markers.forEach(m => map.removeLayer(m));
  markers = [];

  let hasValidCoords = false;

  issues.forEach(issue => {
    if (issue.gps && issue.gps.lat && issue.gps.lng) {
      hasValidCoords = true;
      const cfg = TYPE_CONFIG[issue.type] || { color: '#f59e0b', label: (issue.type || 'DEFECT').toUpperCase() };

      const marker = L.circleMarker([issue.gps.lat, issue.gps.lng], {
        radius: issue.type === 'route_audit' ? 6 : 9,
        fillColor: cfg.color,
        color: '#ffffff',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9
      }).addTo(map);

      const imgUrl = issue.image ? issue.image.replace(/^\//, '') : null;

      marker.bindPopup(`
        <div style="font-size:12px; color:#111; min-width: 190px; line-height: 1.4;">
          <div style="font-weight:700; color:${cfg.color}; letter-spacing:0.5px;">${cfg.label}</div>
          <div style="font-size:11px; color:#555; margin-top:2px;">${issue.description || ''}</div>
          ${issue.magnitude > 0 ? `<div style="margin-top:2px;"><b>Shock:</b> ${issue.magnitude} m/s²</div>` : ''}
          <div style="font-size:10px; color:#777; margin-top:2px;">${new Date(issue.timestamp).toLocaleTimeString()}</div>
          ${imgUrl ? `<img src="${imgUrl}" style="width:100%; max-height:130px; object-fit:cover; margin-top:6px; border-radius:4px; border:1px solid #ddd;" />` : ''}
        </div>
      `);

      markers.push(marker);
    }
  });

  if (hasValidCoords && markers.length > 0 && !map._centeredOnce) {
    const group = new L.featureGroup(markers);
    map.fitBounds(group.getBounds().pad(0.3));
    map._centeredOnce = true;
  }
}

function renderSidebar(issues) {
  const container = document.getElementById('issuesList');
  if (!issues || issues.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="#64748b" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <path d="m9 12 2 2 4-4"></path>
        </svg>
        <p>No defects recorded yet.<br>Start your ride to detect road issues.</p>
      </div>`;
    return;
  }

  container.innerHTML = '';
  const reversed = [...issues].reverse();

  reversed.forEach(issue => {
    const card = document.createElement('div');
    card.className = 'issue-card';
    
    const cfg = TYPE_CONFIG[issue.type] || { label: (issue.type || 'DEFECT').toUpperCase(), color: '#f59e0b', badgeBg: 'rgba(245,158,11,0.15)' };
    const timeStr = new Date(issue.timestamp).toLocaleTimeString();
    const gpsStr = (issue.gps && issue.gps.lat) ? `${issue.gps.lat.toFixed(4)}, ${issue.gps.lng.toFixed(4)}` : 'No GPS Fix';
    const imgUrl = issue.image ? issue.image.replace(/^\//, '') : null;

    card.innerHTML = `
      <div class="issue-card-header">
        <span class="severity-tag" style="background-color:${cfg.badgeBg}; color:${cfg.color}; border:1px solid ${cfg.color};">${cfg.label}</span>
        <span class="issue-time">${timeStr}</span>
      </div>
      <div class="issue-info">
        <div><strong>${issue.description || issue.type}</strong></div>
        ${issue.magnitude > 0 ? `<div><strong>Shock:</strong> ${issue.magnitude} m/s²</div>` : ''}
        <div style="color:var(--text-muted); font-size:11px;">${gpsStr}</div>
      </div>
      ${imgUrl ? `<img src="${imgUrl}" class="issue-thumb" alt="Road Defect" />` : ''}
    `;

    card.addEventListener('click', () => {
      if (imgUrl) {
        showModal(imgUrl, `${cfg.label} | ${issue.description || ''} | ${gpsStr}`);
      }
      if (issue.gps && issue.gps.lat) {
        map.setView([issue.gps.lat, issue.gps.lng], 17);
      }
    });

    container.appendChild(card);
  });
}

function showModal(imgSrc, details) {
  const modal = document.getElementById('imgModal');
  const img = document.getElementById('modalImg');
  const det = document.getElementById('modalDetails');
  img.src = imgSrc;
  det.textContent = details;
  modal.classList.add('active');
}

document.getElementById('modalClose').addEventListener('click', () => {
  document.getElementById('imgModal').classList.remove('active');
});

const btn = document.getElementById('btnTrigger');
if (btn) {
  btn.addEventListener('click', async () => {
    btn.innerHTML = '<span>Capturing...</span>';
    try {
      await fetch('/api/trigger', { method: 'POST' });
      await fetchIssues();
    } catch (err) {
      console.error(err);
    } finally {
      btn.innerHTML = `
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
          <circle cx="12" cy="13" r="4"></circle>
        </svg>
        <span>Manual Flag</span>`;
    }
  });
}

window.addEventListener('DOMContentLoaded', () => {
  initMap();
  fetchTelemetry();
  fetchIssues();

  setInterval(fetchTelemetry, 2000);
  setInterval(fetchIssues, 4000);
});
