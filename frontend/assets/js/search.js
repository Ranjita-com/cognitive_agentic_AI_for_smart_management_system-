/**
 * ============================================================
 * SMART BUS - PASSENGER SEARCH & ROUTE PLANNER CONTROLLER
 * ============================================================
 */

let allRoutes = [];
let allStops = [];

document.addEventListener('DOMContentLoaded', async () => {
  await loadStopsAndRoutes();
  setupSearchForm();
  setupSwapButton();

  // Auto-search from URL query params or trigger default full line list
  const urlParams = new URLSearchParams(window.location.search);
  const origin = urlParams.get('origin') || '';
  const dest = urlParams.get('destination') || '';
  const routeNum = urlParams.get('route') || '';

  if (origin || dest) {
    const originInput = document.getElementById('search-origin');
    const destInput = document.getElementById('search-dest');
    if (originInput) originInput.value = origin;
    if (destInput) destInput.value = dest;
    executeSearch(origin, dest);
  } else if (routeNum) {
    selectRouteQuick(routeNum);
  } else {
    // Show all available routes & buses by default
    executeSearch('', '');
  }
});

async function loadStopsAndRoutes() {
  try {
    const [stopsRes, routesRes] = await Promise.all([
      apiRequest('/stops'),
      apiRequest('/routes')
    ]);

    if (stopsRes && stopsRes.stops) {
      allStops = stopsRes.stops;
      populateDatalists(allStops);
    }

    if (routesRes && routesRes.routes) {
      allRoutes = routesRes.routes;
      renderQuickRouteChips(allRoutes);
      populateRouteSelect(allRoutes);
    }
  } catch (err) {
    console.error('Error loading stops & routes:', err);
  }
}

function populateDatalists(stops) {
  let datalist = document.getElementById('transit-stops-list');
  if (!datalist) {
    datalist = document.createElement('datalist');
    datalist.id = 'transit-stops-list';
    document.body.appendChild(datalist);
  }

  datalist.innerHTML = stops.map(s => `
    <option value="${s.name}">${s.name} (${s.code})</option>
  `).join('');

  const originInput = document.getElementById('search-origin');
  const destInput = document.getElementById('search-dest');
  if (originInput) originInput.setAttribute('list', 'transit-stops-list');
  if (destInput) destInput.setAttribute('list', 'transit-stops-list');
}

function renderQuickRouteChips(routes) {
  const container = document.getElementById('quick-route-chips');
  if (!container) return;

  container.innerHTML = routes.map(r => `
    <button type="button" class="route-chip-btn" onclick="selectRouteQuick('${r.route_number}')" style="border-left: 3px solid ${r.color || '#38bdf8'};">
      <span style="font-weight:700;color:#fff;">Route ${r.route_number}</span>
      <span style="font-size:11px;color:#94a3b8;margin-left:4px;">${r.origin} ➔ ${r.destination}</span>
    </button>
  `).join('');
}

function populateRouteSelect(routes) {
  const select = document.getElementById('route-select-dropdown');
  if (!select) return;

  select.innerHTML = '<option value="">-- Or Quick Select by Route Line --</option>' + routes.map(r => `
    <option value="${r.route_number}">Route ${r.route_number}: ${r.name} (${r.origin} ➔ ${r.destination})</option>
  `).join('');

  select.addEventListener('change', (e) => {
    if (e.target.value) {
      selectRouteQuick(e.target.value);
    }
  });
}

function selectRouteQuick(routeNum) {
  const route = allRoutes.find(r => r.route_number === String(routeNum));
  if (route) {
    const originInput = document.getElementById('search-origin');
    const destInput = document.getElementById('search-dest');
    if (originInput) originInput.value = route.origin;
    if (destInput) destInput.value = route.destination;

    const select = document.getElementById('route-select-dropdown');
    if (select) select.value = route.route_number;

    executeSearch(route.origin, route.destination);
  }
}

function setupSwapButton() {
  const swapBtn = document.getElementById('swap-locations-btn');
  if (swapBtn) {
    swapBtn.addEventListener('click', () => {
      const originInput = document.getElementById('search-origin');
      const destInput = document.getElementById('search-dest');
      if (originInput && destInput) {
        const temp = originInput.value;
        originInput.value = destInput.value;
        destInput.value = temp;
        executeSearch(originInput.value, destInput.value);
      }
    });
  }
}

