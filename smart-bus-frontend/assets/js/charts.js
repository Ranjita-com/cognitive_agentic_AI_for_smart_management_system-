/**
 * ============================================================
 * SMART BUS - CHART.JS ANALYTICS & FLEET METRICS CHARTS
 * ============================================================
 */

function initPassengerHourlyChart(canvasId = 'passenger-hourly-chart') {
  const ctx = document.getElementById(canvasId);
  if (!ctx || typeof Chart === 'undefined') return;

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: ['06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00'],
      datasets: [
        {
          label: 'Route 101 (Green Line)',
          data: [45, 185, 120, 95, 110, 195, 230, 140, 60],
          borderColor: '#10b981',
          backgroundColor: 'rgba(16, 185, 129, 0.1)',
          fill: true,
          tension: 0.4
        },
        {
          label: 'Route 202 (Airport)',
          data: [30, 110, 140, 130, 125, 170, 160, 120, 85],
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          fill: true,
          tension: 0.4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { family: 'Inter' } } }
      },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64748b' } },
        y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64748b' } }
      }
    }
  });
}

function initPunctualityChart(canvasId = 'punctuality-chart') {
  const ctx = document.getElementById(canvasId);
  if (!ctx || typeof Chart === 'undefined') return;

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['On-Time (<3m)', 'Slight Delay (3-8m)', 'Major Delay (>8m)'],
      datasets: [{
        data: [88, 9, 3],
        backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#94a3b8' } }
      },
      cutout: '72%'
    }
  });
}
