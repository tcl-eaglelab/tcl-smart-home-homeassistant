/* Presentation only: all QR actions continue through HA's native flow handlers. */
const MARKER = "tcl-qr-layout";
const STYLE = `
  :host([data-tcl-qr]) .content { display: none; }
  :host([data-tcl-qr]) .options { display: none; }
  .tcl-qr-card { margin-top: 8px; text-align: center; }
  .tcl-qr-card ha-markdown { display: block; text-align: center; }
  .tcl-qr-frame {
    width: 280px; max-width: 100%; margin: 20px auto;
    padding: 8px; box-sizing: border-box; background: #fff;
    border: 1px solid var(--divider-color, #e5e7eb); border-radius: 12px;
  }
  .tcl-qr-frame img { display: block; width: 100%; height: auto; aspect-ratio: 1; }
  .tcl-qr-help { font-size: 12px; color: var(--secondary-text-color); }
  .tcl-qr-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 12px;
    margin: 24px 0 8px;
  }
  .tcl-qr-button {
    width: 100%; min-height: 44px; padding: 10px 12px; border-radius: 10px;
    border: 1px solid var(--primary-color); background: transparent;
    color: var(--primary-color); font: inherit; font-size: 14px;
    font-weight: 600; cursor: pointer;
  }
  .tcl-qr-confirm { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .tcl-qr-button:hover { filter: brightness(.95); }
  .tcl-qr-button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 3px; }
  .tcl-qr-actions.single { grid-template-columns: 1fr; }
  @media (max-width: 380px) {
    .tcl-qr-actions { grid-template-columns: 1fr; gap: 10px; }
  }
`;

const rendered = new WeakMap();
function decorate(menu) {
  const root = menu.shadowRoot;
  if (!root) return;
  const isTclQr = menu.step?.handler === "tcl_smart_home"
    && menu.step.step_id?.startsWith("authorize");
  if (!isTclQr) {
    rendered.delete(menu);
    menu.removeAttribute("data-tcl-qr");
    root.getElementById(MARKER)?.remove();
    root.querySelector(".tcl-qr-actions")?.remove();
    root.querySelector(".tcl-qr-card")?.remove();
    return;
  }
  const items = [...root.querySelectorAll(".options ha-list-item")];
  if (!items.length) return; // Keep HA's original UI if its structure changes.
  const markdown = root.querySelector(".content ha-markdown");
  if (typeof markdown?.content !== "string") return;
  const qrUrl = menu.step.description_placeholders?.qr_url;
  const content = markdown.content;
  const signature = JSON.stringify([menu.step.step_id, qrUrl, content,
    items.map(item => [item.step, item.querySelector("span")?.textContent])]);
  if (rendered.get(menu) === signature && root.querySelector(".tcl-qr-card")) return;
  const imageStart = content.indexOf("![");
  const imageEnd = qrUrl ? content.indexOf(`](${qrUrl})`, imageStart) : -1;
  const hasImage = imageStart >= 0 && imageEnd >= 0;
  const card = document.createElement("div");
  card.className = "tcl-qr-card";
  const instructions = document.createElement("ha-markdown");
  instructions.content = hasImage ? content.slice(0, imageStart).trim() : content;
  instructions.breaks = true;
  card.append(instructions);
  if (hasImage) {
    const frame = document.createElement("div");
    frame.className = "tcl-qr-frame";
    const image = document.createElement("img");
    image.alt = content.slice(imageStart + 2, imageEnd);
    image.referrerPolicy = "no-referrer";
    image.src = qrUrl;
    frame.append(image);
    card.append(frame);
    const help = document.createElement("ha-markdown");
    help.className = "tcl-qr-help";
    help.content = content.slice(imageEnd + qrUrl.length + 3).trim();
    card.append(help);
  }
  const actions = document.createElement("div");
  actions.className = "tcl-qr-actions";
  for (const action of ["refresh_qr", "check_authorization"]) {
    const nativeItem = items.find(item => item.step === action);
    if (!nativeItem) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tcl-qr-button" + (action === "check_authorization" ? " tcl-qr-confirm" : "");
    button.dataset.action = action;
    button.textContent = nativeItem.querySelector("span")?.textContent?.trim() || "";
    // Delegate to HA's existing click handler, preserving loading/error behavior.
    button.addEventListener("click", () => nativeItem.click());
    actions.append(button);
  }
  if (actions.children.length !== items.length) return;
  if (actions.children.length === 1) actions.classList.add("single");
  let style = root.getElementById(MARKER);
  if (!style) {
    style = document.createElement("style");
    style.id = MARKER;
    style.textContent = STYLE;
    root.append(style);
  }
  const previous = root.querySelector(".tcl-qr-actions");
  const previousCard = root.querySelector(".tcl-qr-card");
  if (previousCard) previousCard.replaceWith(card);
  else root.querySelector(".options").before(card);
  if (previous) previous.replaceWith(actions);
  else root.append(actions);
  menu.setAttribute("data-tcl-qr", "");
  rendered.set(menu, signature);
}

// Observe the dialog host chain instead of patching a global HA prototype.
const observers = new Map();
let scheduled = false;
function scheduleScan() {
  if (scheduled) return;
  scheduled = true;
  requestAnimationFrame(() => { scheduled = false; scan(); });
}
function scan() {
  const active = new Set();
  function visit(root) {
    active.add(root);
    for (const element of root.querySelectorAll("*")) {
      if (element.localName === "step-flow-menu" && element.shadowRoot) {
        const menuRoot = element.shadowRoot;
        active.add(menuRoot);
        // Disconnect while rendering our own nodes to avoid observer loops.
        observers.get(menuRoot)?.disconnect();
        decorate(element);
      }
      if (element.shadowRoot && (element.localName === "home-assistant"
          || element.localName.includes("dialog") || element.localName.includes("flow"))) {
        visit(element.shadowRoot);
      }
    }
  }
  for (const observer of observers.values()) observer.disconnect();
  visit(document);
  for (const [root, observer] of observers) {
    if (!active.has(root)) { observer.disconnect(); observers.delete(root); }
  }
  for (const root of active) {
    if (!observers.has(root)) observers.set(root, new MutationObserver(scheduleScan));
    observers.get(root).observe(root, {childList: true, subtree: true, characterData: true});
  }
}
customElements.whenDefined("step-flow-menu").then(scheduleScan);
