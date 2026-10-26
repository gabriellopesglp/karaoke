<script>
  // Aba Controle: transporte, seek, mixer de stems e ajustes da letra/tela.
  // Tudo com UI otimista (ver store.js) e sliders protegidos durante o gesto.
  import Cover from "./Cover.svelte";
  import Icon from "../shared/Icon.svelte";
  import StemRow from "./StemRow.svelte";
  import { fmtOffset, fmtPitch, fmtTime } from "../shared/fmt.js";
  import { cmd, position, refreshSessionState, view } from "./store.js";

  const song = $derived($view?.song || null);
  const playing = $derived(!!$view?.playing);
  const stems = $derived($view?.stems || []);
  const pitch = $derived($view?.pitch || 0);
  const keyOrig = $derived($view?.keyOrig);
  const offset = $derived($view?.offset || 0);
  const size = $derived($view?.size || 1);
  let toggles = $state({ bg: false, focus: false, paint: false, score: false });

  $effect(() => {
    toggles = {
      bg: !!$view?.bg,
      focus: !!$view?.focus,
      paint: !!$view?.paint,
      score: !!$view?.score,
    };
  });

  // ---- seek: valor local durante o arrasto; comando vai no release
  let dragging = $state(false);
  let dragVal = $state(0);
  const dur = $derived($position.dur);
  const seekVal = $derived(dragging ? dragVal : dur ? Math.round(($position.cur / dur) * 1000) : 0);
  const curShown = $derived(dragging ? (dragVal / 1000) * dur : $position.cur);

  function onSeekInput(e) {
    dragging = true;
    dragVal = +e.currentTarget.value;
  }
  function onSeekChange(e) {
    const v = +e.currentTarget.value;
    dragging = false;
    if (!dur) return;
    const t = (v / 1000) * dur;
    cmd({ type: "seek", t }, { cur: t });
  }

  // ---- ajustes
  const round2 = (n) => Math.round(n * 100) / 100;

  function nudgePitch(d) {
    cmd({ type: "pitch", semi: pitch + d }, { pitch: pitch + d });
  }
  function nudgeOffset(d) {
    cmd({ type: "lyricsOffset", delta: d }, { offset: round2(offset + d) });
  }
  function nudgeSize(d) {
    const s = round2(Math.max(0.5, Math.min(2, size + d)));
    cmd({ type: "fontSize", scale: s }, { size: s });
  }
  function toggle(key) {
    const next = !toggles[key];
    toggles = { ...toggles, [key]: next };
    cmd({ type: "toggle", key }, { [key]: next }).finally(() => {
      setTimeout(() => refreshSessionState(), 120);
    });
  }

  let mixerOpen = $state(true);
</script>

