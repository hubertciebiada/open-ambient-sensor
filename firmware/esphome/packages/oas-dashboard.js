// OAS on-device dashboard add-on — served as /0.js by web_server (js_include
// in core.yaml) next to ESPHome's stock v3 page.
//
// Makes the dashboard's cards foldable: tap a card's title to fold or unfold
// it. On every page load a card starts open only if it holds nothing but
// plain readings (sensors, binary sensors, text sensors without an entity
// category); a card with anything you can change (a slider, switch, select,
// time, button) or with diagnostics starts folded, so a thumb scrolling the
// page on a phone cannot move a threshold by accident. A card folded or
// unfolded by hand stays that way until the page is reloaded.
//
// Entities stream in after the page loads, by type (binary sensors and
// sensors before switches, numbers and selects), and a card's state is set
// when its first entity arrives. In every OAS settings card that first
// entity is already a config or diagnostic one, so none shows open for a
// moment while the page fills.
//
// It works on the stock page's own markup (esp-app > esp-entity-table, one
// .tab-header + .tab-container pair per sorting group) and does nothing if
// that markup is not there.

const READINGS = new Set(["sensor", "binary_sensor", "text_sensor"]);
const plainReading = (e) => READINGS.has(e.domain) && !e.entity_category;
const chosen = new Map(); // card title -> open, for cards tapped this visit

// The stock titles are inline-flex, which only works while a card's rows sit
// under each title; folded titles would run together on one line. Flex +
// fit-content keeps the tab look and puts every title on its own line. The
// stock rule sits in an adopted stylesheet, which outranks this <style> at
// equal specificity — hence div.tab-header.
const STYLE = `
div.tab-header {
  display: flex; width: fit-content; cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.tab-header::before { content: "\\25BE"; margin-inline-end: .5em; }
.tab-header.oas-folded::before { content: "\\25B8"; }
.tab-header.oas-folded { border-radius: 12px; }
.tab-header.oas-folded::after {
  content: "(" attr(data-oas-count) ")"; margin-inline-start: .5em; opacity: .6;
}
`;

function fold(table) {
  const entities = table.entities || [];
  for (const head of table.shadowRoot.querySelectorAll(".tab-header")) {
    const box = head.nextElementSibling;
    if (!box || !box.classList.contains("tab-container")) continue;
    const name = head.textContent.trim();
    const open = chosen.has(name)
      ? chosen.get(name)
      : !entities.some((e) => e.sorting_group === name && !plainReading(e));
    box.style.display = open ? "" : "none";
    head.classList.toggle("oas-folded", !open);
    head.setAttribute("aria-expanded", String(open));
    head.dataset.oasCount = box.querySelectorAll(".entity-row").length;
    if (head.oasFoldable) continue;
    head.oasFoldable = true;
    head.setAttribute("role", "button");
    head.tabIndex = 0;
    const toggle = () => {
      chosen.set(head.textContent.trim(), box.style.display === "none");
      fold(table);
    };
    head.addEventListener("click", toggle);
    head.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter" && ev.key !== " ") return;
      ev.preventDefault();
      toggle();
    });
  }
}

function attach() {
  const app = document.querySelector("esp-app");
  const table = app && app.shadowRoot && app.shadowRoot.querySelector("esp-entity-table");
  if (!table || !table.shadowRoot) return false;
  const style = document.createElement("style");
  style.textContent = STYLE;
  table.shadowRoot.appendChild(style);
  // Cards and rows arrive over the event stream after the page loads;
  // re-apply on every insertion (childList only — state updates rewrite
  // text, not nodes, so they do not wake this up).
  new MutationObserver(() => fold(table)).observe(table.shadowRoot, { childList: true, subtree: true });
  fold(table);
  return true;
}

if (!attach()) {
  const poll = setInterval(() => attach() && clearInterval(poll), 100);
  setTimeout(() => clearInterval(poll), 60000);
}
