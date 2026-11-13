/**
 * ============================================================
 * SMART BUS - FLEET DASHBOARD TELEMETRY & METRICS CONTROLLER
 * ============================================================
 */

document.addEventListener('DOMContentLoaded', async () => {
  // Initialize Mini Map on Dashboard if container exists
  if (document.getElementById('fleet-mini-map')) {
    const miniMap = new SmartBusMap('fleet-mini-map');
    miniMap.init([12.9850, 77.6100], 12);
  }

  // Load KPI Stats
  loadDashboardData();

  // Listen for real-time WebSocket bus telemetry
  document.addEventListener('busTelemetryUpdate', (e) => {
    updateTelemetryWidget(e.detail.bus);
  });

  // Listen for Emergency SOS events
  document.addEventListener('emergencySosAlert', (e) => {
    handleEmergencyAlert(e.detail);
  });

  // Listen for Autonomous Bus Reallocation events
  document.addEventListener('busReallocated', (e) => {
    const d = e.detail;
    showToast(`🤖 [AI AUTO-REALLOCATION] Route ${d.route_number} transferred from ${d.degraded_bus?.bus_number} to Standby Bus ${d.replacement_bus?.bus_number}!`, 'warning');
    loadDashboardData();
  });
});

async function loadDashboardData() {
  const [busesRes, alertsRes, recsRes, maintRes] = await Promise.all([
    apiRequest('/buses'),
    apiRequest('/alerts?limit=8'),
    apiRequest('/fleet/recommendations'),
    apiRequest('/maintenance/overview')
  ]);

  // Update KPI Cards
  if (busesRes && busesRes.buses) {
    const totalBuses = busesRes.buses.length;
    const activeBuses = busesRes.buses.filter(b => b.status === 'active').length;
    const totalPassengers = busesRes.buses.reduce((acc, b) => acc + b.current_passengers, 0);
    const avgSafety = (busesRes.buses.reduce((acc, b) => acc + b.safety_score, 0) / totalBuses).toFixed(1);

    document.getElementById('kpi-active-buses')?.replaceChildren(document.createTextNode(`${activeBuses}/${totalBuses}`));
    document.getElementById('kpi-passengers-transit')?.replaceChildren(document.createTextNode(totalPassengers));
    document.getElementById('kpi-safety-score')?.replaceChildren(document.createTextNode(`${avgSafety}%`));
  }

  // Update Alert Feeds
  if (alertsRes && alertsRes.alerts) {
    renderAlertList(alertsRes.alerts);
    const activeAlertsCount = alertsRes.alerts.filter(a => a.status === 'ACTIVE').length;
    document.getElementById('kpi-active-alerts')?.replaceChildren(document.createTextNode(activeAlertsCount));
  }

  // Update Fleet Agent Recommendations
  if (recsRes && recsRes.recommendations) {
    renderRecommendations(recsRes.recommendations);
  }

  // Update Maintenance Fleet Health
  if (maintRes && maintRes.data) {
    document.getElementById('kpi-fleet-health')?.replaceChildren(document.createTextNode(`${maintRes.data.fleet_health_index}%`));
  }
}

function renderAlertList(alerts) {
  const container = document.getElementById('dashboard-alert-list');
  if (!container) return;

  if (alerts.length === 0) {
    container.innerHTML = `<li style="padding:16px;text-align:center;color:#64748b;">No active alerts. Fleet operating normally.</li>`;
    return;
  }

  container.innerHTML = alerts.map(a => `
    <li class="alert-item severity-${a.severity}">
      <div class="alert-icon">
        <i class="fa-solid ${a.severity === 'CRITICAL' ? 'fa-triangle-exclamation' : (a.severity === 'WARNING' ? 'fa-bell' : 'fa-circle-info')}"></i>
      </div>
      <div class="alert-content">
        <div class="alert-title">${a.message}</div>
        <div class="alert-time">${new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • Bus ${a.bus_number}</div>
      </div>
      ${a.status === 'ACTIVE' ? `<button class="action-btn" style="padding:4px 8px;font-size:11px;" onclick="resolveAlertById(${a.id})">Acknowledge</button>` : `<span class="badge-tag badge-success">Resolved</span>`}
    </li>
  `).join('');
}

