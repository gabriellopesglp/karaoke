<script>
  // Pontuação da música: nada é exibido durante o canto — o resultado (0–100)
  // aparece no meio da tela quando a faixa termina.
  // Só é montado quando o Score está ligado (ver App.svelte).
  import { onDestroy, onMount } from "svelte";
  import Icon from "../shared/Icon.svelte";
  import { score, startScore, stopScore } from "./score.js";
  import { currentSong, ready } from "./store.js";

  onDestroy(stopScore);

  // Abre o microfone assim que houver uma música carregada. Se o Score for
  // ligado antes de tocar algo, tenta de novo quando a música ficar pronta.
  let startedFor = null;
  $effect(() => {
    const song = $currentSong;
    if (!$ready || !song || startedFor === song.folder) return;
    startedFor = song.folder;
    startScore(); // no-op quando a sessão já está aberta
  });

  let stageStyle = $state("");
  function syncStageRect() {
    const el = document.querySelector("main");
    if (!el) {
      stageStyle = "";
      return;
    }
    const r = el.getBoundingClientRect();
    stageStyle = `left:${r.left}px;top:${r.top}px;width:${r.width}px;height:${r.height}px;`;
  }

  $effect(() => {
    if ($score.final) syncStageRect();
  });

  onMount(() => {
    syncStageRect();
    const onResize = () => syncStageRect();
    window.addEventListener("resize", onResize);
    document.addEventListener("fullscreenchange", onResize);
    document.addEventListener("webkitfullscreenchange", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      document.removeEventListener("fullscreenchange", onResize);
      document.removeEventListener("webkitfullscreenchange", onResize);
    };
  });
</script>

{#if $score.error || $score.hint}
  <div class="tip" class:err={!!$score.error}>
    <span class="k"><Icon name="mic" size={14} /> Score</span>
    <p>{$score.error || $score.hint}</p>
  </div>
{:else if $score.final}
  <div class="wrap" style={stageStyle}>
    <div class="card">
      <span class="k"><Icon name="mic" size={14} /> Score</span>
      {#if $score.points == null}
        <p class="sub">Nenhuma voz captada nesta música.</p>
      {:else}
        <div class="big" class:good={$score.points >= 75}>{$score.points}</div>
        <p class="sub">pontos · {$score.total} leituras de voz</p>
      {/if}
    </div>
  </div>
{/if}

<style>
  .wrap {
    position: fixed;
    inset: auto;
    z-index: 40;
    display: grid;
    place-items: center;
    pointer-events: none;
    background: rgba(6, 6, 6, 0.28);
    overflow: hidden;
    animation: kscore-fade 0.4s ease;
  }
  @keyframes kscore-fade {
    from {
      opacity: 0;
    }
  }
  .card,
  .tip {
    padding: 22px 30px;
    border-radius: 20px;
    background: rgba(18, 18, 18, 0.62);
    border: 1px solid rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(24px) saturate(150%);
    -webkit-backdrop-filter: blur(24px) saturate(150%);
    font-variant-numeric: tabular-nums;
    text-align: center;
    animation: kscore-in 0.35s cubic-bezier(0.22, 1, 0.36, 1);
  }
  @keyframes kscore-in {
    from {
      opacity: 0;
      transform: scale(0.94);
    }
  }
  .tip {
    position: fixed;
    top: 96px;
    right: 32px;
    width: 244px;
    padding: 14px 16px;
    text-align: left;
    pointer-events: none;
  }
  .k {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .big {
    margin-top: 2px;
    font-size: 84px;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.04em;
    color: var(--text);
  }
  .big.good {
    color: var(--accent);
  }
  .sub {
    margin: 8px 0 0;
    font-size: 13px;
    color: var(--muted);
  }
  .tip p {
    margin: 8px 0 0;
    font-size: 12px;
    line-height: 1.45;
    color: var(--muted);
  }
  .tip.err p {
    color: var(--err);
  }
</style>
