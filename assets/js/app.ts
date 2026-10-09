import "vite/modulepreload-polyfill";

import htmx from "htmx.org";
import Alpine from "alpinejs";

import "@fontsource-variable/inter";

// Bloum dependencies
import "focus-trap";
import "@floating-ui/dom";

// Bloum
import "bloum/dist/bloum.min.css";
import * as Bloum from "bloum";
import { Combobox, Modal, Toast, init as initBloum } from "bloum";
import type { ComboboxInput } from "bloum/dist/types/components/combobox/combobox";
import type { BloumModalElement } from "bloum/dist/types/components/modal/modal";

import "../css/app.css";

declare global {
  interface Window {
    Alpine: typeof Alpine;
    Bloum: typeof Bloum;
    htmx: typeof htmx;
  }
}

window.Alpine = Alpine;
window.Bloum = Bloum;
window.htmx = htmx;

// No settle-based CSS transitions: to animate them, htmx gives the incoming
// elements the attributes of the outgoing ones sharing their id, then restores
// their own after a delay. Both steps break the page: the `value` it copies
// sticks to the input (a modal form reopened for a new object keeps the values
// of the one edited before), and the restore wipes what scripts set meanwhile
// (the `show` class of the tab panel after a boosted navigation).
htmx.config.defaultSettleDelay = 0;

function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? "";
}

// Django's CSRF protection for every htmx request.
document.addEventListener("htmx:config:request", (event) => {
  const token = csrfToken();
  if (token) (event as CustomEvent).detail.ctx.request.headers["X-CSRFToken"] = token;
});

Alpine.start();

initBloum();

type MessageLevel = "success" | "error" | "warning" | "info" | "debug";

function showToast(level: MessageLevel | string, text: string) {
  switch (level) {
    case "success":
      Toast.success(text);
      break;
    case "error":
      Toast.danger(text);
      break;
    case "warning":
      Toast.warning(text);
      break;
    default:
      Toast.show({ title: text, variant: "default", closeable: true });
  }
}

// Django messages rendered by the server become toasts.
function showMessages() {
  const script = document.getElementById("lorebook-messages");
  if (!script) return;
  try {
    const messages = JSON.parse(script.textContent ?? "[]") as { level: string; text: string }[];
    messages.forEach((message) => showToast(message.level.split(" ").pop() ?? "", message.text));
  } catch {
    // Malformed payload: ignore.
  }
  script.remove();
}
showMessages();

// Toasts sent with an HX-Trigger header: {"lorebook:toast": {"level": "success", "text": "…"}}
document.body.addEventListener("lorebook:toast", (event) => {
  const detail = (event as CustomEvent).detail ?? {};
  showToast(detail.level ?? "info", detail.text ?? "");
});

// Interface strings translated by Django (core/base.html).
const strings: Record<string, string> = (() => {
  try {
    return JSON.parse(document.getElementById("lorebook-strings")?.textContent ?? "{}");
  } catch {
    return {};
  }
})();

function enhance(root: ParentNode = document) {
  root.querySelectorAll<ComboboxInput>(".input-combobox").forEach((el) => {
    if (el.blcombobox !== undefined) return;
    new Combobox(el, {
      isSearchable: true,
      placeholder: strings.comboboxPlaceholder,
      noResultsText: strings.noResults,
    });
  });

  // Fragments returned by the server can ask for their modal to open.
  root.querySelectorAll<BloumModalElement>(".modal[data-autoshow]").forEach((el) => {
    el.removeAttribute("data-autoshow");
    (el.blmodal ?? new Modal(el)).open();
  });
}

document.addEventListener("htmx:after:process", (event) => {
  enhance((event.target as ParentNode) ?? document);
});
enhance();

// When a modal form fails validation, htmx swaps the form in place: keep the
// modal open and move the focus to the first invalid field.
document.addEventListener("htmx:after:swap", (event) => {
  const target = (event as CustomEvent).detail?.ctx?.target as HTMLElement | undefined;
  const form = target?.isConnected ? target : document.querySelector<HTMLElement>(".lore-form .field-danger");
  form?.querySelector<HTMLElement>("[aria-invalid=true], .field-danger .input")?.focus();
});

// Generic class toggles (mobile navigation of the portals).
document.addEventListener("click", (event) => {
  const trigger = (event.target as HTMLElement).closest<HTMLElement>("[data-toggle-class]");
  if (!trigger) return;
  const target = document.querySelector(trigger.dataset.toggleTarget ?? "body");
  target?.classList.toggle(trigger.dataset.toggleClass ?? "");
});

// Client-side filtering of a table (glossary drawer).
document.addEventListener("input", (event) => {
  const input = event.target as HTMLInputElement;
  const selector = input.dataset?.filterTable;
  if (!selector) return;
  const query = input.value.trim().toLowerCase();
  document.querySelectorAll<HTMLTableRowElement>(`${selector} tbody tr`).forEach((row) => {
    row.hidden = query !== "" && !row.textContent?.toLowerCase().includes(query);
  });
});

// Copy buttons on code blocks of the portals.
function addCopyButtons() {
  document.querySelectorAll<HTMLElement>(".prose .code-block").forEach((block) => {
    if (block.querySelector(".code-copy")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "code-copy btn btn-ghost btn-xs";
    button.setAttribute("aria-label", strings.copy ?? "Copy");
    button.innerHTML = '<i class="fa-regular fa-copy"></i>';
    button.addEventListener("click", async () => {
      const code = block.querySelector("code")?.textContent ?? "";
      await navigator.clipboard.writeText(code);
      button.innerHTML = '<i class="fa-solid fa-check"></i>';
      setTimeout(() => (button.innerHTML = '<i class="fa-regular fa-copy"></i>'), 1500);
    });
    block.appendChild(button);
  });
}
addCopyButtons();

// Highlight the current heading in the table of contents.
function trackToc() {
  const links = Array.from(document.querySelectorAll<HTMLAnchorElement>(".reader-toc a"));
  if (!links.length || !("IntersectionObserver" in window)) return;
  const byId = new Map(links.map((link) => [decodeURIComponent(link.hash.slice(1)), link]));
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        links.forEach((link) => link.classList.remove("active"));
        byId.get(entry.target.id)?.classList.add("active");
      });
    },
    { rootMargin: "0px 0px -70% 0px" },
  );
  byId.forEach((_link, id) => {
    const heading = document.getElementById(id);
    if (heading) observer.observe(heading);
  });
}
trackToc();
