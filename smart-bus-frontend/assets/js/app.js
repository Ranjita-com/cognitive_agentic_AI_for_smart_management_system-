/**
 * ============================================================
 * SMART BUS - CORE CLIENT APPLICATION & WEBSOCKET ENGINE
 * ============================================================
 */

const API_BASE = '/api';

// Global App State
const AppState = {
  user: null,
  socket: null,
  buses: {},
  routes: [],
  stops: [],
  alerts: []
};

// API Fetch Helper
async function apiRequest(endpoint, method = 'GET', data = null) {
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    }
  };

  if (data && (method === 'POST' || method === 'PUT')) {
    options.body = JSON.stringify(data);
  }

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, options);
    const json = await response.json();
    return json;
  } catch (error) {
    console.error(`[API Error] ${method} ${endpoint}:`, error);
    return { success: false, message: 'Network error or server unreachable.' };
  }
}

// WebSocket Initialization
function initSocket() {
  if (typeof io === 'undefined') return;

  const socket = io();
  AppState.socket = socket;

  socket.on('connect', () => {
    console.log('[WebSocket] Connected to Smart Bus Server.');
    const liveBadges = document.querySelectorAll('.live-indicator span');
    liveBadges.forEach(b => b.textContent = 'Fleet Live');
  });

  socket.on('bus_update', (data) => {
    if (data && data.bus) {
      AppState.buses[data.bus.id] = data.bus;
      document.dispatchEvent(new CustomEvent('busTelemetryUpdate', { detail: data }));
    }
  });

  socket.on('bus_reallocated', (data) => {
    console.warn('[AI REALLOCATION EVENT]', data);
    document.dispatchEvent(new CustomEvent('busReallocated', { detail: data }));
  });

  socket.on('emergency_sos', (data) => {
    console.warn('[SOS RECEIVED]', data);
    document.dispatchEvent(new CustomEvent('emergencySosAlert', { detail: data }));
  });

  socket.on('new_alert', (data) => {
    document.dispatchEvent(new CustomEvent('newFleetAlert', { detail: data }));
  });

  socket.on('disconnect', () => {
    console.warn('[WebSocket] Disconnected from server.');
  });
}

// Global Toast Notification
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:99999;display:flex;flex-direction:column;gap:10px;';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  const colors = {
    info: 'linear-gradient(135deg, #0284c7, #0369a1)',
    success: 'linear-gradient(135deg, #10b981, #059669)',
    warning: 'linear-gradient(135deg, #f59e0b, #d97706)',
    danger: 'linear-gradient(135deg, #ef4444, #dc2626)'
  };

  toast.style.cssText = `background:${colors[type] || colors.info};color:#fff;padding:12px 18px;border-radius:8px;font-size:13px;font-weight:600;box-shadow:0 8px 20px rgba(0,0,0,0.4);display:flex;align-items:center;gap:10px;animation:fadeIn 0.3s ease-out;`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.4s ease';
    setTimeout(() => toast.remove(), 400);
  }, 4000);
}

// Audio Siren for Emergency SOS
function playEmergencyAlarm() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(800, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(1400, ctx.currentTime + 0.3);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.6);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.6);
  } catch (e) {}
}

// Reset Entire Fleet Data to Pristine Defaults (Undo Swaps, Default Routes, SB-101 6 Seats)
async function resetFleetData() {
  if (!confirm("Are you sure you want to reset all fleet data to initial defaults?\n\nThis will:\n• Undo all bus swaps\n• Put Bus SB-101 on Line 101 with 6 seats & 0 passengers\n• Put Bus SB-102 on Line 202 (40 seats)\n• Put Bus SB-103 on Line 303 (42 seats)\n• Clear active emergency alerts and simulator anomalies")) {
    return;
  }
  showToast("Restoring fleet routes and initial defaults...", "info");
  const res = await apiRequest('/fleet/reset', 'POST');
  if (res && res.success) {
    showToast(res.message || "Fleet successfully restored to initial defaults!", "success");
    setTimeout(() => {
      window.location.reload();
    }, 600);
  } else {
    showToast(res.message || "Failed to reset fleet data.", "danger");
  }
}

// ============================================================
// THEME MANAGEMENT ENGINE (Classic Cyber & Executive Pro)
// ============================================================

const THEMES = {
  CYBER: 'cyber',
  EXECUTIVE: 'executive'
};

function getCurrentTheme() {
  const saved = localStorage.getItem('smartbus_theme');
  // Default to Classic Cyber
  if (!saved || saved === 'executive') {
    localStorage.setItem('smartbus_theme', THEMES.CYBER);
    return THEMES.CYBER;
  }
  return saved || THEMES.CYBER;
}

