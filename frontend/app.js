const form = document.getElementById("preferences-form");
const output = document.getElementById("json-output");
const errorEl = document.getElementById("form-error");
const copyButton = document.getElementById("copy-json");
const resetButton = document.getElementById("reset-button");
const listingResults = document.getElementById("listing-results");

const STORAGE_KEY = "campusnest.userInput.v1";
const API_ENDPOINT = "/api/recommendations";

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

function getListingPrice(listing) {
  if (Number.isFinite(listing.minBaseRent)) return listing.minBaseRent;
  if (Number.isFinite(listing.unformattedPrice)) return listing.unformattedPrice;
  if (Array.isArray(listing.units) && listing.units.length > 0) {
    const values = listing.units.map((unit) => parseCurrency(unit.price)).filter(Number.isFinite);
    if (values.length > 0) return Math.min(...values);
  }
  return NaN;
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
      const commute = Number.isFinite(item.estimated_commute_minutes)
        ? `${item.estimated_commute_minutes.toFixed(1)} min commute`
        : "Commute unavailable";
      const explanation = item.explanation?.explanation_text || "No AI explanation available for this listing yet.";
      const safeTarget = link === "#" ? "" : 'target="_blank" rel="noopener noreferrer"';

      return `
        <article class="listing-item">
          <img class="listing-image" src="${image}" alt="${title}" />
          <div class="listing-content">
            <h3>${title}</h3>
            <p class="listing-meta">${formattedPrice} - ${unitSummary}</p>
            <p class="listing-meta">${address}</p>
            <p class="listing-meta">${commute}</p>
            <p class="listing-explanation">${explanation}</p>
            <a class="listing-link" href="${link}" ${safeTarget}>View listing</a>
          </div>
        </article>
      `;
    })
    .join("");
}

async function fetchRecommendations(payload) {
  const response = await fetch(API_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error("Failed to fetch backend recommendations.");
  }
  return response.json();
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
    const apiResponse = await fetchRecommendations(payload);
    const matches = Array.isArray(apiResponse.listings) ? apiResponse.listings : [];
    writeOutput(payload);
    renderListingResults(matches);
    saveToLocalStorage(payload);
  } catch (error) {
    showError(error instanceof Error ? error.message : "Failed to load recommendations.");
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
