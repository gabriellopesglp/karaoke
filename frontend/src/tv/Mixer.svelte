<script>
  // Mixer: uma linha por stem (mute, nome, volume, %). O estado mora no
  // player; stemsVersion força a releitura quando o controle remoto muda algo.
  import Icon from "../shared/Icon.svelte";
  import { player } from "./player.js";
  import { bumpStems, setStemVol, stemsVersion, toggleStemMute } from "./store.js";

  const stems = $derived.by(() => {
    $stemsVersion;
    return player.stems.map((s) => ({ ...s }));
  });
</script>

<div class="mixer">
  {#each stems as s, i (s.label)}
    <div class="stem" class:muted={s.muted}>
      <button
        class="mute"
        title="Tirar/voltar esta faixa"
        aria-label="Tirar/voltar {s.label}"
        aria-pressed={s.muted}
        onclick={() => { toggleStemMute(i); bumpStems(); }}
      >
        <Icon name={s.muted ? "mute" : "vol"} size={16} />
      </button>
      <span class="name">{s.label}</span>
      <input
        type="range"
        min="0"
        max="100"
        value={s.vol}
        style="--v:{s.vol}%"
        aria-label="Volume de {s.label}"
        oninput={(e) => {
          e.currentTarget.style.setProperty("--v", `${e.currentTarget.value}%`);
          setStemVol(i, +e.currentTarget.value);
          bumpStems();
        }}
      />
      <span class="pct">{s.vol}%</span>
    </div>
  {/each}
</div>
