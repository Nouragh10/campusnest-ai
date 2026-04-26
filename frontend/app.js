const form = document.getElementById("preferences-form");
const output = document.getElementById("json-output");
const errorEl = document.getElementById("form-error");
const copyButton = document.getElementById("copy-json");
const resetButton = document.getElementById("reset-button");
const listingResults = document.getElementById("listing-results");

const STORAGE_KEY = "campusnest.userInput.v1";
const DATASET_PATH = "../data/zillow_dataset.json";
const DEFAULT_RESULTS_LIMIT = 10;
let listingsCache = null;

function getSelectedPreferences() {
  return Array.from(document.querySelectorAll('input[name="preferences"]:checked')).map(
    (checkbox) => checkbox.value
  );
}

function showError(message) {
  errorEl.textContent = message;
}

function clearError() {
  errorEl.textContent = "";
}

function buildPayload(formData) {
  return {
    studentProfile: {
      budget: Number(formData.get("maxRent")),
      bedrooms: formData.get("bedrooms"),
      commuteConstraintMinutes: Number(formData.get("maxCommuteMinutes")),
      destination: formData.get("primaryDestination").trim(),
      transportMode: formData.get("transportMode"),
      preferences: getSelectedPreferences(),
      notes: String(formData.get("notes") || "").trim(),
    },
    metadata: {
      createdAt: new Date().toISOString(),
      source: "frontend-user-input",
    },
  };
}

function validatePayload(payload) {
  if (!Number.isFinite(payload.studentProfile.budget) || payload.studentProfile.budget <= 0) {
    return "Enter a valid monthly budget greater than 0.";
  }
  if (!payload.studentProfile.bedrooms) {
    return "Select a bedroom preference.";
  }
  if (
    !Number.isFinite(payload.studentProfile.commuteConstraintMinutes) ||
    payload.studentProfile.commuteConstraintMinutes < 1
  ) {
    return "Enter a valid commute time of at least 1 minute.";
  }
  if (!payload.studentProfile.destination) {
    return "Provide a primary campus destination.";
  }
  return "";
}

function writeOutput(payload) {
  output.textContent = JSON.stringify(payload, null, 2);
}

function parseCurrency(value) {
  if (typeof value === "number") return value;
  if (typeof value !== "string") return NaN;
  const digits = value.replace(/[^0-9.]/g, "");
  return Number(digits);
}

function normalizeBedrooms(raw) {
  if (!raw && raw !== 0) return NaN;
  if (typeof raw === "number") return raw;
  if (typeof raw === "string") {
    const lower = raw.toLowerCase();
    if (lower.includes("studio")) return 0;
    if (lower.includes("+")) return Number(lower.replace(/[^0-9]/g, ""));
    return Number(lower.replace(/[^0-9.]/g, ""));
  }
  return NaN;
}

function requiredBedroomCount(selection) {
  if (selection === "studio") return 0;
  if (selection === "3+") return 3;
  return Number(selection);
}

function getListingPrice(listing) {
  if (Number.isFinite(listing.minBaseRent)) return listing.minBaseRent;
  if (Number.isFinite(listing.unformattedPrice)) return listing.unformattedPrice;
  if (Array.isArray(listing.units) && listing.units.length > 0) {
    const values = listing.units.map((unit) => parseCurrency(unit.price)).filter(Number.isFinite);
    if (values.length > 0) return Math.min(...values);
  }
  return NaN;
}

function hasBedroomMatch(listing, targetBedrooms) {
  if (Array.isArray(listing.units) && listing.units.length > 0) {
    const options = listing.units.map((unit) => normalizeBedrooms(unit.beds)).filter(Number.isFinite);
    if (targetBedrooms === 3) return options.some((count) => count >= 3);
    return options.some((count) => count === targetBedrooms);
  }
  return true;
}

function scoreListing(listing, payload, targetBedrooms) {
  const price = getListingPrice(listing);
  const budget = payload.studentProfile.budget;
  const budgetDiff = Math.max(0, price - budget);
  const preferenceBonus = payload.studentProfile.preferences.length > 0 ? 2 : 0;
  const featuredBonus = listing.isFeaturedListing ? 1 : 0;
  return budgetDiff - preferenceBonus - featuredBonus;
}

