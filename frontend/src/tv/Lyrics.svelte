<script>
  // A letra sincronizada — porte fiel do updateLyrics do legado.
  //
  // O markup é declarativo (Svelte escapa o texto), mas as atualizações por
  // quadro (classes .past/.past-2/.active/.next/.next-2/.next-3,
  // preenchimento --p, pintura
  // palavra-a-palavra) são imperativas sobre os nós — como no legado — para
  // não reconciliar o DOM a 60 fps.
  import { onMount } from "svelte";
  import { player } from "./player.js";
  import { lyr, lyrOffset, lyricScale, immersive, onTick, wokeByTouch, wordSync } from "./store.js";

  let box;
  let activeIdx = -2;
  let lastT = 0;

  // Mudanças que exigem recomputar a linha ativa (e recentralizar)
  $effect(() => {
    $lyr;
    $lyrOffset;
    $lyricScale;
    $immersive;
    $wordSync;
    activeIdx = -2;
  });

  // Centraliza a linha ativa usando posições reais (getBoundingClientRect),
  // independente do padding do container. Ligeiramente acima do centro (38%)
  // como no Apple Music, para dar respiro entre header e footer.
  function scrollToActive(els, i) {
    const el = els[Math.max(i, 0)];
    if (!el) return;
    const boxRect = box.getBoundingClientRect();
    const elRect = el.getBoundingClientRect();
    const currentCenter = elRect.top + elRect.height / 2 - boxRect.top;
    const desiredCenter = boxRect.height * 0.38;
    const top = box.scrollTop + currentCenter - desiredCenter;
    box.scrollTo({ top, behavior: "smooth" });
  }

  function updateLyrics(t) {
    const lines = $lyr.lines;
    if (!lines.length || !box) return;
    t += $lyrOffset;
    // Fim da música/seek para trás: recomputa do zero
    if (t < lastT - 1) activeIdx = -2;
    lastT = t;
    let i = -1;
    for (let k = 0; k < lines.length && lines[k].t <= t; k++) i = k;
    const els = box.children;
    if (i !== activeIdx) {
      for (let k = 0; k < els.length; k++) {
        const l = lines[k];
        if (!l) continue;
        const d = k - i;
        els[k].className =
          "line" +
          (l.gap ? " gap" : "") +
          ($wordSync && l.words ? " words" : "") +
          (l.duet ? ` duet-${l.duet}` : "") +
          (d < -1
            ? " past"
            : d === -1
              ? " past-2"
              : d === 0
                ? " active"
                : d === 1
                  ? " next"
                  : d === 2
                    ? " next-2"
                    : d === 3
                      ? " next-3"
                      : "");
      }
      scrollToActive(els, i);
      activeIdx = i;
    }
    if (i < 0 || !els[i]) return;
    const line = lines[i];

    // Pintura desligada: só destaca a linha ativa (branca, ampliada), sem preencher
    if (!$wordSync) return;

    if (line.words) {
      // Palavra por palavra: cada palavra é preenchida continuamente da esquerda
      // para a direita enquanto é cantada (--wp, 0–100%), acompanhando o tempo
      // da palavra — em vez de pintar a palavra inteira de uma vez.
      const spans = els[i].querySelectorAll(".w");
      line.words.forEach((w, k) => {
        const el = spans[k];
        if (!el) return;
        const dur = w.e - w.s;
        const p = dur > 0 ? Math.min(1, Math.max(0, (t - w.s) / dur)) : t >= w.s ? 1 : 0;
        el.style.setProperty("--wp", `${(p * 100).toFixed(1)}%`);
      });
      return;
    }

    // Só linhas: preenchimento avança enquanto há voz entre o início desta
    // linha e a próxima (atividade de voz; fallback linear sem voz detectável)
    const start = line.t,
      end = lines[i + 1]?.t ?? start + 6;
    const v = player.voice,
      a0 = start - $lyrOffset,
      a1 = end - $lyrOffset,
      a = t - $lyrOffset;
    const total = v ? v.at(a1) - v.at(a0) : 0;
    const p =
      v && total > 0.3 && !line.gap
        ? (v.at(a) - v.at(a0)) / total
        : (t - start) / Math.max(0.5, Math.min(end - start, 8) * 0.9);
    els[i].style.setProperty("--p", `${(Math.min(1, p) * 100).toFixed(1)}%`);
  }

  // Rolagem para o topo quando a letra muda (como o renderLyrics do legado)
  $effect(() => {
    $lyr;
    if (box) box.scrollTop = 0;
  });

  function onClick(e) {
    if (wokeByTouch.value) {
      wokeByTouch.value = false;
      return;
    } // toque só para mostrar os controles
    const el = e.target.closest(".line");
    if (el) player.seek($lyr.lines[+el.dataset.i].t - $lyrOffset);
  }

  onMount(() => onTick(updateLyrics));
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions (clique na letra = seek, como no legado) -->
<div class="lyrics" class:no-paint={!$wordSync} bind:this={box} onclick={onClick}>
  {#if $lyr.lines.length}
    {#each $lyr.lines as l, i (i)}
      <div class="line" class:gap={l.gap} class:words={$wordSync && l.words} data-i={i}>
        {#if $wordSync && l.words}
          {#each l.words as w, k (k)}{#if k > 0}{" "}{/if}<span class="w">{w.w}</span>{/each}
        {:else}
          {l.text}
        {/if}
      </div>
    {/each}
  {:else if $lyr.plain}
    <div class="plain">{$lyr.plain}</div>
    <p class="empty">Letra sem sincronização</p>
  {/if}
</div>
