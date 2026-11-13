/**
 * ============================================================
 * SMART BUS - REAL-WORLD GIS LEAFLET MAP ENGINE
 * ============================================================
 * Features:
 * - 100% Free Natural Street Maps (OpenStreetMap - No API Key, No Watermark)
 * - Satellite View (Esri World Imagery) & Topo Layers via Map Switcher
 * - Separate Multi-Route Corridors (Green Line 101, Blue Line 202, Red Line 303)
 * - Explicit On-Map Permanent Route Stop Badges (Hospital, School, Market, Bus Terminal, etc.)
 * - Live Bus Markers with Dynamic Vector Icons, Heading Arrows, and IoT vs Auto-Sim Badges
 * - High-Priority Z-Index for Physical IoT Bus SB-101
 * - Interactive Bus Stop Pins & Route Corridor Filtering
 */

class SmartBusMap {
  constructor(containerId = 'fleet-map', options = {}) {
    this.containerId = containerId;
    this.map = null;
    this.busMarkers = {};
    this.stopMarkers = {};
    this.routeLayers = {};
    this.haloLayers = {};
    this.routesData = {};
    this.selectedBusId = null;
    this.baseLayers = {};
    this.options = options;
  }

  init(center = [12.9850, 77.6100], zoom = 13) {
    if (!document.getElementById(this.containerId)) return;
    if (typeof L === 'undefined') return;

    this.map = L.map(this.containerId, {
      zoomControl: true,
      attributionControl: true
    }).setView(center, zoom);

    // 1. Natural Standard Street Map (Original Real Colors - 100% Free, Zero API Key)
    const streetMap = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      subdomains: ['a', 'b', 'c'],
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'
    });

    // 2. High-Resolution Satellite View (Esri World Imagery - 100% Free, Zero API Key)
    const satelliteMap = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19,
      attribution: 'Tiles &copy; Esri &mdash; Earthstar Geographics'
    });

    // 3. Topographic Terrain Map
    const topoMap = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      maxZoom: 17,
      subdomains: ['a', 'b', 'c'],
      attribution: 'Map data: &copy; OpenStreetMap contributors, SRTM'
    });

    // Default to natural street map
    streetMap.addTo(this.map);

    this.baseLayers = {
      '🗺️ Standard Street Map': streetMap,
      '🛰️ Real Satellite Imagery': satelliteMap,
      '⛰️ Terrain / Topo': topoMap
    };

    // Add Layer Switcher Control in Top Right
    L.control.layers(this.baseLayers, null, { position: 'topright', collapsed: true }).addTo(this.map);

    this.addFloatingQuickControls();
    this.loadRoutesAndStops();
    this.bindSocketEvents();
  }

  addFloatingQuickControls() {
    const container = document.getElementById(this.containerId);
    if (!container) return;

    const quickDiv = document.createElement('div');
    quickDiv.className = 'map-quick-actions';
    quickDiv.innerHTML = `
      <button class="map-btn-action" title="Recenter Map View" onclick="if(window.fullMap) window.fullMap.recenter(); if(window.pMap) window.pMap.recenter();">
        <i class="fa-solid fa-crosshairs"></i>
      </button>
      <button class="map-btn-action" title="Fit All Active Buses" onclick="if(window.fullMap) window.fullMap.fitAllBuses(); if(window.pMap) window.pMap.fitAllBuses();">
        <i class="fa-solid fa-bus"></i>
      </button>
    `;
    container.appendChild(quickDiv);
  }

  async loadRoutesAndStops() {
    try {
      const [routesRes, stopsRes, busesRes] = await Promise.all([
        apiRequest('/routes'),
        apiRequest('/stops'),
        apiRequest('/buses')
      ]);

      // 1. Render Multi-Route Corridors with High-Visibility Colors
      if (routesRes && routesRes.routes) {
        routesRes.routes.forEach(route => {
          try {
            this.routesData[route.id] = route;
            const routeColor = route.color || (route.route_number === '101' ? '#10b981' : (route.route_number === '202' ? '#3b82f6' : '#ef4444'));

            if (route.polyline && route.polyline.length > 0) {
              // Broad glowing corridor underlay
              const haloLayer = L.polyline(route.polyline, {
                color: routeColor,
                weight: 10,
                opacity: 0.35,
                lineCap: 'round',
                lineJoin: 'round'
              }).addTo(this.map);
              this.haloLayers[route.id] = haloLayer;

              // Crisp core transit track
              const polylineLayer = L.polyline(route.polyline, {
                color: routeColor,
                weight: 5,
                opacity: 0.95,
                lineCap: 'round',
                lineJoin: 'round'
              }).addTo(this.map);

              const stopProgressionText = route.route_number === '101' 
                ? '🏥 Hospital Stop ➔ 🏫 School Zone ➔ 🛒 Market Area ➔ 🚌 Bus Terminal'
                : (route.route_number === '202'
                  ? '✈️ Airport Terminal ➔ 🏢 Aerospace Tech Park ➔ 🛣️ Highway Interchange ➔ 🏙️ Downtown District'
                  : '🎓 University Campus ➔ 🏥 Medical College ➔ 🎭 Civic Arts Center ➔ 🛍️ South Commercial Mall');

              polylineLayer.bindTooltip(
                `<div style="font-family:sans-serif;padding:6px 10px;font-size:12px;">
                  <b style="color:${routeColor};font-size:13px;">Line ${route.route_number} (${route.name})</b><br>
                  <span style="color:#0f172a;font-weight:600;">${stopProgressionText}</span>
                </div>`,
                { sticky: true }
              );
              this.routeLayers[route.id] = polylineLayer;
            }
          } catch (err) {
            console.error('Error rendering route:', route, err);
          }
        });

        this.renderRouteLegend(routesRes.routes);
      }

      // 2. Render Real Bus Stops with Route Color Pins and Permanent On-Map Labels
      if (stopsRes && stopsRes.stops) {
        stopsRes.stops.forEach(stop => {
          try {
            let stopColor = '#0284c7';
            let stopSeq = '';
            if (stop.code && stop.code.startsWith('ST-1')) {
              stopColor = '#10b981';
              stopSeq = stop.code.replace('ST-10', '');
            } else if (stop.code && stop.code.startsWith('ST-2')) {
              stopColor = '#3b82f6';
              stopSeq = stop.code.replace('ST-20', '');
            } else if (stop.code && stop.code.startsWith('ST-3')) {
              stopColor = '#ef4444';
              stopSeq = stop.code.replace('ST-30', '');
            }

            const stopHtml = `
              <div class="custom-stop-marker" id="marker-stop-${stop.id}">
                <div class="stop-pin-head" style="background:${stopColor};">
                  <span>${stopSeq || '🚏'}</span>
                </div>
                <div class="stop-permanent-label" style="border-left:3px solid ${stopColor};">
                  <span class="stop-code-badge" style="background:${stopColor};">${stop.code}</span>
                  <span><b>${stop.name}</b></span>
                </div>
              </div>
            `;

            const stopIcon = L.divIcon({
              className: 'stop-marker-wrapper',
              html: stopHtml,
              iconSize: [40, 40],
              iconAnchor: [20, 12]
            });

            const marker = L.marker([stop.latitude, stop.longitude], { 
              icon: stopIcon,
              zIndexOffset: 800 
            }).addTo(this.map);

            marker.bindPopup(`
              <div style="font-family:sans-serif;padding:8px;min-width:210px;color:#cbd5e1;">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                  <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:${stopColor};box-shadow:0 0 8px ${stopColor};"></span>
                  <b style="font-size:15px;color:#ffffff;font-weight:700;">🚏 ${stop.name}</b>
                </div>
                <div style="font-size:11px;color:#94a3b8;margin-bottom:6px;">
                  Stop Code: <b style="color:#f8fafc;">${stop.code}</b> • RFID Tag: <b style="color:#f8fafc;">${stop.rfid_tag || 'N/A'}</b>
                </div>
                <p style="font-size:12px;color:#e2e8f0;margin:4px 0 8px;line-height:1.4;">📍 ${stop.address}</p>
                <div style="font-size:11px;color:#10b981;font-weight:600;display:flex;align-items:center;gap:4px;">
                  <i class="fa-solid fa-sparkles"></i> Amenities: ${(stop.amenities || []).join(', ') || 'Shelter, Seating'}
                </div>
              </div>
            `);
            this.stopMarkers[stop.id] = marker;
          } catch (err) {
            console.error('Error rendering stop:', stop, err);
          }
        });
      }

      // 3. Render Initial Fleet Buses
      if (busesRes && busesRes.buses) {
        busesRes.buses.forEach(bus => {
          try {
            this.updateBusMarker(bus);
          } catch (err) {
            console.error('Error rendering bus:', bus, err);
          }
        });

        // Focus selected bus or auto-fit all active buses
        if (this.selectedBusId && this.busMarkers[this.selectedBusId]) {
          this.selectBus(this.selectedBusId);
        } else {
          setTimeout(() => {
            this.fitAllBuses();
          }, 300);
        }
      }
    } catch (error) {
      console.error('[Map Error] Failed to load routes and stops:', error);
    }
  }

  getBusColor(bus) {
    if (bus.route_color) return bus.route_color;
    if (bus.route_number === '101' || bus.bus_number === 'SB-101') return '#10b981'; // Green
    if (bus.route_number === '202' || bus.bus_number === 'SB-102') return '#3b82f6'; // Blue
    if (bus.route_number === '303' || bus.bus_number === 'SB-103') return '#ef4444'; // Red
    return '#10b981';
  }

  updateBusMarker(bus) {
    if (!this.map || !bus) return;

    const lat = parseFloat(bus.current_lat);
    const lng = parseFloat(bus.current_lng);
    if (isNaN(lat) || isNaN(lng)) return;

    const isReal = (bus.bus_number === 'SB-101' || bus.data_source === 'REAL' || bus.hardware_available);
    const busColor = this.getBusColor(bus);
    const isEmergency = bus.emergency_status || bus.status === 'emergency';
    const heading = parseFloat(bus.heading) || 0;

    let markerClass = 'bus-marker-icon';
    if (isEmergency) {
      markerClass += ' status-emergency';
    } else if (isReal) {
      markerClass += ' marker-physical';
    }

    const occupancy = bus.occupancy_rate || 0;
    const occColor = occupancy > 90 ? '#ef4444' : (occupancy > 75 ? '#f59e0b' : '#10b981');
    const routeLabel = bus.route_number ? `Line ${bus.route_number}` : 'Standby';

    // Vector Bus SVG Icon ensures crystal-clear rendering in all environments
    const busSvg = `<svg viewBox="0 0 24 24" width="22" height="22" fill="#ffffff"><path d="M4 16c0 .88.39 1.67 1 2.22V20c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h8v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1.78c.61-.55 1-1.34 1-2.22V6c0-3.5-3.58-4-8-4s-8 .5-8 4v10zm3.5 1c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zm9 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm1.5-6H6V6h12v5z"/></svg>`;

    const html = `
      <div class="custom-bus-marker" id="marker-bus-${bus.id}">
        <div class="${markerClass}" style="background: linear-gradient(135deg, ${busColor}, ${this._shadeColor(busColor, -25)});">
          <div class="bus-heading-arrow" style="transform: translateX(-50%) rotate(${heading}deg);"></div>
          ${busSvg}
        </div>
        <div class="bus-marker-label" style="border-left: 3px solid ${occColor};">
          <span class="marker-badge-route" style="background:${busColor};">${routeLabel}</span>
          <span><b>${bus.bus_number}</b></span>
          <span class="marker-source-tag ${isReal ? 'tag-real' : 'tag-sim'}">${isReal ? 'REAL IoT' : 'AUTO SIM'}</span>
        </div>
      </div>
    `;

    const icon = L.divIcon({
      className: 'bus-marker-container',
      html: html,
      iconSize: [60, 60],
      iconAnchor: [30, 23]
    });

    if (this.busMarkers[bus.id]) {
      this.busMarkers[bus.id].setLatLng([lat, lng]);
      this.busMarkers[bus.id].setIcon(icon);
      this.busMarkers[bus.id].setZIndexOffset(isReal ? 2500 : 1000);
    } else {
      const marker = L.marker([lat, lng], { 
        icon: icon, 
        zIndexOffset: isReal ? 2500 : 1000 
      }).addTo(this.map);
      marker.on('click', () => {
        this.selectBus(bus.id);
      });
      this.busMarkers[bus.id] = marker;
    }

    // Diagnostics Popup
    this.busMarkers[bus.id].bindPopup(`
      <div style="font-family:sans-serif;padding:8px;min-width:240px;color:#cbd5e1;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <h4 style="margin:0;font-size:16px;color:#ffffff;display:flex;align-items:center;gap:8px;font-weight:700;">
            <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${busColor};box-shadow:0 0 8px ${busColor};"></span>
            🚌 ${bus.bus_number}
          </h4>
          <span style="font-size:10px;font-weight:800;padding:2px 7px;border-radius:4px;background:${isReal ? 'rgba(16,185,129,0.25)' : 'rgba(56,189,248,0.25)'};color:${isReal ? '#34d399' : '#38bdf8'};border:1px solid ${isReal ? 'rgba(16,185,129,0.5)' : 'rgba(56,189,248,0.5)'};">
            ${isReal ? 'REAL PHYSICAL (ESP32)' : 'AUTONOMOUS SIM'}
          </span>
        </div>
        <div style="font-size:12px;font-weight:700;color:${busColor};margin-bottom:6px;">
          Line ${bus.route_number || '101'}: ${bus.route_name || 'Active Transit Line'}
        </div>
        <hr style="border:0;border-top:1px solid rgba(255,255,255,0.12);margin:8px 0;">
        <div style="font-size:12px;line-height:1.7;color:#e2e8f0;">
          <b style="color:#ffffff;">🎟️ Ticket Fare:</b> ₹${bus.fare ? Number(bus.fare).toFixed(2) : (bus.ticket_price ? Number(bus.ticket_price).toFixed(2) : '30.00')}<br>
          <b style="color:#ffffff;">⚡ Speed:</b> ${(bus.speed || 0).toFixed(1)} km/h • <b style="color:#ffffff;">Heading:</b> ${heading.toFixed(0)}°<br>
          <b style="color:#ffffff;">🪑 Passengers:</b> ${bus.current_passengers || 0} / ${bus.capacity || 40} (${occupancy.toFixed(0)}%) • <strong style="color:#10b981;">${bus.available_seats !== undefined ? bus.available_seats : (40 - (bus.current_passengers || 0))} Free</strong><br>
          <b style="color:#ffffff;">📍 Coordinates:</b> ${lat.toFixed(4)}, ${lng.toFixed(4)}<br>
          <b style="color:#ffffff;">👨‍✈️ Driver:</b> ${bus.driver_name || 'Assigned Driver'}<br>
          <b style="color:#ffffff;">🔋 Battery:</b> ${bus.battery_voltage ? bus.battery_voltage.toFixed(2) + 'V' : '12.6V'} | <b style="color:#ffffff;">Temp:</b> ${bus.engine_temp ? bus.engine_temp.toFixed(1) + '°C' : '82.0°C'}
        </div>
        <div style="margin-top:12px;display:flex;gap:8px;">
          <a href="../passenger/seat-status.html?bus_id=${bus.id}" class="action-btn" style="padding:6px 10px;font-size:11px;flex:1;text-align:center;text-decoration:none;border-radius:6px;background:rgba(255,255,255,0.08);color:#f8fafc;border:1px solid rgba(255,255,255,0.18);display:inline-block;font-weight:600;">
            🪑 2D Seats
          </a>
          <a href="../passenger/tracking.html?bus_id=${bus.id}" class="action-btn" style="padding:6px 10px;font-size:11px;flex:1;text-align:center;text-decoration:none;border-radius:6px;background:${busColor};color:#ffffff;display:inline-block;font-weight:700;box-shadow:0 2px 8px rgba(0,0,0,0.4);">
            📍 Live Track
          </a>
        </div>
      </div>
    `);

    if (this.selectedBusId === bus.id) {
      this.map.panTo([lat, lng]);
    }
  }

  selectBus(busId) {
    const id = parseInt(busId);
    this.selectedBusId = id;
    if (this.busMarkers[id]) {
      const latLng = this.busMarkers[id].getLatLng();
      this.map.setView(latLng, 15, { animate: true });
      this.busMarkers[id].openPopup();
    }
  }

  recenter() {
    if (this.map) {
      this.map.setView([12.9850, 77.6100], 13);
    }
  }

  fitAllBuses() {
    const latLngs = Object.values(this.busMarkers).map(m => m.getLatLng());
    if (latLngs.length > 0 && this.map) {
      const bounds = L.latLngBounds(latLngs);
      this.map.fitBounds(bounds, { padding: [50, 50] });
    }
  }

  renderRouteLegend(routes) {
    const legendContainer = document.getElementById('map-route-legend-container');
    if (!legendContainer) return;

    const stopStrs = {
      '101': '🏥 Hospital Stop ➔ 🏫 School Zone ➔ 🛒 Market Area ➔ 🚌 Bus Terminal',
      '202': '✈️ Airport Terminal ➔ 🏢 Aerospace Tech Park ➔ 🛣️ Highway Interchange ➔ 🏙️ Downtown District',
      '303': '🎓 University Campus ➔ 🏥 Medical College ➔ 🎭 Civic Arts Center ➔ 🛍️ South Commercial Mall'
    };

    let html = `
      <div class="map-route-legend">
        <div style="font-size:11px;font-weight:700;color:#cbd5e1;text-transform:uppercase;margin-bottom:4px;">Project Transit Corridors:</div>
    `;

    routes.forEach(r => {
      const color = r.color || (r.route_number === '101' ? '#10b981' : (r.route_number === '202' ? '#3b82f6' : '#ef4444'));
      const note = r.route_number === '101' ? 'SB-101 (Real Physical IoT)' : (r.route_number === '202' ? 'SB-102 (Airport Auto Sim)' : 'SB-103 (City Auto Sim)');
      const stopsProgression = stopStrs[r.route_number] || `${r.origin} ➔ ${r.destination}`;

      html += `
        <div class="route-legend-item" onclick="if(window.fullMap) window.fullMap.focusRoute(${r.id}); if(window.pMap) window.pMap.focusRoute(${r.id});">
          <div style="display:flex;align-items:center;justify-content:space-between;">
            <div style="display:flex;align-items:center;">
              <span class="route-color-pill" style="background:${color};"></span>
              <span style="color:#fff;font-weight:700;font-size:12px;">Line ${r.route_number}: ${r.name}</span>
            </div>
            <span style="color:#10b981;font-size:11px;font-weight:700;">₹${Number(r.fare).toFixed(2)}</span>
          </div>
          <div class="route-stop-progression-text">
            ${stopsProgression}
          </div>
        </div>
      `;
    });

    html += `</div>`;
    legendContainer.innerHTML = html;
  }

  focusRoute(routeId) {
    if (this.routeLayers[routeId] && this.map) {
      const bounds = this.routeLayers[routeId].getBounds();
      this.map.fitBounds(bounds, { padding: [40, 40] });
    }
  }

  bindSocketEvents() {
    document.addEventListener('busTelemetryUpdate', (e) => {
      if (e.detail && e.detail.bus) {
        this.updateBusMarker(e.detail.bus);
      }
    });

    document.addEventListener('busReallocated', (e) => {
      if (e.detail) {
        if (e.detail.degraded_bus) this.updateBusMarker(e.detail.degraded_bus);
        if (e.detail.replacement_bus) this.updateBusMarker(e.detail.replacement_bus);
      }
    });
  }

  _shadeColor(color, percent) {
    if (!color || typeof color !== 'string' || !color.startsWith('#') || color.length < 7) {
      return color || '#0f172a';
    }
    try {
      let R = parseInt(color.substring(1,3), 16) || 0;
      let G = parseInt(color.substring(3,5), 16) || 0;
      let B = parseInt(color.substring(5,7), 16) || 0;

      R = Math.min(255, Math.max(0, Math.round(R * (100 + percent) / 100)));
      G = Math.min(255, Math.max(0, Math.round(G * (100 + percent) / 100)));
      B = Math.min(255, Math.max(0, Math.round(B * (100 + percent) / 100)));

      const RR = (R < 16 ? "0" : "") + R.toString(16);
      const GG = (G < 16 ? "0" : "") + G.toString(16);
      const BB = (B < 16 ? "0" : "") + B.toString(16);

      return "#" + RR + GG + BB;
    } catch (e) {
      return color;
    }
  }
}