function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === THEMES.EXECUTIVE) {
    root.setAttribute('data-theme', 'executive');
  } else {
    root.setAttribute('data-theme', 'cyber');
  }

  // Update Admin Theme Buttons with clear active indicator
  const adminThemeBtns = document.querySelectorAll('.theme-switch-btn, #theme-toggle-btn, #admin-theme-toggle');
  adminThemeBtns.forEach(btn => {
    if (theme === THEMES.EXECUTIVE) {
      btn.innerHTML = '<i class="fa-solid fa-briefcase" style="color:#2563eb;"></i> <span>Executive Pro</span> <span class="theme-active-dot" title="Active Theme"></span>';
      btn.title = "Current Theme: Executive Pro (Click to switch to Classic Cyber)";
    } else {
      btn.innerHTML = '<i class="fa-solid fa-bolt" style="color:#38bdf8;"></i> <span>Classic Cyber</span> <span class="theme-active-dot" title="Active Theme"></span>';
      btn.title = "Current Theme: Classic Cyber (Click to switch to Executive Pro)";
    }
  });

  // Update Passenger Theme Buttons with clear active indicator
  const passengerThemeBtns = document.querySelectorAll('.passenger-theme-toggle, #passenger-theme-btn, #passenger-theme-toggle');
  passengerThemeBtns.forEach(btn => {
    if (theme === THEMES.EXECUTIVE) {
      btn.innerHTML = '<i class="fa-solid fa-briefcase" style="color:#2563eb;"></i> <span>Executive</span> <span class="theme-active-dot"></span>';
      btn.title = "Current Theme: Executive Pro (Click to switch to Classic Cyber)";
    } else {
      btn.innerHTML = '<i class="fa-solid fa-bolt" style="color:#38bdf8;"></i> <span>Cyber</span> <span class="theme-active-dot"></span>';
      btn.title = "Current Theme: Classic Cyber (Click to switch to Executive Pro)";
    }
  });

  document.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
}

function toggleTheme() {
  const current = getCurrentTheme();
  const nextTheme = (current === THEMES.EXECUTIVE) ? THEMES.CYBER : THEMES.EXECUTIVE;
  localStorage.setItem('smartbus_theme', nextTheme);
  applyTheme(nextTheme);

  if (typeof showToast === 'function') {
    if (nextTheme === THEMES.EXECUTIVE) {
      showToast('Switched to Executive Pro Theme', 'info');
    } else {
      showToast('Switched to Classic Cyber Theme', 'info');
    }
  }
}

// Alias for explicit button triggers
window.toggleAppTheme = toggleTheme;
window.toggleTheme = toggleTheme;

// Auto-inject Theme Toggle button into headers if missing
function ensureThemeButtons() {
  const current = getCurrentTheme();

  // 1. Admin Navbar Injection
  const adminNavRight = document.querySelector('.admin-navbar .nav-right');
  if (adminNavRight && !adminNavRight.querySelector('.theme-switch-btn, #admin-theme-toggle, #theme-toggle-btn')) {
    const btn = document.createElement('button');
    btn.id = 'admin-theme-toggle';
    btn.className = 'action-btn theme-switch-btn';
    btn.type = 'button';
    btn.onclick = toggleTheme;
    btn.innerHTML = '<i class="fa-solid fa-bolt" style="color:#38bdf8;"></i> <span>Classic Cyber</span> <span class="theme-active-dot"></span>';
    btn.title = 'Current Theme: Classic Cyber (Click to switch)';
    adminNavRight.insertBefore(btn, adminNavRight.firstChild);
  }

  // 2. Passenger Header Injection
  const passengerNavTop = document.querySelector('.passenger-nav-top');
  if (passengerNavTop && !passengerNavTop.querySelector('.passenger-theme-toggle, #passenger-theme-toggle, #passenger-theme-btn')) {
    const rightCluster = passengerNavTop.children[1] || passengerNavTop;
    const btn = document.createElement('button');
    btn.id = 'passenger-theme-toggle';
    btn.className = 'passenger-theme-toggle';
    btn.type = 'button';
    btn.onclick = toggleTheme;
    btn.innerHTML = '<i class="fa-solid fa-bolt" style="color:#38bdf8;"></i> <span>Cyber</span> <span class="theme-active-dot"></span>';
    btn.title = 'Current Theme: Classic Cyber (Click to switch)';
    
    if (rightCluster && rightCluster !== passengerNavTop) {
      rightCluster.insertBefore(btn, rightCluster.firstChild);
    } else {
      passengerNavTop.appendChild(btn);
    }
  }

  // Re-apply label state
  applyTheme(current);
}

// Listen to storage events across different tabs/windows
window.addEventListener('storage', (e) => {
  if (e.key === 'smartbus_theme') {
    applyTheme(e.newValue || THEMES.CYBER);
  }
});

// Immediate Theme Pre-load
(function() {
  const saved = getCurrentTheme();
  if (saved === THEMES.EXECUTIVE) {
    document.documentElement.setAttribute('data-theme', 'executive');
  } else {
    document.documentElement.setAttribute('data-theme', 'cyber');
  }
})();

document.addEventListener('DOMContentLoaded', () => {
  initSocket();
  ensureThemeButtons();
});

