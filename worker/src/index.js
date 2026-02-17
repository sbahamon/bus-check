/**
 * bus-check-collector: Cloudflare Worker that polls CTA Bus Tracker API
 * every 5 minutes and writes vehicle positions to D1.
 *
 * Replaces the GitHub Actions collector (scripts/collect_to_d1.py) with
 * higher-frequency polling for better headway detection.
 */

// Mirrors src/bus_check/config.py ALL_FREQUENT_ROUTES
const ALL_ROUTES = [
  "J14", "34", "47", "54", "60", "63", "79", "95", // Phase 1
  "4", "20", "49", "66",                             // Phase 2
  "53", "55", "77", "82",                             // Phase 3
  "9", "12", "72", "81",                              // Phase 4
];

const BATCH_SIZE = 10; // CTA API max routes per getvehicles call
const CTA_API_BASE = "http://www.ctabustracker.com/bustime/api/v2";

// Mirrors config.py SERVICE_WINDOW_WEEKDAY / SERVICE_WINDOW_WEEKEND
const SERVICE_WINDOW = {
  weekday: { start: 6, end: 21 }, // 6am-9pm
  weekend: { start: 9, end: 21 }, // 9am-9pm
};

const INSERT_SQL =
  "INSERT INTO vehicle_positions " +
  "(collected_at, vid, tmstmp, route, direction, destination, " +
  "lat, lon, heading, speed, pdist, pattern_id, delayed) " +
  "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";

/**
 * Check if current Chicago time is within the FN service window.
 * Mirrors config.py is_in_service_window().
 */
function isInServiceWindow() {
  const now = new Date();
  // Get Chicago hour and day of week
  const chicagoStr = now.toLocaleString("en-US", { timeZone: "America/Chicago" });
  const chicago = new Date(chicagoStr);
  const hour = chicago.getHours();
  const day = chicago.getDay(); // 0=Sun, 6=Sat
  const isWeekday = day >= 1 && day <= 5;
  const window = isWeekday ? SERVICE_WINDOW.weekday : SERVICE_WINDOW.weekend;
  return { inWindow: hour >= window.start && hour < window.end, chicagoStr };
}

/**
 * Fetch vehicle positions from CTA Bus Tracker API.
 * Mirrors bus_tracker.py BusTrackerClient.get_vehicles().
 */
async function fetchVehicles(apiKey) {
  const allVehicles = [];

  for (let i = 0; i < ALL_ROUTES.length; i += BATCH_SIZE) {
    const batch = ALL_ROUTES.slice(i, i + BATCH_SIZE);
    const rt = batch.join(",");
    const url = `${CTA_API_BASE}/getvehicles?key=${apiKey}&rt=${rt}&format=json`;

    try {
      const resp = await fetch(url);
      if (!resp.ok) {
        console.error(`CTA API HTTP ${resp.status} for routes ${rt}`);
        continue;
      }

      const data = await resp.json();
      const bustime = data["bustime-response"] || {};

      // Check for API-level errors (non-fatal)
      if (bustime.error) {
        const msgs = bustime.error.map((e) => e.msg || JSON.stringify(e));
        if (msgs.some((m) => m.includes("No data found"))) {
          continue;
        }
        console.error(`CTA API error for routes ${rt}: ${msgs.join("; ")}`);
        continue;
      }

      // CTA returns a dict (not array) for single vehicle — normalize
      let vehicles = bustime.vehicle || [];
      if (!Array.isArray(vehicles)) {
        vehicles = [vehicles];
      }
      allVehicles.push(...vehicles);
    } catch (err) {
      console.error(`Fetch failed for routes ${rt}: ${err.message}`);
    }
  }

  return allVehicles;
}

/**
 * Insert vehicle positions into D1 using batch().
 * Each position is a separate prepared statement in one transaction.
 */
async function insertPositions(db, vehicles, collectedAt) {
  if (vehicles.length === 0) return 0;

  const stmt = db.prepare(INSERT_SQL);

  // Transform and bind — mirrors collect_to_d1.py lines 57-74
  const statements = vehicles.map((v) =>
    stmt.bind(
      collectedAt,
      String(v.vid ?? ""),
      String(v.tmstmp ?? ""),
      String(v.rt ?? ""),
      v.rtdir ?? null,
      v.des ?? null,
      parseFloat(v.lat) || 0,
      parseFloat(v.lon) || 0,
      v.hdg != null ? parseInt(v.hdg, 10) : null,
      v.spd != null ? parseInt(v.spd, 10) : null,
      v.pdist != null ? parseInt(v.pdist, 10) : null,
      v.pid != null ? String(v.pid) : null,
      v.dly ? 1 : 0
    )
  );

  // D1 batch() handles up to ~100 statements per call
  const CHUNK_SIZE = 100;
  for (let i = 0; i < statements.length; i += CHUNK_SIZE) {
    await db.batch(statements.slice(i, i + CHUNK_SIZE));
  }

  return vehicles.length;
}

export default {
  async scheduled(controller, env, ctx) {
    const { inWindow, chicagoStr } = isInServiceWindow();
    if (!inWindow) {
      console.log(`Outside service window (Chicago: ${chicagoStr}). Skipping.`);
      return;
    }

    if (!env.CTA_API_KEY) {
      console.error("CTA_API_KEY secret not set");
      return;
    }

    const vehicles = await fetchVehicles(env.CTA_API_KEY);
    if (vehicles.length === 0) {
      console.log("No vehicles returned from CTA API.");
      return;
    }

    const collectedAt = new Date().toISOString();
    const count = await insertPositions(env.DB, vehicles, collectedAt);
    console.log(`Collected ${count} vehicle positions at ${collectedAt}`);
  },

  // Health check endpoint
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      const result = await env.DB.prepare(
        "SELECT COUNT(*) as total, MAX(collected_at) as last_poll FROM vehicle_positions"
      ).first();

      return Response.json({
        status: "ok",
        total_positions: result?.total,
        last_poll: result?.last_poll,
        in_service_window: isInServiceWindow().inWindow,
      });
    }

    return new Response("bus-check-collector", { status: 200 });
  },
};
