(function () {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const WIDTH = 1200;
  const HEIGHT = 600;

  function svgElement(name, attributes) {
    const element = document.createElementNS(SVG_NS, name);
    Object.entries(attributes || {}).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
  }

  function viewForCoordinates(lons, lats, minimumLatitudeSpan) {
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const centerLon = (minLon + maxLon) / 2;
    const centerLat = (minLat + maxLat) / 2;
    const latitudeScale = Math.max(Math.cos(centerLat * Math.PI / 180), 0.25);
    let latSpan = Math.max((maxLat - minLat) * 1.25, minimumLatitudeSpan);
    let lonSpan = Math.max((maxLon - minLon) * 1.25, latSpan * 2 / latitudeScale);
    latSpan = Math.max(latSpan, lonSpan * latitudeScale / 2);
    return {
      centerLon,
      centerLat,
      lonSpan: Math.min(lonSpan, 360),
      latSpan: Math.min(latSpan, 170),
    };
  }

  function initialView(markers) {
    return viewForCoordinates(
      markers.map((marker) => Number(marker.lon)),
      markers.map((marker) => Number(marker.lat)),
      2
    );
  }

  function countryView(country) {
    return viewForCoordinates([country[1], country[3]], [country[2], country[4]], 1);
  }

  function placeView(marker) {
    return viewForCoordinates([Number(marker.lon)], [Number(marker.lat)], 0.8);
  }

  function currentBounds(view, zoom) {
    const lonSpan = Math.min(view.lonSpan / zoom, 360);
    const latSpan = Math.min(view.latSpan / zoom, 170);
    return {
      minLon: view.centerLon - lonSpan / 2,
      maxLon: view.centerLon + lonSpan / 2,
      minLat: Math.max(view.centerLat - latSpan / 2, -85),
      maxLat: Math.min(view.centerLat + latSpan / 2, 85),
      lonSpan,
      latSpan,
    };
  }

  function clampViewCenter(view, zoom) {
    const halfLon = Math.min(view.lonSpan / zoom, 360) / 2;
    const halfLat = Math.min(view.latSpan / zoom, 170) / 2;
    view.centerLon = Math.min(Math.max(view.centerLon, -180 + halfLon), 180 - halfLon);
    view.centerLat = Math.min(Math.max(view.centerLat, -85 + halfLat), 85 - halfLat);
  }

  function zoomAtPoint(container, view, currentZoom, nextZoom, clientX, clientY) {
    const rect = container.getBoundingClientRect();
    const xRatio = Math.min(Math.max((clientX - rect.left) / rect.width, 0), 1);
    const yRatio = Math.min(Math.max((clientY - rect.top) / rect.height, 0), 1);
    const oldBounds = currentBounds(view, currentZoom);
    const longitude = oldBounds.minLon + xRatio * oldBounds.lonSpan;
    const latitude = oldBounds.maxLat - yRatio * oldBounds.latSpan;
    const newLonSpan = Math.min(view.lonSpan / nextZoom, 360);
    const newLatSpan = Math.min(view.latSpan / nextZoom, 170);
    view.centerLon = longitude - (xRatio - 0.5) * newLonSpan;
    view.centerLat = latitude + (yRatio - 0.5) * newLatSpan;
    clampViewCenter(view, nextZoom);
    return nextZoom;
  }

  function projector(bounds) {
    return function (lon, lat) {
      return [
        (lon - bounds.minLon) / bounds.lonSpan * WIDTH,
        (bounds.maxLat - lat) / bounds.latSpan * HEIGHT,
      ];
    };
  }

  function linePath(coordinates, project, closePath) {
    let path = "";
    let previousLon = null;
    coordinates.forEach((coordinate) => {
      const lon = Number(coordinate[0]);
      const lat = Number(coordinate[1]);
      const point = project(lon, lat);
      const startsSegment = previousLon === null || Math.abs(lon - previousLon) > 180;
      path += `${startsSegment ? "M" : "L"}${point[0].toFixed(2)},${point[1].toFixed(2)}`;
      previousLon = lon;
    });
    return path + (closePath ? "Z" : "");
  }

  function geometryPath(geometry, project) {
    if (!geometry || !geometry.coordinates) return "";
    if (geometry.type === "Polygon") {
      return geometry.coordinates.map((ring) => linePath(ring, project, true)).join("");
    }
    if (geometry.type === "MultiPolygon") {
      return geometry.coordinates.flatMap((polygon) => (
        polygon.map((ring) => linePath(ring, project, true))
      )).join("");
    }
    if (geometry.type === "LineString") {
      return linePath(geometry.coordinates, project, false);
    }
    if (geometry.type === "MultiLineString") {
      return geometry.coordinates.map((line) => linePath(line, project, false)).join("");
    }
    return "";
  }

  function combinedPath(geometries, project) {
    return geometries.map((geometry) => geometryPath(geometry, project)).join("");
  }

  function gridStep(span) {
    if (span <= 3) return 0.5;
    if (span <= 8) return 1;
    if (span <= 20) return 2;
    if (span <= 50) return 5;
    if (span <= 100) return 10;
    return 30;
  }

  function drawGrid(svg, bounds, project) {
    const path = [];
    const lonStep = gridStep(bounds.lonSpan);
    const latStep = gridStep(bounds.latSpan);
    for (let lon = Math.ceil(bounds.minLon / lonStep) * lonStep; lon <= bounds.maxLon; lon += lonStep) {
      const top = project(lon, bounds.maxLat);
      const bottom = project(lon, bounds.minLat);
      path.push(`M${top[0].toFixed(2)},${top[1].toFixed(2)}L${bottom[0].toFixed(2)},${bottom[1].toFixed(2)}`);
    }
    for (let lat = Math.ceil(bounds.minLat / latStep) * latStep; lat <= bounds.maxLat; lat += latStep) {
      const left = project(bounds.minLon, lat);
      const right = project(bounds.maxLon, lat);
      path.push(`M${left[0].toFixed(2)},${left[1].toFixed(2)}L${right[0].toFixed(2)},${right[1].toFixed(2)}`);
    }
    svg.appendChild(svgElement("path", {d: path.join(""), class: "places-local-grid"}));
  }

  function townRankLimit(bounds) {
    const span = Math.max(bounds.lonSpan, bounds.latSpan);
    if (span <= 7) return 10;
    if (span <= 15) return 9;
    if (span <= 30) return 8;
    if (span <= 70) return 6;
    return 4;
  }

  function drawTowns(svg, towns, bounds, project) {
    const rankLimit = townRankLimit(bounds);
    const visible = towns.filter((town) => (
      town[0] >= bounds.minLon && town[0] <= bounds.maxLon &&
      town[1] >= bounds.minLat && town[1] <= bounds.maxLat && town[3] <= rankLimit
    )).sort((left, right) => left[3] - right[3] || right[4] - left[4]).slice(0, 240);
    const labelBoxes = [];
    visible.forEach((town, index) => {
      const point = project(town[0], town[1]);
      svg.appendChild(svgElement("circle", {
        cx: point[0].toFixed(2), cy: point[1].toFixed(2), r: town[3] <= 4 ? 3 : 2,
        class: "places-local-town-dot",
      }));
      if (index >= 80) return;
      const width = Math.max(32, town[2].length * 6.5);
      const box = {x: point[0] + 5, y: point[1] - 12, width, height: 15};
      const overlaps = labelBoxes.some((other) => !(
        box.x + box.width < other.x || other.x + other.width < box.x ||
        box.y + box.height < other.y || other.y + other.height < box.y
      ));
      if (overlaps) return;
      labelBoxes.push(box);
      const label = svgElement("text", {
        x: box.x.toFixed(2), y: point[1].toFixed(2), class: "places-local-town-label",
      });
      label.textContent = town[2];
      svg.appendChild(label);
    });
  }

  function addPopup(container, marker, x, y) {
    container.querySelectorAll(".places-local-popup").forEach((popup) => popup.remove());
    const popup = document.createElement("div");
    popup.className = "places-local-popup places-map-popup";
    popup.style.left = `${Math.min(Math.max(x / WIDTH * 100, 4), 78)}%`;
    popup.style.top = `${Math.min(Math.max(y / HEIGHT * 100, 4), 72)}%`;
    const title = document.createElement("div");
    title.className = "places-map-popup-title";
    title.textContent = marker.name || "Place";
    popup.appendChild(title);
    (marker.details || []).forEach((detail) => {
      const row = document.createElement("div");
      row.className = "places-map-tooltip-row";
      row.textContent = detail;
      popup.appendChild(row);
    });
    const actions = document.createElement("div");
    actions.className = "places-map-popup-actions";
    const viewLink = document.createElement("a");
    viewLink.href = marker.url;
    viewLink.textContent = "View place";
    actions.appendChild(viewLink);
    (marker.actions || []).forEach((action) => {
      const link = document.createElement("a");
      link.href = action.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = action.label;
      actions.appendChild(link);
    });
    popup.appendChild(actions);
    const close = document.createElement("button");
    close.type = "button";
    close.className = "places-local-popup-close";
    close.setAttribute("aria-label", "Close place details");
    close.textContent = "×";
    close.addEventListener("click", () => popup.remove());
    popup.appendChild(close);
    container.appendChild(popup);
  }

  function drawMarkers(container, markers, bounds, project) {
    container.querySelectorAll(".places-local-marker").forEach((marker) => marker.remove());
    markers.forEach((marker) => {
      const point = project(marker.lon, marker.lat);
      if (point[0] < 0 || point[0] > WIDTH || point[1] < 0 || point[1] > HEIGHT) return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "places-local-marker";
      button.style.left = `${point[0] / WIDTH * 100}%`;
      button.style.top = `${point[1] / HEIGHT * 100}%`;
      button.title = marker.name || "View place";
      button.setAttribute("aria-label", marker.name || "View place");
      button.innerHTML = '<span aria-hidden="true"></span>';
      button.addEventListener("click", () => addPopup(container, marker, point[0], point[1]));
      container.appendChild(button);
    });
  }

  function featurePath(features, project) {
    return (features || []).map((feature) => geometryPath(feature.g, project)).join("");
  }

  function featurePoint(geometry) {
    if (!geometry || !geometry.coordinates) return null;
    if (geometry.type === "Point") return geometry.coordinates;
    let coordinates = geometry.coordinates;
    while (coordinates && coordinates.length && Array.isArray(coordinates[0]) && Array.isArray(coordinates[0][0])) {
      coordinates = coordinates[0];
    }
    if (!coordinates || !coordinates.length) return null;
    const midpoint = coordinates[Math.floor(coordinates.length / 2)];
    return midpoint && midpoint.length >= 2 ? midpoint : null;
  }

  function drawStreetDetails(svg, details, project) {
    svg.querySelectorAll(".places-street-detail").forEach((element) => element.remove());
    if (!details || !details.enabled || !details.detail) return;
    const group = svgElement("g", {class: `places-street-detail detail-${details.detail}`});
    ["landuse", "water", "buildings", "waterways", "railways"].forEach((layer) => {
      if (details[layer] && details[layer].length) {
        group.appendChild(svgElement("path", {
          d: featurePath(details[layer], project),
          class: `places-street-${layer}`,
        }));
      }
    });
    const roadClasses = {};
    (details.roads || []).forEach((feature) => {
      const roadClass = ["motorway", "trunk", "primary", "secondary"].find((name) => (
        String(feature.c || "").startsWith(name)
      )) || "minor";
      (roadClasses[roadClass] ||= []).push(feature);
    });
    ["minor", "secondary", "primary", "trunk", "motorway"].forEach((roadClass) => {
      if (!roadClasses[roadClass]) return;
      group.appendChild(svgElement("path", {
        d: featurePath(roadClasses[roadClass], project),
        class: `places-street-road places-street-road-${roadClass}`,
      }));
    });
    const insertionPoint = svg.querySelector(".places-local-town-dot, .places-local-town-label");
    svg.insertBefore(group, insertionPoint || null);

    const labels = svgElement("g", {class: "places-street-detail places-street-labels"});
    const usedNames = new Set();
    const labelBoxes = [];
    [...(details.places || []), ...(details.roads || [])].forEach((feature) => {
      const name = String(feature.n || "").trim();
      if (!name || usedNames.has(name) || usedNames.size >= 60) return;
      const coordinate = featurePoint(feature.g);
      if (!coordinate) return;
      const point = project(coordinate[0], coordinate[1]);
      if (point[0] < 0 || point[0] > WIDTH || point[1] < 0 || point[1] > HEIGHT) return;
      const width = Math.min(name.length * 6.5, 150);
      const box = {left: point[0] - 3, right: point[0] + width + 3, top: point[1] - 12, bottom: point[1] + 4};
      if (labelBoxes.some((used) => (
        box.left < used.right && box.right > used.left && box.top < used.bottom && box.bottom > used.top
      ))) return;
      usedNames.add(name);
      labelBoxes.push(box);
      const label = svgElement("text", {
        x: point[0].toFixed(2),
        y: point[1].toFixed(2),
        class: feature.g.type === "Point" ? "places-street-place-label" : "places-street-road-label",
      });
      label.textContent = name;
      labels.appendChild(label);
    });
    svg.appendChild(labels);
  }

  function streetDetailLevel(bounds) {
    const span = Math.max(bounds.lonSpan, bounds.latSpan);
    if (span > 4) return 0;
    if (span > 0.8) return 1;
    if (span > 0.18) return 2;
    return 3;
  }

  function expandedStreetBounds(bounds) {
    const span = Math.max(bounds.lonSpan, bounds.latSpan);
    const factor = span > 2.5 ? 1 : 1.4;
    const extraLon = bounds.lonSpan * (factor - 1) / 2;
    const extraLat = bounds.latSpan * (factor - 1) / 2;
    return {
      minLon: Math.max(-180, bounds.minLon - extraLon),
      maxLon: Math.min(180, bounds.maxLon + extraLon),
      minLat: Math.max(-85, bounds.minLat - extraLat),
      maxLat: Math.min(85, bounds.maxLat + extraLat),
    };
  }

  function cachedStreetDetails(cache, bounds, detail) {
    return cache && cache.detail === detail &&
      cache.bounds.minLon <= bounds.minLon && cache.bounds.maxLon >= bounds.maxLon &&
      cache.bounds.minLat <= bounds.minLat && cache.bounds.maxLat >= bounds.maxLat;
  }

  function loadStreetDetails(options, frame, queryBounds, detail, requestNumber, latestRequest, signal, onLoaded) {
    const params = new URLSearchParams({
      min_lon: queryBounds.minLon,
      min_lat: queryBounds.minLat,
      max_lon: queryBounds.maxLon,
      max_lat: queryBounds.maxLat,
      detail,
    });
    fetch(`${options.streetDetailsUrl}?${params}`, {signal}).then((response) => {
      if (!response.ok) throw new Error(`Local street detail returned ${response.status}`);
      return response.json();
    }).then((details) => {
      if (requestNumber !== latestRequest() || !frame.svg.isConnected) return;
      onLoaded({bounds: queryBounds, detail, details});
      drawStreetDetails(frame.svg, details, frame.project);
    }).catch((error) => {
      if (error.name === "AbortError") return;
      // The bundled overview remains usable if an optional pack is unavailable.
    });
  }

  function setupMapMenu(options) {
    const menu = document.querySelector("[data-places-map-menu]");
    if (!menu) return;
    const statusBox = document.querySelector("[data-map-download-status]");
    const statusMessage = document.querySelector("[data-map-download-message]");
    const progress = document.querySelector("[data-map-download-progress]");
    const summary = document.querySelector("[data-map-pack-summary]");
    let timer = null;
    const showStatus = (state) => {
      if (!statusBox) return;
      statusBox.hidden = false;
      statusMessage.textContent = state.error || state.message || "Preparing offline map data…";
      const percent = state.total ? Math.round(state.downloaded / state.total * 100) : 0;
      progress.value = percent;
      progress.hidden = !state.running || !state.total;
      if (summary) {
        const count = (state.installed || []).length;
        summary.textContent = `Street detail: ${options.streetDetailsEnabled ? "on" : "off"}; ${count} local pack${count === 1 ? "" : "s"}.`;
      }
      if (!state.running && timer) {
        clearInterval(timer);
        timer = null;
      }
    };
    const poll = () => fetch(options.localMapStatusUrl).then((response) => response.json()).then(showStatus);
    const beginPolling = () => {
      poll();
      if (!timer) timer = setInterval(poll, 1000);
    };
    menu.addEventListener("change", () => {
      const action = menu.value;
      menu.selectedIndex = 0;
      if (!action) return;
      if (action === "toggle-detail") {
        fetch(options.localMapSettingsUrl, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({enabled: !options.streetDetailsEnabled}),
        }).then((response) => response.json()).then(() => window.location.reload());
        return;
      }
      const isAustralia = action === "download-au";
      const warning = isAustralia
        ? "Download approximately 1.9 GB and use roughly 4–5 GB after extraction for Australia's seven state/territory map packs?"
        : "Download approximately 144 MB and use roughly 302 MB after extraction for South Australia?";
      if (!window.confirm(warning)) return;
      const url = isAustralia ? options.localMapDownloadAuUrl : options.localMapDownloadSaUrl;
      fetch(url, {method: "POST"}).then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || "Could not start the map download.");
        showStatus(result.status);
        beginPolling();
      }).catch((error) => {
        showStatus({message: "", error: error.message, running: false, installed: []});
      });
    });
    if (statusBox && !statusBox.hidden) beginPolling();
  }

  function render(container, markers, base, towns, view, zoom) {
    container.querySelectorAll("svg, .places-local-marker, .places-local-popup").forEach((item) => item.remove());
    const bounds = currentBounds(view, zoom);
    const project = projector(bounds);
    const svg = svgElement("svg", {
      viewBox: `0 0 ${WIDTH} ${HEIGHT}`, role: "img",
      "aria-label": "Static local overview map showing saved places and nearby towns",
      preserveAspectRatio: "none",
    });
    svg.appendChild(svgElement("rect", {x: 0, y: 0, width: WIDTH, height: HEIGHT, class: "places-local-ocean"}));
    drawGrid(svg, bounds, project);
    svg.appendChild(svgElement("path", {d: combinedPath(base.land, project), class: "places-local-land"}));
    svg.appendChild(svgElement("path", {d: combinedPath(base.boundaries, project), class: "places-local-boundary"}));
    svg.appendChild(svgElement("path", {d: combinedPath(base.lakes, project), class: "places-local-lake"}));
    drawTowns(svg, towns, bounds, project);
    container.insertBefore(svg, container.firstChild);
    drawMarkers(container, markers, bounds, project);
    return {svg, bounds, project};
  }

  window.initPlacesLocalMap = function (options) {
    setupMapMenu(options);
    const container = document.getElementById(options.elementId);
    if (!container || !options.markers.length) return;
    const status = container.querySelector(".places-local-map-status");
    const savedPlacesView = initialView(options.markers);
    const view = {...savedPlacesView};
    let zoom = 1;
    let streetRequest = 0;
    let streetTimer = null;
    let streetController = null;
    let streetCache = null;
    let redrawFrame = null;
    Promise.all([
      fetch(options.baseDataUrl).then((response) => {
        if (!response.ok) throw new Error(`Local base map returned ${response.status}`);
        return response.json();
      }),
      fetch(options.townsDataUrl).then((response) => {
        if (!response.ok) throw new Error(`Local town data returned ${response.status}`);
        return response.json();
      }),
    ]).then(([base, towns]) => {
      status.remove();
      const redrawNow = () => {
        redrawFrame = null;
        const frame = render(container, options.markers, base, towns, view, zoom);
        const requestNumber = ++streetRequest;
        if (streetTimer) clearTimeout(streetTimer);
        const detail = streetDetailLevel(frame.bounds);
        if (!options.streetDetailsEnabled || !options.streetDetailsUrl || !detail) {
          if (streetController) streetController.abort();
          return;
        }
        if (cachedStreetDetails(streetCache, frame.bounds, detail)) {
          if (streetController) streetController.abort();
          drawStreetDetails(frame.svg, streetCache.details, frame.project);
          return;
        }
        streetTimer = setTimeout(() => {
          if (streetController) streetController.abort();
          streetController = new AbortController();
          loadStreetDetails(
            options,
            frame,
            expandedStreetBounds(frame.bounds),
            detail,
            requestNumber,
            () => streetRequest,
            streetController.signal,
            (cache) => { streetCache = cache; }
          );
        }, 180);
      };
      const redraw = () => {
        if (redrawFrame !== null) return;
        redrawFrame = window.requestAnimationFrame(redrawNow);
      };
      const showView = (nextView) => {
        Object.assign(view, nextView);
        zoom = 1;
        redraw();
      };
      const countrySelect = container.querySelector('[data-map-action="country"]');
      (base.countries || []).forEach((country, index) => {
        const option = document.createElement("option");
        option.value = String(index);
        option.textContent = country[0];
        countrySelect.appendChild(option);
      });
      countrySelect.addEventListener("change", () => {
        if (countrySelect.value === "") return;
        placeSelect.value = "";
        showView(countryView(base.countries[Number(countrySelect.value)]));
      });
      const placeSelect = container.querySelector('[data-map-action="place"]');
      [...options.markers].sort((left, right) => (
        (left.name || "").localeCompare(right.name || "")
      )).forEach((marker) => {
        const option = document.createElement("option");
        option.value = String(options.markers.indexOf(marker));
        option.textContent = marker.country ? `${marker.name || "Place"} — ${marker.country}` : (marker.name || "Place");
        placeSelect.appendChild(option);
      });
      placeSelect.addEventListener("change", () => {
        if (placeSelect.value === "") return;
        countrySelect.value = "";
        showView(placeView(options.markers[Number(placeSelect.value)]));
      });
      container.querySelector('[data-map-action="zoom-in"]').addEventListener("click", () => {
        zoom = Math.min(zoom * 1.7, 1024);
        redraw();
      });
      container.querySelector('[data-map-action="zoom-out"]').addEventListener("click", () => {
        zoom = Math.max(zoom / 1.7, 0.25);
        redraw();
      });
      container.querySelector('[data-map-action="fit-saved"]').addEventListener("click", () => {
        countrySelect.value = "";
        placeSelect.value = "";
        showView(savedPlacesView);
      });
      container.querySelector('[data-map-action="world"]').addEventListener("click", () => {
        countrySelect.value = "";
        placeSelect.value = "";
        showView({centerLon: 0, centerLat: 0, lonSpan: 360, latSpan: 170});
      });
      container.addEventListener("wheel", (event) => {
        if (event.target.closest(".places-local-map-controls, .places-local-map-jump, .places-local-popup")) return;
        event.preventDefault();
        const nextZoom = event.deltaY < 0 ? Math.min(zoom * 1.35, 1024) : Math.max(zoom / 1.35, 0.25);
        zoom = zoomAtPoint(container, view, zoom, nextZoom, event.clientX, event.clientY);
        redraw();
      }, {passive: false});
      container.addEventListener("dblclick", (event) => {
        if (event.target.closest("button, select, a, .places-local-popup")) return;
        event.preventDefault();
        const nextZoom = Math.min(zoom * 1.7, 1024);
        zoom = zoomAtPoint(container, view, zoom, nextZoom, event.clientX, event.clientY);
        redraw();
      });

      let drag = null;
      const endDrag = (event, applyMovement) => {
        if (!drag || event.pointerId !== drag.pointerId) return;
        const dx = event.clientX - drag.clientX;
        const dy = event.clientY - drag.clientY;
        const moved = Math.abs(dx) + Math.abs(dy) >= 3;
        if (applyMovement && moved) {
          view.centerLon = drag.centerLon - dx / drag.width * drag.bounds.lonSpan;
          view.centerLat = drag.centerLat + dy / drag.height * drag.bounds.latSpan;
          clampViewCenter(view, zoom);
        }
        container.classList.remove("is-dragging");
        container.style.removeProperty("--map-pan-x");
        container.style.removeProperty("--map-pan-y");
        if (container.hasPointerCapture(event.pointerId)) container.releasePointerCapture(event.pointerId);
        drag = null;
        if (applyMovement && moved) redraw();
      };
      container.addEventListener("pointerdown", (event) => {
        if (event.button !== 0 || event.target.closest("button, select, a, .places-local-popup")) return;
        const rect = container.getBoundingClientRect();
        drag = {
          pointerId: event.pointerId,
          clientX: event.clientX,
          clientY: event.clientY,
          centerLon: view.centerLon,
          centerLat: view.centerLat,
          width: rect.width,
          height: rect.height,
          bounds: currentBounds(view, zoom),
        };
        container.querySelectorAll(".places-local-popup").forEach((popup) => popup.remove());
        container.setPointerCapture(event.pointerId);
        container.classList.add("is-dragging");
        event.preventDefault();
      });
      container.addEventListener("pointermove", (event) => {
        if (!drag || event.pointerId !== drag.pointerId) return;
        event.preventDefault();
        container.style.setProperty("--map-pan-x", `${event.clientX - drag.clientX}px`);
        container.style.setProperty("--map-pan-y", `${event.clientY - drag.clientY}px`);
      });
      container.addEventListener("pointerup", (event) => endDrag(event, true));
      container.addEventListener("pointercancel", (event) => endDrag(event, false));
      redraw();
    }).catch((error) => {
      status.textContent = `The bundled local map data could not be loaded: ${error.message}`;
      status.classList.add("places-local-map-error");
    });
  };
}());
