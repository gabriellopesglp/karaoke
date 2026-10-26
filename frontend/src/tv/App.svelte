<script>
  // Casca da TV: sidebar + palco, classes de estado no <body> (drawer,
  // immersive, idle, focus, darken-bg), atalhos de teclado, wake lock,
  // fullscreen e a tela de desligado.
  import { onMount } from "svelte";
  import { get } from "svelte/store";
  import Icon from "../shared/Icon.svelte";
  import Sidebar from "./Sidebar.svelte";
  import Stage from "./Stage.svelte";
  import ConfirmModal from "./ConfirmModal.svelte";
  import ShareModal from "./ShareModal.svelte";
  import LyricsModal from "./LyricsModal.svelte";
  import SettingsModal from "./SettingsModal.svelte";
  import ScoreOverlay from "./ScoreOverlay.svelte";
  import { player } from "./player.js";
  import {
    confirm,
    drawer,
    focusMode,
    immersive,
    initTV,
    lyricScale,
    darkenBg,
    lyricsOpen,
    off,
    playNext,
    queue,
    scoreEnabled,
    setLyricScale,
    setPitch,
    settingsOpen,
    shareOpen,
    togglePlay,
    toggleStemMute,
    wokeByTouch,
  } from "./store.js";

  // ---- classes de estado no <body> (o CSS do legado depende delas)
  $effect(() => document.body.classList.toggle("drawer", $drawer));
  $effect(() => document.body.classList.toggle("immersive", $immersive));
  $effect(() => document.body.classList.toggle("focus", $focusMode));
  $effect(() => document.body.classList.toggle("darken-bg", $darkenBg));
  $effect(() =>
    document.documentElement.style.setProperty("--ls", String($lyricScale)),
  );

  // ---- tela cheia (Fullscreen API + prefixo webkit) e wake lock
  const fsElement = () => document.fullscreenElement || document.webkitFullscreenElement;

  let wakeLock = null;
  async function requestWakeLock() {
    if (!("wakeLock" in navigator)) return;
    try {
      wakeLock = await navigator.wakeLock.request("screen");
    } catch (e) {
      wakeLock = null;
    }
  }
  function releaseWakeLock() {
    if (wakeLock) {
      wakeLock.release().catch(() => {});
      wakeLock = null;
    }
  }

  function setImmersive(on) {
    immersive.set(on);
    const root = document.documentElement;
    if (on && !fsElement()) {
      if (root.requestFullscreen) root.requestFullscreen().catch(() => {});
      else root.webkitRequestFullscreen?.();
      requestWakeLock();
    }
    if (!on && fsElement())
      (document.exitFullscreen || document.webkitExitFullscreen)?.call(document);
    if (!on) releaseWakeLock();
    wake();
  }

  function onFullscreenChange() {
    if (!fsElement() && get(immersive)) setImmersive(false);
  }

  // ---- idle: em tela cheia, controles somem com o mouse parado
  let idleTimer = null;
  function wake() {
    document.body.classList.remove("idle");
    clearTimeout(idleTimer);
    if (get(immersive)) idleTimer = setTimeout(() => document.body.classList.add("idle"), 2500);
  }

  // ---- atalhos de teclado
  function onKeydown(e) {
    if (get(confirm) || get(shareOpen) || get(lyricsOpen) || get(settingsOpen)) return;
    if (e.target.tagName === "INPUT" && e.target.type !== "range") return;
    if (e.key === " ") {
      e.preventDefault();
      togglePlay();
    } else if (e.key === "ArrowRight") player.seek(player.now() + 5);
    else if (e.key === "ArrowLeft") player.seek(player.now() - 5);
    else if (e.key.toLowerCase() === "v") toggleStemMute(0); // liga/desliga a voz
    else if (e.key === "/") {
      e.preventDefault();
      if (get(immersive)) setImmersive(false);
      document.getElementById("q")?.focus();
    } else if (e.key === "=" || e.key === "+") setLyricScale(get(lyricScale) + 0.1);
    else if (e.key === "-") setLyricScale(get(lyricScale) - 0.1);
    else if (e.key === "0") setLyricScale(1);
    else if (e.key.toLowerCase() === "f") setImmersive(!get(immersive));
    else if (e.key.toLowerCase() === "n" && get(queue).length) playNext();
    else if (e.key.toLowerCase() === "k") {
      // K = subir tom, Shift+K = descer tom
      setPitch(player.pitch + (e.shiftKey ? -1 : 1));
    } else if (e.key.toLowerCase() === "l") setPitch(0);
  }

  onMount(() => {
    initTV();

    // No toque não há mouse: um toque mostra os controles (sem pular a letra).
    const onPointerDown = (e) => {
      if (e.pointerType === "mouse") return;
      wokeByTouch.value = document.body.classList.contains("idle");
      wake();
    };
    // Só conta movimento real (há navegadores que disparam mousemove sem
    // o mouse sair do lugar)
    let lastXY = "";
    const onMouseMove = (e) => {
      const xy = `${Math.round(e.screenX / 4)},${Math.round(e.screenY / 4)}`;
      if (xy !== lastXY) {
        lastXY = xy;
        wake();
      }
    };
    const onVisibility = () => {
      // Re-ativa o wake lock quando a aba volta a ficar visível (o navegador
      // libera automaticamente quando a aba fica em segundo plano)
      if (wakeLock !== null && document.visibilityState === "visible") requestWakeLock();
    };
    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("visibilitychange", onVisibility);
    document.addEventListener("fullscreenchange", onFullscreenChange);
    document.addEventListener("webkitfullscreenchange", onFullscreenChange);
    document.addEventListener("keydown", onKeydown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown, true);
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("visibilitychange", onVisibility);
      document.removeEventListener("fullscreenchange", onFullscreenChange);
      document.removeEventListener("webkitfullscreenchange", onFullscreenChange);
      document.removeEventListener("keydown", onKeydown);
    };
  });
</script>

<Sidebar />
<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions (scrim do drawer) -->
<div class="scrim" onclick={() => drawer.set(false)}></div>
<Stage onToggleImmersive={() => setImmersive(!$immersive)} />

<ConfirmModal />
{#if $shareOpen}
  <ShareModal mode={$shareOpen} />
{/if}
{#if $lyricsOpen}
  <LyricsModal />
{/if}
{#if $settingsOpen}
  <SettingsModal />
{/if}
{#if $scoreEnabled}
  <ScoreOverlay />
{/if}

{#if $off}
  <div class="off-screen">
    <div>
      <Icon name="power" size={44} />
      <h2>Karaokê desligado</h2>
      <p>O servidor foi encerrado. Para abrir de novo, use o atalho <b>Karaoke Player</b> no Mac.</p>
    </div>
  </div>
{/if}