function setupSearchForm() {
  const searchForm = document.getElementById('passenger-search-form');
  if (searchForm) {
    searchForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const origin = document.getElementById('search-origin')?.value || '';
      const dest = document.getElementById('search-dest')?.value || '';
      executeSearch(origin, dest);
    });
  }
}

async function executeSearch(origin, dest) {
  const resultsContainer = document.getElementById('search-results-list');
  if (resultsContainer) {
    resultsContainer.innerHTML = `
      <div style="text-align:center;padding:36px;color:#94a3b8;">
        <i class="fa-solid fa-spinner fa-spin" style="font-size:26px;color:#38bdf8;margin-bottom:12px;"></i>
        <div>Searching active buses, dynamic ETAs & seat counts...</div>
      </div>
    `;
  }

  const res = await apiRequest(`/passenger/search?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(dest)}`);

  if (!resultsContainer) return;

  if (res && res.results) {
    if (res.results.length === 0) {
      resultsContainer.innerHTML = `
        <div class="glass-panel" style="padding:32px 20px;text-align:center;border-radius:16px;">
          <div style="width:50px;height:50px;background:rgba(239,68,68,0.1);border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 12px;">
            <i class="fa-solid fa-route" style="font-size:22px;color:#ef4444;"></i>
          </div>
          <h4 style="color:#fff;margin:0 0 6px;">No Direct Route Found</h4>
          <p style="color:#94a3b8;font-size:13px;margin:0 0 16px;">Try selecting from the suggested stop options or choose one of our active express lines below.</p>
          <button type="button" class="btn-submit" style="display:inline-block;width:auto;padding:8px 20px;" onclick="executeSearch('','')">
            Show All Active Lines
          </button>
        </div>
      `;
      return;
    }

    resultsContainer.innerHTML = res.results.map(r => renderRouteCard(r)).join('');
  } else {
    resultsContainer.innerHTML = '<div style="padding:24px;text-align:center;color:#ef4444;">Failed to connect to transit server.</div>';
  }
}

