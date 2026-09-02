let map;
let markers = [];
let issuesData = [];

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
      document.getElementById('gpsStatus').textContent = `Locked (${data.gps.provider})`;
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
    // Works on both local server and GitHub Pages statically
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
      const marker = L.circleMarker([issue.gps.lat, issue.gps.lng], {
        radius: 8,
        fillColor: issue.severity === 'high' ? '#ef4444' : '#f59e0b',
        color: '#fff',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.85
      }).addTo(map);

      // Support relative image path on GitHub Pages
      const imgUrl = issue.image ? issue.image.replace(/^\//, '') : null;

      marker.bindPopup(`
        <div style="font-size:12px; color:#111;">
          <b>${(issue.type || 'DEFECT').toUpperCase()}</b><br>
          Severity: ${issue.severity}<br>
          G-Force: ${issue.magnitude || '0'} m/s²<br>
          ${imgUrl ? `<img src="${imgUrl}" style="width:180px; height:100px; object-fit:cover; margin-top:5px; border-radius:4px;" />` : ''}
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
    container.innerHTML = '<div class="empty-state">No road issues detected yet. Start riding your scooter!</div>';
    return;
  }

  container.innerHTML = '';
  const reversed = [...issues].reverse();

  reversed.forEach(issue => {
    const card = document.createElement('div');
    card.className = 'issue-card';
    
    const timeStr = new Date(issue.timestamp).toLocaleTimeString();
    const gpsStr = (issue.gps && issue.gps.lat) ? `${issue.gps.lat.toFixed(4)}, ${issue.gps.lng.toFixed(4)}` : 'No GPS Fix';
    const imgUrl = issue.image ? issue.image.replace(/^\//, '') : null;

    card.innerHTML = `
      <div class="issue-card-header">
        <span class="severity-tag ${issue.severity}">${issue.type}</span>
        <span class="issue-time">${timeStr}</span>
      </div>
      <div class="issue-info">
        <div><strong>Shock:</strong> ${issue.magnitude} m/s² (Z: ${issue.z_accel} m/s²)</div>
        <div><strong>Location:</strong> ${gpsStr}</div>
      </div>
      ${imgUrl ? `<img src="${imgUrl}" class="issue-thumb" alt="Defect" />` : ''}
    `;

    card.addEventListener('click', () => {
      if (imgUrl) {
        showModal(imgUrl, `Detected at ${timeStr} | Shock: ${issue.magnitude} m/s² | ${gpsStr}`);
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
    btn.textContent = 'Capturing...';
    try {
      await fetch('/api/trigger', { method: 'POST' });
      await fetchIssues();
    } catch (err) {
      console.error(err);
    } finally {
      btn.textContent = '📸 Manual Flag';
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
