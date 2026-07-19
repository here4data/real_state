(() => {
  const els = {
    locality: document.getElementById("locality"),
    operation: document.getElementById("operation"),
    propertyType: document.getElementById("propertyType"),
    maxPrice: document.getElementById("maxPrice"),
    minRooms: document.getElementById("minRooms"),
    minParking: document.getElementById("minParking"),
    sortBy: document.getElementById("sortBy"),
    results: document.getElementById("results"),
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

  function render() {
    const locality = els.locality.value;
    const operation = els.operation.value;
    const propertyType = els.propertyType.value;
    const maxPrice = parseFloat(els.maxPrice.value);
    const minRooms = parseInt(els.minRooms.value, 10) || 0;
    const minParking = parseInt(els.minParking.value, 10) || 0;

    let filtered = listings.filter((l) => {
      if (locality && l.locality !== locality) return false;
      if (operation && l.operation !== operation) return false;
      if (propertyType && l.property_type !== propertyType) return false;
      if (!Number.isNaN(maxPrice) && l.price_cop > maxPrice) return false;
      if ((l.rooms ?? 0) < minRooms) return false;
      if ((l.parking_spots ?? 0) < minParking) return false;
      return true;
    });

    const sortBy = els.sortBy.value;
    filtered.sort((a, b) => {
      if (sortBy === "price_desc") return b.price_cop - a.price_cop;
      if (sortBy === "area_desc") return (b.area_m2 ?? 0) - (a.area_m2 ?? 0);
      return a.price_cop - b.price_cop;
    });

    els.results.innerHTML = "";
    for (const listing of filtered) {
      els.results.appendChild(buildCard(listing));
    }

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

    node.querySelector(".card-title").textContent = listing.title || "(sin título)";
    node.querySelector(".card-address").textContent =
      listing.address || capitalize(listing.locality);
    node.querySelector(".card-price").textContent = formatPrice(listing);

    node.querySelector(".attr-rooms").textContent = listing.rooms
      ? `${listing.rooms} hab.`
      : "";
    node.querySelector(".attr-bathrooms").textContent = listing.bathrooms
      ? `${listing.bathrooms} baños`
      : "";
    node.querySelector(".attr-parking").textContent = listing.parking_spots
      ? `${listing.parking_spots} parq.`
      : "";
    node.querySelector(".attr-area").textContent = listing.area_m2
      ? `${listing.area_m2} m²`
      : "";

    const link = node.querySelector(".card-link");
    link.href = listing.url;

    return node;
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
    els.minParking,
    els.sortBy,
  ]) {
    el.addEventListener("input", render);
  }

  init();
})();
