(() => {
  const els = {
    locality: document.getElementById("locality"),
    operation: document.getElementById("operation"),
    propertyType: document.getElementById("propertyType"),
    maxPrice: document.getElementById("maxPrice"),
    minRooms: document.getElementById("minRooms"),
    portal: document.getElementById("portal"),
    sortBy: document.getElementById("sortBy"),
    results: document.getElementById("results"),
    topOffers: document.getElementById("topOffers"),
    resultCount: document.getElementById("resultCount"),
    generatedAt: document.getElementById("generatedAt"),
    emptyState: document.getElementById("emptyState"),
    errorState: document.getElementById("errorState"),
    cardTemplate: document.getElementById("cardTemplate"),
  };

  const COP_FORMATTER = new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  });

  let listings = [];
  let map = null;
  let markerLayer = null;

  function initMap() {
    if (typeof L === "undefined") return; // Leaflet CDN unavailable: degrade to list
    map = L.map("map").setView([4.70, -74.06], 12); // Usaquén–Chapinero–Suba
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    markerLayer = L.layerGroup().addTo(map);
  }

  function renderMap(filtered) {
    if (!map) return;
    markerLayer.clearLayers();
    const bounds = [];
    for (const l of filtered) {
      if (l.latitude == null || l.longitude == null) continue;
      const marker = L.marker([l.latitude, l.longitude]).bindPopup(
        `<strong>${escapeHtml(l.title || "")}</strong><br>` +
          `${formatPrice(l)}<br>` +
          `${l.rooms ?? "?"} hab · ${l.area_m2 ?? "?"} m² · ${escapeHtml(l.portal)}<br>` +
          (l.opportunity_rank ? `Ranking oportunidad: #${l.opportunity_rank}<br>` : "") +
          `<a href="${l.url}" target="_blank" rel="noopener">Ver anuncio →</a>`
      );
      markerLayer.addLayer(marker);
      bounds.push([l.latitude, l.longitude]);
    }
    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function render() {
    const locality = els.locality.value;
    const operation = els.operation.value;
    const propertyType = els.propertyType.value;
    const maxPrice = parseFloat(els.maxPrice.value);
    const minRooms = parseInt(els.minRooms.value, 10) || 0;
    const portal = els.portal.value;

    let filtered = listings.filter((l) => {
      if (portal && l.portal !== portal) return false;
      if (locality && l.locality !== locality) return false;
      if (operation && l.operation !== operation) return false;
      if (propertyType && l.property_type !== propertyType) return false;
      if (!Number.isNaN(maxPrice) && l.price_cop > maxPrice) return false;
      if ((l.rooms ?? 0) < minRooms) return false;
      return true;
    });

    const sortBy = els.sortBy.value;
    filtered.sort((a, b) => {
      if (sortBy === "opportunity")
        return (a.opportunity_rank ?? Infinity) - (b.opportunity_rank ?? Infinity);
      if (sortBy === "price_desc") return b.price_cop - a.price_cop;
      if (sortBy === "area_desc") return (b.area_m2 ?? 0) - (a.area_m2 ?? 0);
      return a.price_cop - b.price_cop;
    });

    els.results.innerHTML = "";
    for (const listing of filtered) {
      els.results.appendChild(buildCard(listing));
    }

    // Ofertas: top 6 del filtro actual, ordenadas por ranking de oportunidad
    els.topOffers.innerHTML = "";
    const top = filtered
      .filter((l) => l.opportunity_rank != null)
      .sort((a, b) => a.opportunity_rank - b.opportunity_rank)
      .slice(0, 6);
    for (const listing of top) {
      els.topOffers.appendChild(buildCard(listing));
    }

    renderMap(filtered);

    els.resultCount.textContent = `${filtered.length} inmueble${filtered.length === 1 ? "" : "s"}`;
    els.emptyState.hidden = filtered.length !== 0;
  }

  function buildCard(listing) {
    const node = els.cardTemplate.content.cloneNode(true);

    const img = node.querySelector(".card-image img");
    img.src = listing.photo_urls?.[0] || "";
    img.alt = listing.title || "";

    const badge = node.querySelector(".badge");
    badge.textContent = listing.operation;
    badge.classList.add(listing.operation);

    const article = node.querySelector(".card");
    if (listing.good_price) article.classList.add("good-price");

    node.querySelector(".card-title").textContent = listing.title || "(sin título)";
    node.querySelector(".card-address").textContent =
      listing.address || capitalize(listing.locality);
    node.querySelector(".card-price").textContent = formatPrice(listing);

    const score = node.querySelector(".card-score");
    if (listing.opportunity_rank != null) {
      score.textContent =
        `#${listing.opportunity_rank} oportunidad · ` +
        `${listing.opportunity_score > 0 ? "-" : "+"}${Math.abs(listing.opportunity_score)}% vs. mediana del segmento`;
      score.classList.add(listing.opportunity_score > 0 ? "good-deal" : "above-median");
    } else {
      score.textContent = "";
    }

    setAttr(node, ".attr-rooms", listing.rooms, (v) => `${v} hab.`, "Hab.: sin información");
    setAttr(node, ".attr-bathrooms", listing.bathrooms, (v) => `${v} baños`, "Baños: sin información");
    setAttr(node, ".attr-parking", listing.parking_spots, (v) => `${v} parq.`, "Parq.: sin información");
    setAttr(node, ".attr-area", listing.area_m2, (v) => `${v} m²`, "Área: sin información");
    setAttr(node, ".attr-ppm2", listing.price_per_m2, (v) => `${COP_FORMATTER.format(v)}/m²`, "Precio/m²: sin información");
    setAttr(node, ".attr-stratum", listing.stratum, (v) => `Estrato ${v}`, "Estrato: sin información");
    setAttr(
      node,
      ".attr-expenses",
      listing.common_expenses_cop,
      (v) => `Admin. ${COP_FORMATTER.format(v)}`,
      "Admin.: sin información"
    );

    const link = node.querySelector(".card-link");
    link.href = listing.url;
    link.textContent = `Ver en ${capitalize(listing.portal)} →`;

    return node;
  }

  function setAttr(node, selector, value, formatter, missingText) {
    const el = node.querySelector(selector);
    const present = value !== null && value !== undefined && value !== 0;
    el.textContent = present ? formatter(value) : missingText;
    el.classList.toggle("attr-missing", !present);
  }

  function formatPrice(listing) {
    const price = COP_FORMATTER.format(listing.price_cop);
    return listing.operation === "arriendo" ? `${price} / mes` : price;
  }

  function capitalize(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
  }

  async function init() {
    try {
      const res = await fetch("data/listings.json", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload = await res.json();
      listings = payload.listings || [];
      const portals = [...new Set(listings.map((l) => l.portal))].sort();
      for (const p of portals) {
        const opt = document.createElement("option");
        opt.value = p;
        opt.textContent = capitalize(p);
        els.portal.appendChild(opt);
      }
      if (payload.generated_at) {
        els.generatedAt.textContent = `Actualizado: ${payload.generated_at}`;
      }
      render();
    } catch (err) {
      els.errorState.hidden = false;
      els.resultCount.textContent = "";
      console.error(err);
    }
  }

  for (const el of [
    els.locality,
    els.operation,
    els.propertyType,
    els.maxPrice,
    els.minRooms,
    els.portal,
    els.sortBy,
  ]) {
    el.addEventListener("input", render);
  }

  initMap();
  init();
})();
