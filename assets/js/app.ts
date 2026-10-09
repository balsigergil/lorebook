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
import { Combobox, init as initBloum } from "bloum";

import "../css/app.css";
import { ComboboxInput } from "bloum/dist/types/components/combobox/combobox";

// @ts-ignore
window.Alpine = Alpine;
// @ts-ignore
window.Bloum = Bloum;
// @ts-ignore
window.htmx = htmx;

// No settle-based CSS transitions: to animate them, htmx gives the incoming
// elements the attributes of the outgoing ones sharing their id, then restores
// their own after a delay. Both steps break the page: the `value` it copies
// sticks to the input (a modal form reopened for a new object keeps the values
// of the one edited before), and the restore wipes what scripts set meanwhile
// (the `show` class of the tab panel after a boosted navigation).
htmx.config.defaultSettleDelay = 0;

Alpine.start();

initBloum();

document.addEventListener("htmx:after:process", () => {
  document.querySelectorAll<ComboboxInput>(".input-combobox").forEach((el) => {
    if (el.blcombobox !== undefined) {
      return;
    }
    new Combobox(el, {
      isSearchable: true,
      noResultsText: "Aucun résultat",
    });
  });
});