function renderRecommendations(recs) {
  const container = document.getElementById('dashboard-recommendations');
  if (!container) return;

  if (recs.length === 0) {
    container.innerHTML = `<p style="color:#64748b;font-size:13px;">Optimal route headways maintained. No dispatch interventions required.</p>`;
    return;
  }

  container.innerHTML = recs.map(r => {
    // If this is a Maintenance Swap proposal with a suggested standby candidate
    if (r.can_reallocate && r.suggested_replacement && r.degraded_bus) {
      const deg = r.degraded_bus;
      const rep = r.suggested_replacement;
      const isReal101 = (deg.bus_number === 'SB-101');

      return `
        <div class="ai-swap-card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <div style="display:flex;align-items:center;gap:8px;">
              <span class="badge-tag badge-purple" style="font-size:11px;"><i class="fa-solid fa-robot"></i> AI FLEET AGENT PROPOSAL</span>
              <span class="badge-tag badge-danger" style="font-size:10px;">ACTION REQUIRED</span>
            </div>
            <span style="font-size:11px;color:#94a3b8;font-family:monospace;">Route: ${deg.route_name}</span>
          </div>

          <h5 style="color:#fff;font-size:14px;margin-bottom:4px;">
            <i class="fa-solid fa-triangle-exclamation" style="color:#ef4444;"></i> Replace ${deg.bus_number} (${deg.health_score.toFixed(0)}% Health) with Standby ${rep.bus_number} (${rep.health_score.toFixed(0)}% Health)
          </h5>
          <p style="font-size:12px;color:#cbd5e1;margin-bottom:12px;">
            ${deg.bus_number} exhibits critical health degradation. The Fleet Optimization Agent recommends swapping with healthy standby ${rep.bus_number} to prevent commuter disruption.
          </p>

          <!-- Side-by-Side Bus Comparison -->
          <div class="ai-swap-grid">
            <!-- Left: Degraded Bus -->
            <div class="ai-swap-box degraded">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <b style="color:#ef4444;font-size:13px;"><i class="fa-solid fa-bus"></i> ${deg.bus_number}</b>
                <span class="badge-tag badge-danger" style="font-size:9px;">NEEDS REPAIR</span>
              </div>
              <div style="font-size:11px;color:#cbd5e1;">Health Score: <b style="color:#ef4444;">${deg.health_score.toFixed(0)}%</b></div>
              <div style="font-size:11px;color:#94a3b8;">Active on: ${deg.route_name}</div>
              <div style="font-size:10px;color:#94a3b8;margin-top:2px;">Hardware: ${isReal101 ? 'Physical ESP32-S3' : 'Simulated Unit'}</div>
            </div>

            <!-- Middle: Arrow -->
            <div class="ai-swap-arrow">
              <i class="fa-solid fa-right-left"></i>
              <span style="font-size:9px;color:#a855f7;font-weight:700;margin-top:2px;">SWAP</span>
            </div>

            <!-- Right: Recommended Standby Replacement -->
            <div class="ai-swap-box replacement">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <b style="color:#10b981;font-size:13px;"><i class="fa-solid fa-bus"></i> ${rep.bus_number}</b>
                <span class="badge-tag badge-success" style="font-size:9px;">PRISTINE STANDBY</span>
              </div>
              <div style="font-size:11px;color:#cbd5e1;">Health Score: <b style="color:#10b981;">${rep.health_score.toFixed(0)}%</b></div>
              <div style="font-size:11px;color:#94a3b8;">Status: Ready in Depot</div>
              <div style="font-size:10px;color:#38bdf8;margin-top:2px;">Capacity: ${rep.capacity} Seats</div>
            </div>
          </div>

          <!-- Bottom Approval Question & Execution Actions -->
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.08);">
            <div style="font-size:12px;color:#e2e8f0;">
              <b>Approve Agent Swap:</b> Replace ${deg.bus_number} with ${rep.bus_number}?
            </div>
            <div style="display:flex;gap:8px;">
              <button class="btn-ai-approve" onclick="approveBusReallocation(${deg.bus_id}, ${rep.bus_id}, '${deg.bus_number}', '${rep.bus_number}', '${deg.route_name}')">
                <i class="fa-solid fa-bolt"></i> Approve & Execute Bus Swap
              </button>
            </div>
          </div>
        </div>
      `;
    }

    // Standard Recommendation Card
    return `
      <div class="agent-rec-card">
        <div class="agent-rec-header">
          <span class="agent-rec-badge">${r.category}</span>
          <span style="font-size:11px;color:#94a3b8;font-weight:600;">Priority: ${r.priority}</span>
        </div>
        <h5 style="font-size:14px;margin-bottom:4px;color:#fff;">${r.title}</h5>
        <p style="font-size:12px;color:#cbd5e1;margin-bottom:10px;">${r.message}</p>
        <button class="action-btn btn-primary" style="padding:5px 12px;font-size:11px;">
          <i class="fa-solid fa-bolt"></i> ${r.action || r.recommended_action}
        </button>
      </div>
    `;
  }).join('');
}

async function approveBusReallocation(degradedBusId, replacementBusId, degradedBusNumber, replacementBusNumber, routeName) {
  const confirmed = confirm(
    `🤖 AI FLEET AGENT DISPATCH APPROVAL:\n\n` +
    `Do you approve automated replacement of Bus ${degradedBusNumber} with Standby Bus ${replacementBusNumber} on ${routeName}?\n\n` +
    `• ${replacementBusNumber} will be activated and assigned to ${routeName}\n` +
    `• ${degradedBusNumber} will be transferred to depot workshop for urgent maintenance\n\n` +
    `Click OK to execute automated agent swap.`
  );

  if (!confirmed) return;

  const res = await apiRequest('/fleet/approve-reallocation', 'POST', {
    degraded_bus_id: degradedBusId,
    replacement_bus_id: replacementBusId,
    reason: `Admin Approved Agent Swap (${degradedBusNumber} -> ${replacementBusNumber})`
  });

  if (res && res.success) {
    showToast(`🎉 [AI AGENT EXECUTION COMPLETE] ${routeName} successfully transferred from ${degradedBusNumber} to ${replacementBusNumber}! ${degradedBusNumber} routed to maintenance.`, 'success');
    loadDashboardData();
  } else {
    showToast(res.message || 'Failed to execute fleet reallocation.', 'danger');
  }
}


function updateTelemetryWidget(bus) {
  // Update live passenger total counter
  const passEl = document.getElementById(`bus-occ-${bus.id}`);
  if (passEl) {
    passEl.textContent = `${bus.current_passengers}/${bus.capacity}`;
  }
}

function handleEmergencyAlert(data) {
  playEmergencyAlarm();
  showToast(`EMERGENCY SOS Triggered on Bus ${data.bus_number || data.bus_id}!`, 'danger');
  
  // Refresh alerts list
  loadDashboardData();
}

async function resolveAlertById(alertId) {
  const res = await apiRequest(`/alerts/${alertId}/resolve`, 'PUT');
  if (res.success) {
    showToast('Alert resolved.', 'success');
    loadDashboardData();
  }
}