function renderRouteCard(r) {
  const hasActiveBuses = r.active_buses && r.active_buses.length > 0;

  const busesHtml = hasActiveBuses ? r.active_buses.map(b => {
    const isPhysical = b.bus_number === 'SB-101' || b.hardware_type === 'PHYSICAL_IOT_SB101';
    const occRate = b.occupancy_rate || 0;
    
    // Occupancy color scheme
    let barColor = '#10b981'; // Green
    let badgeClass = 'badge-success';
    if (occRate >= 90) {
      barColor = '#ef4444'; // Red
      badgeClass = 'badge-danger';
    } else if (occRate >= 70) {
      barColor = '#f59e0b'; // Amber
      badgeClass = 'badge-warning';
    }

    return `
      <div class="glass-panel" style="padding:14px 16px;border-radius:12px;margin-top:10px;background:rgba(15,23,42,0.7);border:1px solid rgba(255,255,255,0.07);">
        <!-- Bus Top Header -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:14px;font-weight:800;color:#fff;"><i class="fa-solid fa-bus"></i> ${b.bus_number}</span>
            <span class="badge-tag" style="background:${isPhysical ? 'rgba(16,185,129,0.2)' : 'rgba(56,189,248,0.15)'};color:${isPhysical ? '#10b981' : '#38bdf8'};border:1px solid ${isPhysical ? 'rgba(16,185,129,0.4)' : 'rgba(56,189,248,0.3)'};font-size:10px;">
              ${isPhysical ? '🟢 Physical IoT (SB-101)' : '⚡ Live Simulated'}
            </span>
          </div>
          <div style="text-align:right;">
            <span style="font-size:18px;font-weight:800;color:#38bdf8;">~${b.eta_minutes}m</span>
            <span style="font-size:10px;color:#94a3b8;display:block;">ETA</span>
          </div>
        </div>

        <!-- Real-time Location & Current Status -->
        <div style="display:flex;align-items:center;justify-content:space-between;font-size:12px;color:#cbd5e1;margin-bottom:10px;background:rgba(255,255,255,0.03);padding:8px 10px;border-radius:8px;">
          <div>
            <i class="fa-solid fa-location-crosshairs" style="color:#38bdf8;"></i> 
            <b>${b.current_location_desc || (b.next_stop_name ? 'Approaching ' + b.next_stop_name : 'En Route')}</b>
          </div>
          <div style="color:#94a3b8;font-size:11px;">
            <i class="fa-solid fa-gauge-high"></i> ${b.current_speed || 30} km/h
          </div>
        </div>

        <!-- Seat Availability Section -->
        <div style="margin-bottom:12px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;font-size:12px;">
            <span style="color:#fff;font-weight:600;">
              <i class="fa-solid fa-chair" style="color:${barColor};"></i> 
              <span style="color:#10b981;font-weight:700;">${b.available_seats} Seats Available</span> 
              <span style="color:#64748b;font-size:11px;">(${b.current_passengers || 0}/${b.capacity || 40} taken)</span>
            </span>
            <span class="badge-tag ${badgeClass}" style="font-size:10px;">${b.occupancy_status || (occRate + '% Occ')}</span>
          </div>
          
          <!-- Occupancy Progress Bar -->
          <div style="height:6px;width:100%;background:rgba(255,255,255,0.1);border-radius:4px;overflow:hidden;">
            <div style="height:100%;width:${Math.min(100, occRate)}%;background:${barColor};border-radius:4px;transition:width 0.4s ease;"></div>
          </div>
        </div>

        <!-- Action Buttons -->
        <div style="display:flex;gap:8px;">
          <a href="tracking.html?bus_id=${b.bus_id}&route_id=${r.route_id}" class="action-btn" style="flex:1;text-align:center;text-decoration:none;font-size:12px;padding:7px 10px;background:rgba(56,189,248,0.15);color:#38bdf8;border:1px solid rgba(56,189,248,0.3);border-radius:8px;">
            <i class="fa-solid fa-map-location-dot"></i> Live Track
          </a>
          <a href="seat-status.html?bus_id=${b.bus_id}" class="action-btn" style="flex:1;text-align:center;text-decoration:none;font-size:12px;padding:7px 10px;background:rgba(16,185,129,0.15);color:#10b981;border:1px solid rgba(16,185,129,0.3);border-radius:8px;">
            <i class="fa-solid fa-chair"></i> View 2D Seats
          </a>
        </div>
      </div>
    `;
  }).join('') : `
    <div style="padding:14px;background:rgba(255,255,255,0.02);border-radius:10px;margin-top:10px;text-align:center;font-size:12px;color:#94a3b8;">
      <i class="fa-solid fa-clock"></i> Next scheduled bus departing in ~10 mins
    </div>
  `;

  // Stops itinerary preview
  const stopsPreview = r.stops && r.stops.length > 0
    ? `<div style="font-size:11px;color:#64748b;margin-top:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
        <i class="fa-solid fa-signs-post"></i> Stops: ${r.stops.map(s => s.name).join(' ➔ ')}
       </div>`
    : '';

  return `
    <div class="glass-panel" style="padding:18px;margin-bottom:16px;border-radius:14px;border-top:3px solid ${r.color || '#38bdf8'};">
      <!-- Route Title Header -->
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
        <div style="display:flex;align-items:center;gap:8px;">
          <span class="badge-tag" style="background:${r.color || '#38bdf8'};color:#fff;font-weight:800;font-size:11px;padding:3px 9px;">
            Route ${r.route_number}
          </span>
          <h4 style="font-size:15px;margin:0;color:#fff;font-weight:700;">${r.route_name}</h4>
        </div>
        <div style="font-size:16px;font-weight:800;color:#10b981;">
          ₹${Number(r.fare).toFixed(2)}
        </div>
      </div>

      <!-- Route Terminus Info -->
      <div style="font-size:12px;color:#94a3b8;margin-bottom:6px;">
        <i class="fa-solid fa-location-dot" style="color:#ef4444;"></i> <b>${r.origin}</b> ➔ <b>${r.destination}</b>
        <span style="margin-left:8px;color:#64748b;">(${r.distance_km} km • ~${r.estimated_duration_mins} mins)</span>
      </div>

      ${stopsPreview}

      <!-- Active Buses List for this Route -->
      <div style="margin-top:10px;">
        <div style="font-size:11px;font-weight:700;color:#38bdf8;text-transform:uppercase;letter-spacing:0.5px;display:flex;align-items:center;justify-content:space-between;">
          <span><i class="fa-solid fa-satellite-dish"></i> Live Buses On Route (${r.active_buses ? r.active_buses.length : 0})</span>
        </div>
        ${busesHtml}
      </div>
    </div>
  `;
}
