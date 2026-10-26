<script>
  // Transporte: play/pausa, tempos, seek e próxima da fila.
  // O slider usa o padrão do remoto: valor local durante o arrasto.
  import Icon from "../shared/Icon.svelte";
  import { fmtTime } from "../shared/fmt.js";
  import { player } from "./player.js";
  import { frame, playNext, ready, togglePlay } from "./store.js";

  let { next } = $props();

  let seeking = $state(false);
  let seekVal = $state(0); // 0..1000

  const dur = $derived($frame.duration);
  const shown = $derived(seeking ? seekVal : dur ? Math.round(($frame.t / dur) * 1000) : 0);
  const curText = $derived(fmtTime(seeking ? (seekVal / 1000) * dur : $frame.t));

  function onInput(e) {
    seeking = true;
    seekVal = +e.currentTarget.value;
  }
  function onChange(e) {
    player.seek((+e.currentTarget.value / 1000) * dur);
    seeking = false;
  }
</script>

<div class="transport">
  <button
    class="play"
    disabled={!$ready}
    title="Tocar/pausar (espaço)"
    aria-label={$frame.playing ? "Pausar" : "Tocar"}
    onclick={togglePlay}
  >
    <Icon name={$frame.playing ? "pause" : "play"} size={20} />
  </button>
  <span class="time">{curText}</span>
  <input
    type="range"
    min="0"
    max="1000"
    value={shown}
    disabled={!$ready}
    style="--v:{shown / 10}%"
    aria-label="Posição na música"
    oninput={onInput}
    onchange={onChange}
  />
  <span class="time">{fmtTime(dur)}</span>
  <button
    class="icon-btn"
    title="Próxima da fila (N)"
    aria-label="Próxima da fila"
    disabled={!next}
    onclick={playNext}
  >
    <Icon name="next" size={18} />
  </button>
</div>
