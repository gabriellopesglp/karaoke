<script>
  // Barra de ferramentas do palco: grupos Letra / Tom / Tamanho e os toggles
  // Fundo / Foco / Pintar. (Tooltips do offset corrigidos: 0,05 s — no legado
  // diziam "0,25 s" por engano.)
  import Icon from "../shared/Icon.svelte";
  import { fmtOffset } from "../shared/fmt.js";
  import { shiftedKey } from "./keydetect.js";
  import {
    currentSong,
    darkenBg,
    focusMode,
    lyricScale,
    lyricsOpen,
    lyrOffset,
    nudge,
    origKey,
    pitch,
    resetOffset,
    scoreEnabled,
    setLyricScale,
    setPitch,
    toggleDarkenBg,
    toggleFocusMode,
    toggleScore,
    toggleWordSync,
    wordSync,
  } from "./store.js";

  // Rótulo do tom: "F#m → Gm" com a detecção; "+2"/"0" sem ela
  const keyView = $derived.by(() => {
    const p = $pitch;
    const orig = $origKey;
    if (orig) {
      const suffix = orig.mode === "minor" ? "m" : "";
      const cur = p !== 0 ? shiftedKey(orig, p) : null;
      return {
        orig: orig.name + suffix,
        origTitle: orig.fullName + " (original)",
        now: cur ? cur.name + suffix : null,
        nowTitle: cur ? cur.fullName + " (atual)" : null,
      };
    }
    return { orig: p > 0 ? `+${p}` : `${p}`, origTitle: "Deslocamento em semitons", now: null };
  });
</script>

<div class="tools">
  <span class="grp">
    Letra
    <button title="Letra adiantada: atrasar 0,05 s" aria-label="Atrasar a letra" onclick={() => nudge(-0.05)}>
      <Icon name="minus" size={14} />
    </button>
    <span
      class="offset"
      class:nonzero={$lyrOffset !== 0}
      title="Clique para zerar"
      role="button"
      tabindex="0"
      onclick={resetOffset}
      onkeydown={(e) => e.key === "Enter" && resetOffset()}
    >
      {fmtOffset($lyrOffset)}
    </span>
    <button title="Letra atrasada: adiantar 0,05 s" aria-label="Adiantar a letra" onclick={() => nudge(0.05)}>
      <Icon name="plus" size={14} />
    </button>
    <button title="Zerar o ajuste da letra" aria-label="Zerar ajuste da letra" onclick={resetOffset}>
      <Icon name="refresh" size={14} />
    </button>
    <button
      title="Escolher outra versão da letra"
      aria-label="Escolher letra"
      disabled={!$currentSong}
      onclick={() => lyricsOpen.set(true)}
    >
      <Icon name="lyrics" size={14} /><span class="txt">Escolher</span>
    </button>
  </span>
  <span class="grp">
    Tom
    <button
      title="Abaixar o tom (1 semitom)"
      aria-label="Abaixar o tom"
      disabled={$pitch <= -12}
      onclick={() => setPitch($pitch - 1)}
    >
      <Icon name="minus" size={14} />
    </button>
    <span class="offset" class:nonzero={$pitch !== 0} title="Tom original e atual">
      <span title={keyView.origTitle}>{keyView.orig}</span>{#if keyView.now}
        <span>→</span><span title={keyView.nowTitle}>{keyView.now}</span>
      {/if}
    </span>
    <button
      title="Subir o tom (1 semitom)"
      aria-label="Subir o tom"
      disabled={$pitch >= 12}
      onclick={() => setPitch($pitch + 1)}
    >
      <Icon name="plus" size={14} />
    </button>
    <button title="Voltar ao tom original" onclick={() => setPitch(0)}>Normal</button>
  </span>
  <span class="grp">
    Tamanho
    <button
      class="aa"
      title="Diminuir a letra (-)"
      aria-label="Diminuir a letra"
      disabled={$lyricScale <= 0.6}
      onclick={() => setLyricScale($lyricScale - 0.1)}
    >
      A<small>−</small>
    </button>
    <span class="offset">{Math.round($lyricScale * 100)}%</span>
    <button
      class="aa"
      title="Aumentar a letra (=)"
      aria-label="Aumentar a letra"
      disabled={$lyricScale >= 2}
      onclick={() => setLyricScale($lyricScale + 0.1)}
    >
      A<small>+</small>
    </button>
    <button title="Voltar ao tamanho normal (0)" onclick={() => setLyricScale(1)}>Normal</button>
  </span>
  <span class="grp">
    <button
      title="Escurecer o fundo da capa para melhorar a leitura"
      aria-label="Escurecer o fundo"
      aria-pressed={$darkenBg}
      onclick={toggleDarkenBg}
    >
      <Icon name="moon" size={14} /><span class="txt">Fundo</span>
    </button>
    <button
      title="Modo foco: mostra só a linha atual e a próxima, com fonte gigante (estilo bar de karaokê)"
      aria-label="Modo foco"
      aria-pressed={$focusMode}
      onclick={toggleFocusMode}
    >
      <Icon name="focus" size={14} /><span class="txt">Foco</span>
    </button>
    <button
      title="Pintar palavra por palavra conforme são cantadas. Desligue para só destacar a linha inteira."
      aria-label="Pintar palavras"
      aria-pressed={$wordSync}
      onclick={toggleWordSync}
    >
      <Icon name="mic" size={14} /><span class="txt">Pintar</span>
    </button>
    <button
      title="Ativar overlay de precisão de afinação e score"
      aria-label="Score de afinação"
      aria-pressed={$scoreEnabled}
      onclick={toggleScore}
    >
      <Icon name="score" size={14} /><span class="txt">Score</span>
    </button>
  </span>
</div>
