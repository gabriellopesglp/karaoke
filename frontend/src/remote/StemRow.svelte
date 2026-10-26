<script>
  // Linha do mixer: slider de volume protegido contra re-render durante o
  // gesto (o bug do legado): enquanto o dedo está no slider, o valor é local.
  import Icon from "../shared/Icon.svelte";
  import { cmd, view } from "./store.js";

  let { stem, index } = $props();

  let dragging = $state(false);
  let localVol = $state(0);
  let lastSent = 0;

  const vol = $derived(dragging ? localVol : stem.vol || 0);

  function sendVol(v) {
    const stems = ($view?.stems || []).map((s, i) => (i === index ? { ...s, vol: v } : s));
    cmd({ type: "stemVol", index, vol: v }, { stems });
  }

  function onInput(e) {
    dragging = true;
    localVol = +e.currentTarget.value;
    // manda no máximo 1 comando a cada 100 ms durante o arrasto
    const now = Date.now();
    if (now - lastSent > 100) {
      lastSent = now;
      sendVol(localVol);
    }
  }

  function onChange(e) {
    sendVol(+e.currentTarget.value); // valor final sempre vai
    dragging = false;
  }

  function toggleMute() {
    const stems = ($view?.stems || []).map((s, i) =>
      i === index ? { ...s, muted: !s.muted } : s,
    );
    cmd({ type: "stemMute", index }, { stems });
  }
</script>

<div class="stem" class:muted={stem.muted}>
  <button
    class="mutebtn"
    aria-label={stem.muted ? `Ativar ${stem.label}` : `Silenciar ${stem.label}`}
    aria-pressed={!!stem.muted}
    onclick={toggleMute}
  >
    <Icon name={stem.muted ? "mute" : "vol"} size={20} />
  </button>
  <span class="name">{stem.label}</span>
  <input
    type="range"
    class="slider"
    min="0"
    max="100"
    step="1"
    value={vol}
    style="--v:{vol}%"
    aria-label={`Volume de ${stem.label}`}
    oninput={onInput}
    onchange={onChange}
  />
  <span class="pct">{Math.round(vol)}</span>
</div>

<style>
  .stem {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .mutebtn {
    width: 44px;
    height: 44px;
    flex: none;
    display: grid;
    place-items: center;
    border-radius: var(--radius);
    border: 1px solid var(--line);
    background: var(--panel-2);
    color: var(--text);
  }
  .mutebtn[aria-pressed="true"] {
    color: var(--err);
    border-color: color-mix(in srgb, var(--err) 40%, transparent);
  }
  .name {
    width: 86px;
    flex: none;
    font-size: 14px;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .stem.muted .name {
    text-decoration: line-through;
    color: var(--dim);
  }
  .stem.muted .slider {
    opacity: 0.4;
  }
  .pct {
    width: 30px;
    flex: none;
    text-align: right;
    font-size: 13px;
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }
</style>
