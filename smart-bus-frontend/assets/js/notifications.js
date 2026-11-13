/**
 * ============================================================
 * SMART BUS - NOTIFICATIONS & ALERT HUB CONTROLLER
 * ============================================================
 */

document.addEventListener('DOMContentLoaded', async () => {
  const alertCenter = document.getElementById('full-notification-list');
  if (alertCenter) {
    loadAllNotifications();
  }

  // Real-time listener for incoming alerts / broadcasts
  document.addEventListener('newFleetAlert', () => {
    loadAllNotifications();
  });

  const broadcastForm = document.getElementById('broadcast-alert-form');
  if (broadcastForm) {
    broadcastForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const msgInput = document.getElementById('broadcast-msg');
      const severityInput = document.getElementById('broadcast-severity');
      const msg = msgInput.value.trim();
      const severity = severityInput.value;
      
      if (!msg) return;

      const submitBtn = broadcastForm.querySelector('button[type="submit"]');
      const origText = submitBtn ? submitBtn.innerHTML : '';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Dispatching Broadcast...';
      }

      const res = await apiRequest('/alerts/broadcast', 'POST', {
        message: msg,
        severity: severity,
        alert_type: 'BROADCAST'
      });

      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = origText;
      }

      if (res && res.success) {
        showToast(`Broadcast Dispatched: "${msg}" to all passenger apps & fleet terminals.`, severity === 'CRITICAL' ? 'danger' : 'success');
        broadcastForm.reset();
        loadAllNotifications();
      } else {
        showToast(res.message || 'Failed to dispatch broadcast alert.', 'danger');
      }
    });
  }
});

async function loadAllNotifications() {
  const container = document.getElementById('full-notification-list');
  if (!container) return;

  const res = await apiRequest('/alerts?limit=50');
  if (res && res.alerts) {
    if (res.alerts.length === 0) {
      container.innerHTML = '<div style="padding:24px;text-align:center;color:#64748b;">No alerts recorded in the system.</div>';
      return;
    }

    container.innerHTML = res.alerts.map(a => `
      <div class="glass-panel" style="padding:16px 20px;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;border-left:4px solid ${a.severity === 'CRITICAL' ? '#ef4444' : (a.severity === 'WARNING' ? '#f59e0b' : '#38bdf8')};">
        <div>
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
            <span class="badge-tag badge-${a.severity === 'CRITICAL' ? 'danger' : (a.severity === 'WARNING' ? 'warning' : 'info')}">
              <i class="fa-solid ${a.alert_type === 'BROADCAST' ? 'fa-bullhorn' : (a.alert_type === 'SOS' ? 'fa-triangle-exclamation' : (a.alert_type === 'OVERCROWDING' ? 'fa-users' : 'fa-bell'))}"></i>
              ${a.alert_type}
            </span>
            <b style="color:#fff;font-size:14px;">${a.message}</b>
          </div>
          <div style="font-size:12px;color:#64748b;">
            ${new Date(a.created_at).toLocaleString()} • Scope: <b>${a.bus_number || 'All Fleet / All Passengers'}</b>
          </div>
        </div>
        <div>
          ${a.status === 'ACTIVE' ? `<button class="action-btn" onclick="resolveNotification(${a.id})"><i class="fa-solid fa-check"></i> Resolve</button>` : `<span class="badge-tag badge-success">Resolved</span>`}
        </div>
      </div>
    `).join('');
  }
}

async function resolveNotification(alertId) {
  const res = await apiRequest(`/alerts/${alertId}/resolve`, 'PUT');
  if (res.success) {
    showToast('Alert resolved.', 'success');
    loadAllNotifications();
  }
}
