<script>
  // Menu de configurações: motor de separação e chave do MVSep.
  import { onMount } from "svelte";
  import Icon from "../shared/Icon.svelte";
  import { apiJson, postJson } from "../shared/api.js";
  import { scoreEnabled, settingsOpen } from "./store.js";

  let cfg = {
    separation: "cpu",
    mvsep_api_key: "",
    mvsep_endpoint: "https://mvsep.com/api/separate",
    score_enabled: false,
  };
  let gpu = { available: false, device: "cpu" };
  let saving = false;
  let error = "";
  let success = "";

  onMount(async () => {
    try {
      const [loaded, gpuInfo] = await Promise.all([
        apiJson("/api/settings"),
        apiJson("/api/settings/gpu"),
      ]);
      cfg = { ...cfg, ...loaded };
      gpu = gpuInfo;
    } catch (e) {
      error = "Não foi possível carregar as configurações.";
    }
  });

  async function save() {
    saving = true;
    error = "";
    success = "";
    try {
      const updated = await postJson("/api/settings", {
        separation: cfg.separation,
        mvsep_api_key: cfg.mvsep_api_key,
        mvsep_endpoint: cfg.mvsep_endpoint,
        score_enabled: cfg.score_enabled,
      });
      cfg = { ...cfg, ...updated };
      scoreEnabled.set(updated.score_enabled === true);
      success = "Configurações salvas.";
      setTimeout(() => (success = ""), 2000);
    } catch (e) {
      error = "Erro ao salvar.";
    } finally {
      saving = false;
    }
  }

  function close() {
    settingsOpen.set(false);
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="modal" onclick={(e) => e.target === e.currentTarget && close()}>
  <div class="box">
    <div class="head">
      <h2><Icon name="settings" size={20} /> Configurações</h2>
      <button class="close" aria-label="Fechar" onclick={close}><Icon name="x" size={18} /></button>
    </div>

    <div class="section">
      <h3>Motor de separação das faixas</h3>
      <label class="radio">
        <input type="radio" bind:group={cfg.separation} value="cpu" />
        <span>CPU</span>
        <small>Sempre funciona; mais lento.</small>
      </label>
      <label class="radio" class:disabled={!gpu.available}>
        <input type="radio" bind:group={cfg.separation} value="gpu" disabled={!gpu.available} />
        <span>GPU</span>
        <small>
          {#if gpu.available}
            Detectado: {gpu.device === "mps" ? "Apple Silicon (MPS)" : gpu.device === "cuda" ? "NVIDIA (CUDA)" : gpu.device}.
          {:else}
            Nenhuma GPU compatível detectada.
          {/if}
        </small>
      </label>
      <label class="radio">
        <input type="radio" bind:group={cfg.separation} value="mvsep" />
        <span>MVSep</span>
        <small>Online. Requer chave de API.</small>
      </label>

      {#if cfg.separation === "mvsep"}
        <div class="field">
          <label for="mvsep-key">Chave de API do MVSep</label>
          <input id="mvsep-key" type="password" bind:value={cfg.mvsep_api_key} placeholder="cole aqui" />
        </div>
        <div class="field">
          <label for="mvsep-url">Endpoint (opcional)</label>
          <input id="mvsep-url" type="text" bind:value={cfg.mvsep_endpoint} />
        </div>
      {/if}
    </div>

    <div class="section">
      <h3>Pontuação / precisão</h3>
      <label class="switch">
        <input type="checkbox" bind:checked={cfg.score_enabled} />
        <span class="knob"></span>
        <span class="lbl">Ativar pontuação (score)</span>
      </label>
      <p class="hint">Quando ligado, o app usa o microfone para comparar sua voz com a melodia da música original e mostra a pontuação de 0 a 100 no fim de cada música. Só conta o que você canta (silêncio não derruba a nota), quase-acertos somam parcialmente e cantar a melodia em outra oitava vale igual.</p>
    </div>

    {#if error}<p class="error">{error}</p>{/if}
    {#if success}<p class="success">{success}</p>{/if}

    <div class="foot">
      <button class="ghost" onclick={close}>Fechar</button>
      <button class="primary" onclick={save} disabled={saving}>
        {saving ? "Salvando..." : "Salvar"}
      </button>
    </div>
  </div>
</div>

<style>
  .modal {
    position: fixed;
    inset: 0;
    z-index: 100;
    background: rgba(0, 0, 0, 0.75);
    display: grid;
    place-items: center;
    padding: 20px;
  }
  .box {
    width: min(480px, 100%);
    max-height: 90vh;
    overflow-y: auto;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 22px;
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 18px;
  }
  h2 {
    margin: 0;
    font-size: 20px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  h3 {
    margin: 0 0 12px;
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--muted);
  }
  .section {
    margin-bottom: 22px;
  }
  .radio {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 4px 10px;
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid var(--line);
    background: var(--panel-2);
    margin-bottom: 8px;
    cursor: pointer;
  }
  .radio.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .radio input {
    grid-row: span 2;
    align-self: center;
  }
  .radio span {
    font-weight: 600;
  }
  .radio small {
    color: var(--muted);
    font-size: 12px;
  }
  .field {
    margin-top: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .field label {
    font-size: 13px;
    color: var(--muted);
  }
  .field input {
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid var(--line);
    background: #0e0f15;
    color: var(--text);
    font-size: 14px;
  }
  .hint {
    font-size: 12px;
    color: var(--muted);
    margin: 8px 0 0;
    line-height: 1.4;
  }
  .switch {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
  }
  .switch input {
    display: none;
  }
  .knob {
    width: 44px;
    height: 24px;
    border-radius: 999px;
    background: var(--line);
    position: relative;
    transition: background 0.2s;
  }
  .knob::after {
    content: "";
    position: absolute;
    top: 2px;
    left: 2px;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #fff;
    transition: transform 0.2s;
  }
  .switch input:checked + .knob {
    background: var(--accent);
  }
  .switch input:checked + .knob::after {
    transform: translateX(20px);
  }
  .lbl {
    font-weight: 600;
  }
  .error { color: var(--error); margin: 8px 0 0; }
  .success { color: var(--ok); margin: 8px 0 0; }
  .foot {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 8px;
  }
  .close {
    background: transparent;
    border: 0;
    color: var(--text);
    cursor: pointer;
    padding: 4px;
  }
</style>
