import "../shared/theme.css";
import { mount } from "svelte";
import App from "./App.svelte";
import { captureAuth } from "../shared/api.js";

// Guarda token/sessão do QR code no aparelho e limpa a barra de endereço
captureAuth();

mount(App, { target: document.getElementById("app") });
