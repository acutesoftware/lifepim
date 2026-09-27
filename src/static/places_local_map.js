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

  function initialView(markers) {
    const lons = markers.map((marker) => Number(marker.lon));
    const lats = markers.map((marker) => Number(marker.lat));
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const centerLon = (minLon + maxLon) / 2;
    const centerLat = (minLat + maxLat) / 2;
    const latitudeScale = Math.max(Math.cos(centerLat * Math.PI / 180), 0.25);
    let latSpan = Math.max((maxLat - minLat) * 1.35, 2);
    let lonSpan = Math.max((maxLon - minLon) * 1.35, latSpan * 2 / latitudeScale);
    latSpan = Math.max(latSpan, lonSpan * latitudeScale / 2);
    return {
      centerLon,
      centerLat,
      lonSpan: Math.min(lonSpan, 360),
      latSpan: Math.min(latSpan, 170),
    };
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
  }

  window.initPlacesLocalMap = function (options) {
    const container = document.getElementById(options.elementId);
    if (!container || !options.markers.length) return;
    const status = container.querySelector(".places-local-map-status");
    const view = initialView(options.markers);
    let zoom = 1;
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
      const redraw = () => render(container, options.markers, base, towns, view, zoom);
      container.querySelector('[data-map-action="zoom-in"]').addEventListener("click", () => {
        zoom = Math.min(zoom * 1.7, 16);
        redraw();
      });
      container.querySelector('[data-map-action="zoom-out"]').addEventListener("click", () => {
        zoom = Math.max(zoom / 1.7, 0.25);
        redraw();
      });
      container.querySelector('[data-map-action="reset"]').addEventListener("click", () => {
        zoom = 1;
        redraw();
      });
      redraw();
    }).catch((error) => {
      status.textContent = `The bundled local map data could not be loaded: ${error.message}`;
      status.classList.add("places-local-map-error");
    });
  };
}());
