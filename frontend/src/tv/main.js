// Entrada da TV: hacks anti-zoom do iOS, audioSession e montagem do app.
import "../shared/theme.css";
import "./tv.css";
import { mount } from "svelte";
import App from "./App.svelte";
import { captureAuth } from "../shared/api.js";

// Guarda o token do QR code (?t=) no aparelho e tira da barra de endereço
captureAuth();

// Bloqueia o double-tap e o pinch-to-zoom no Safari/iPad.
// O Safari ignora user-scalable=no e touch-action:manipulation em alguns
// casos, então cancelamos manualmente eventos de toque duplo e gesto.
let lastTouchEnd = 0;
document.addEventListener(
  "touchend",
  (e) => {
    const now = Date.now();
    if (now - lastTouchEnd <= 300) e.preventDefault();
    lastTouchEnd = now;
  },
  { passive: false },
);
// Bloqueia pinch-to-zoom: qualquer movimento com 2+ dedos é cancelado.
document.addEventListener(
  "touchmove",
  (e) => {
    if (e.touches.length > 1) e.preventDefault();
  },
  { passive: false },
);
document.addEventListener("gesturestart", (e) => e.preventDefault(), { passive: false });
document.addEventListener("gesturechange", (e) => e.preventDefault(), { passive: false });

// iPhone/iPad: toca mesmo com a chave do modo silencioso ligada
try {
  if (navigator.audioSession) navigator.audioSession.type = "playback";
} catch (e) {}

mount(App, { target: document.getElementById("app") });