<section class="card player">
  {#if song}
    <div class="art">
      <Cover folder={song.folder} size={560} radius={10} hasCover={true} />
    </div>
    <div class="title">{song.track}</div>
    <div class="artist">{song.artist}</div>
  {:else}
    <div class="art placeholder">
      <Icon name="note" size={64} />
    </div>
    <div class="title">Nada tocando</div>
    <div class="artist">Escolha uma música na aba Buscar</div>
  {/if}

  <div class="transport">
    <button class="tbtn" aria-label="Reiniciar a música" onclick={() => cmd({ type: "prev" }, playing ? { cur: 0 } : null)}>
      <Icon name="prev" size={26} />
    </button>
    <button class="tbtn play" aria-label={playing ? "Pausar" : "Tocar"} onclick={() => cmd({ type: "play" }, { playing: !playing })}>
      <Icon name={playing ? "pause" : "play"} size={30} />
    </button>
    <button class="tbtn" aria-label="Próxima da fila" onclick={() => cmd({ type: "next" })}>
      <Icon name="next" size={26} />
    </button>
  </div>

  <div class="seekrow">
    <span class="time">{fmtTime(curShown)}</span>
    <input
      type="range"
      class="slider"
      min="0"
      max="1000"
      value={seekVal}
      disabled={!dur}
      style="--v:{seekVal / 10}%"
      aria-label="Posição na música"
      oninput={onSeekInput}
      onchange={onSeekChange}
    />
    <span class="time">{fmtTime(dur)}</span>
  </div>
</section>

<section class="card">
  <button class="secthead" aria-expanded={mixerOpen} onclick={() => (mixerOpen = !mixerOpen)}>
    <span>Mixer</span>
    <Icon name={mixerOpen ? "up" : "down"} size={20} />
  </button>
  {#if mixerOpen}
    <div class="mixer">
      {#if stems.length === 0}
        <p class="dim">O mixer aparece quando uma música estiver tocando.</p>
      {:else}
        {#each stems as stem, i (i)}
          <StemRow {stem} index={i} />
        {/each}
      {/if}
    </div>
  {/if}
</section>

<section class="card">
  <div class="secthead static"><span>Ajustes</span></div>
  <div class="adjusts">
    <div class="arow">
      <span class="albl">Tom</span>
      <div class="stepper">
        <button class="sbtn" aria-label="Abaixar o tom" onclick={() => nudgePitch(-1)}>
          <Icon name="minus" size={18} />
        </button>
        <span class="val" class:nonzero={pitch !== 0}>{fmtPitch(pitch, keyOrig)}</span>
        <button class="sbtn" aria-label="Subir o tom" onclick={() => nudgePitch(1)}>
          <Icon name="plus" size={18} />
        </button>
        <button
          class="sbtn reset"
          aria-label="Voltar ao tom original"
          title="Voltar ao tom original"
          disabled={pitch === 0}
          onclick={() => cmd({ type: "pitch", semi: 0 }, { pitch: 0 })}
        >
          <Icon name="refresh" size={16} />
        </button>
      </div>
    </div>

    <div class="arow">
      <span class="albl">Letra</span>
      <div class="stepper">
        <button class="sbtn" aria-label="Atrasar a letra" onclick={() => nudgeOffset(-0.05)}>
          <Icon name="minus" size={18} />
        </button>
        <button
          class="val btnval"
          class:nonzero={Math.abs(offset) > 0.001}
          title="Toque para zerar"
          onclick={() => cmd({ type: "lyricsResetOffset" }, { offset: 0 })}
        >
          {fmtOffset(offset)}
        </button>
        <button class="sbtn" aria-label="Adiantar a letra" onclick={() => nudgeOffset(0.05)}>
          <Icon name="plus" size={18} />
        </button>
          <button
            class="sbtn reset"
            aria-label="Zerar ajuste da letra"
            title="Zerar ajuste da letra"
            disabled={Math.abs(offset) <= 0.001}
            onclick={() => cmd({ type: "lyricsResetOffset" }, { offset: 0 })}
          >
            <Icon name="refresh" size={16} />
          </button>
      </div>
    </div>

    <div class="arow">
      <span class="albl">Tamanho</span>
      <div class="stepper">
        <button class="sbtn aa" aria-label="Diminuir a letra" onclick={() => nudgeSize(-0.1)}>A−</button>
        <span class="val" class:nonzero={Math.abs(size - 1) > 0.001}>{Math.round(size * 100)}%</span>
        <button class="sbtn aa" aria-label="Aumentar a letra" onclick={() => nudgeSize(0.1)}>A+</button>
          <button
            class="sbtn reset"
            aria-label="Voltar ao tamanho normal"
            title="Voltar ao tamanho normal"
            disabled={Math.abs(size - 1) <= 0.001}
            onclick={() => cmd({ type: "fontSize", scale: 1 }, { size: 1 })}
          >
            <Icon name="refresh" size={16} />
          </button>
      </div>
    </div>

    <div class="toggles">
      <button type="button" class="switch" aria-pressed={toggles.bg} onclick={() => toggle("bg")}>
        <span class="pill"></span>
        <Icon name="moon" size={18} /> Fundo
      </button>
      <button type="button" class="switch" aria-pressed={toggles.focus} onclick={() => toggle("focus")}>
        <span class="pill"></span>
        <Icon name="focus" size={18} /> Foco
      </button>
      <button type="button" class="switch" aria-pressed={toggles.paint} onclick={() => toggle("paint")}>
        <span class="pill"></span>
        <Icon name="mic" size={18} /> Pintar
      </button>
      <button type="button" class="switch" aria-pressed={toggles.score} onclick={() => toggle("score")}>
        <span class="pill"></span>
        <Icon name="score" size={18} /> Score
      </button>
    </div>
  </div>
</section>

<style>
  .card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 14px;
  }
  .player {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }
  .art {
    width: 100%;
    aspect-ratio: 1;
    border-radius: var(--radius);
    overflow: hidden;
    margin-bottom: 8px;
  }
  .art :global(.cover) {
    width: 100%;
    height: 100%;
  }
  .art.placeholder {
    display: grid;
    place-items: center;
    background: var(--panel-2);
    color: var(--dim);
  }
  .title {
    font-size: 21px;
    font-weight: 700;
    line-height: 1.25;
    text-align: center;
  }
  .artist {
    font-size: 15px;
    color: var(--muted);
    text-align: center;
  }

  .transport {
    display: flex;
    align-items: center;
    gap: 22px;
    margin-top: 10px;
  }
  .tbtn {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    border: 1px solid var(--line);
    background: var(--panel-2);
    color: var(--text);
    display: grid;
    place-items: center;
  }
  .tbtn:active {
    filter: brightness(1.2);
  }
  .tbtn.play {
    width: 68px;
    height: 68px;
    background: var(--accent);
    color: var(--accent-ink);
    border-color: var(--accent);
  }

  .seekrow {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    margin-top: 10px;
  }
  .time {
    font-size: 13px;
    color: var(--muted);
    font-variant-numeric: tabular-nums;
    min-width: 38px;
    text-align: center;
    flex: none;
  }

  .secthead {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    background: none;
    border: 0;
    padding: 4px 2px;
    min-height: 44px;
    font-size: 16px;
    font-weight: 700;
    color: var(--text);
  }
  .secthead.static {
    cursor: default;
  }
  .mixer {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding-top: 4px;
  }
  .dim {
    color: var(--dim);
    font-size: 14px;
    margin: 6px 2px;
  }

  .adjusts {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .arow {
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--panel-2);
    border-radius: var(--radius);
    padding: 6px 10px;
    min-height: 56px;
  }
  .albl {
    width: 70px;
    flex: none;
    font-size: 14px;
    font-weight: 600;
    color: var(--muted);
  }
  .stepper {
    flex: 1;
    display: grid;
      grid-template-columns: 44px minmax(72px, 1fr) 44px 44px;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }
  .sbtn {
    width: 100%;
    height: 44px;
    padding: 0 10px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    border: 1px solid var(--line);
    background: var(--panel);
    color: var(--text);
    font-size: 15px;
    font-weight: 700;
  }
  .sbtn.aa {
    font-size: 16px;
  }
  .sbtn.reset {
    padding: 0;
  }
  .val {
    min-width: 0;
    width: 100%;
    text-align: center;
    font-size: 15px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--text);
    background: none;
    border: 0;
    padding: 8px 2px;
  }
  .val.nonzero {
    color: var(--accent);
  }
  .btnval {
    cursor: pointer;
  }
  .toggles {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .toggles .switch {
    width: 100%;
    min-width: 0;
    justify-content: flex-start;
    padding-inline: 12px;
    white-space: nowrap;
  }

  @media (max-width: 380px) {
    .arow {
      gap: 8px;
      padding-inline: 8px;
    }
    .albl {
      width: 60px;
    }
    .stepper {
      grid-template-columns: 40px minmax(68px, 1fr) 40px 40px;
      gap: 4px;
    }
    .sbtn {
      padding-inline: 6px;
    }
    .toggles .switch {
      gap: 8px;
      padding-inline: 10px;
      font-size: 14px;
    }
  }
</style>