function renderListingResults(items) {
  if (!items.length) {
    listingResults.textContent = "No listings matched those filters. Try increasing budget or changing bedroom count.";
    return;
  }

  listingResults.innerHTML = items
    .map((item) => {
      const title = item.buildingName || item.statusText || "Listing";
      const price = getListingPrice(item);
      const formattedPrice = Number.isFinite(price) ? `$${price.toLocaleString()}/mo` : "Price unavailable";
      const unitSummary = Array.isArray(item.units) && item.units.length > 0
        ? item.units.map((unit) => `${unit.beds} bd`).join(", ")
        : "Beds unavailable";
      const address = item.address || "Address unavailable";
      const image = item.imgSrc || "";
      const link = item.detailUrl || "#";
      const safeTarget = link === "#" ? "" : 'target="_blank" rel="noopener noreferrer"';

      return `
        <article class="listing-item">
          <img class="listing-image" src="${image}" alt="${title}" />
          <div class="listing-content">
            <h3>${title}</h3>
            <p class="listing-meta">${formattedPrice} - ${unitSummary}</p>
            <p class="listing-meta">${address}</p>
            <a class="listing-link" href="${link}" ${safeTarget}>View listing</a>
          </div>
        </article>
      `;
    })
    .join("");
}

async function getListings() {
  if (Array.isArray(listingsCache)) return listingsCache;
  const response = await fetch(DATASET_PATH);
  if (!response.ok) {
    throw new Error("Unable to load listing dataset.");
  }
  const data = await response.json();
  listingsCache = Array.isArray(data) ? data : [];
  return listingsCache;
}

async function buildMatches(payload) {
  const listings = await getListings();
  const targetBedrooms = requiredBedroomCount(payload.studentProfile.bedrooms);
  const budget = payload.studentProfile.budget;

  const filtered = listings.filter((listing) => {
    const price = getListingPrice(listing);
    if (!Number.isFinite(price)) return false;
    if (price > budget) return false;
    return hasBedroomMatch(listing, targetBedrooms);
  });

  return filtered
    .sort((a, b) => scoreListing(a, payload, targetBedrooms) - scoreListing(b, payload, targetBedrooms))
    .slice(0, DEFAULT_RESULTS_LIMIT);
}

function saveToLocalStorage(payload) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload.studentProfile));
}

function loadStoredInput() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return;

  try {
    const saved = JSON.parse(raw);
    if (saved.budget) document.getElementById("max-rent").value = saved.budget;
    if (saved.bedrooms) document.getElementById("bedrooms").value = saved.bedrooms;
    if (saved.commuteConstraintMinutes) {
      document.getElementById("max-commute").value = saved.commuteConstraintMinutes;
    }
    if (saved.destination) document.getElementById("destination").value = saved.destination;
    if (saved.notes) document.getElementById("notes").value = saved.notes;

    if (saved.transportMode) {
      const radio = document.querySelector(`input[name="transportMode"][value="${saved.transportMode}"]`);
      if (radio) radio.checked = true;
    }

    if (Array.isArray(saved.preferences)) {
      saved.preferences.forEach((preference) => {
        const checkbox = document.querySelector(`input[name="preferences"][value="${preference}"]`);
        if (checkbox) checkbox.checked = true;
      });
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();

  const formData = new FormData(form);
  const payload = buildPayload(formData);
  const error = validatePayload(payload);

  if (error) {
    showError(error);
    return;
  }

  try {
    const matches = await buildMatches(payload);
    writeOutput(payload);
    renderListingResults(matches);
    saveToLocalStorage(payload);
  } catch (error) {
    showError(error instanceof Error ? error.message : "Failed to load listings.");
  }
});

copyButton.addEventListener("click", async () => {
  const text = output.textContent.trim();
  if (!text || text === "Submit the form to preview request JSON.") {
    showError("Submit the form before copying JSON.");
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    clearError();
  } catch {
    showError("Clipboard access failed. Copy manually from the payload box.");
  }
});

resetButton.addEventListener("click", () => {
  form.reset();
  clearError();
  output.textContent = "Submit the form to preview request JSON.";
  listingResults.textContent = "Submit the form to view matched listings.";
  localStorage.removeItem(STORAGE_KEY);
});

loadStoredInput();
