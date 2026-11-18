(() => {
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  const grid = document.getElementById('preset-grid');
  const search = document.getElementById('theme-search');
  const effectFilter = document.getElementById('effect-filter');
  const resultCount = document.getElementById('result-count');
  const emptyState = document.getElementById('empty-state');
  const toast = document.getElementById('toast');
  const customColors = [...document.querySelectorAll('.custom-color')];
  const customBrightness = [...document.querySelectorAll('.custom-brightness')];
  const brightnessOutputs = [...document.querySelectorAll('.brightness-value')];
  const shadeControls = [...document.querySelectorAll('.color-control')];
  const shadeCountOutput = document.getElementById('shade-count');
  const addShadeButton = document.getElementById('add-shade');
  const removeShadeButton = document.getElementById('remove-shade');
  const speedRange = document.getElementById('speed-range');
  const labModeButtons = [...document.querySelectorAll('[data-lab-mode]')];
  const extremeNotice = document.getElementById('extreme-notice');
  const wildPaletteButton = document.getElementById('generate-wild-palette');
  const paletteSource = document.getElementById('palette-source');
  const paletteName = document.getElementById('palette-name');
  const loadPaletteButton = document.getElementById('load-palette-source');
  const savePaletteButton = document.getElementById('save-palette-new');
  const updatePaletteButton = document.getElementById('save-palette-changes');
  const deletePaletteButton = document.getElementById('delete-palette');
  const quitButton = document.getElementById('quit-studio');
  let presets = [];
  let savedPalettes = [];
  let activeFilter = 'All';
  let activeEffect = 'All';
  let extremeMode = false;
  let activeShadeCount = 5;
  let selectedPresetId = null;
  let toastTimer;
  let countdownTimer;
  let pendingZone = null;
  const observedZones = loadZoneObservations();

  function loadZoneObservations() {
    try {
      return JSON.parse(localStorage.getItem('alienfx-zone-observations-v1') || '{}');
    } catch (_) {
      return {};
    }
  }

  function showToast(message, isError = false) {
    toast.textContent = message;
    toast.classList.toggle('error', isError);
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 4200);
  }

  function swatch(hex) {
    const item = document.createElement('i');
    item.style.backgroundColor = hex;
    item.setAttribute('aria-label', hex);
    return item;
  }

  function previewDuration(speed) {
    const tempo = Math.max(25, Math.min(942, Number(speed) || 220));
    const duration = tempo < 30
      ? 0.65 + ((tempo - 25) / 5) * 0.15
      : tempo < 50
        ? 0.8 + ((tempo - 30) / 20) * 0.2
        : 1 + ((tempo - 50) / 892) * 3;
    return `${duration.toFixed(2)}s`;
  }

  function updatePaletteButtons() {
    const hasSource = Boolean(paletteSource.value);
    const hasSavedSource = paletteSource.value.startsWith('saved:');
    loadPaletteButton.disabled = !hasSource;
    updatePaletteButton.disabled = !hasSavedSource;
    deletePaletteButton.disabled = !hasSavedSource;
  }

  function setShadeCount(count) {
    activeShadeCount = Math.max(1, Math.min(customColors.length, Math.trunc(count)));
    shadeControls.forEach((control, index) => {
      control.hidden = index >= activeShadeCount;
      customColors[index].setAttribute('aria-label', `Color ${index + 1}`);
      customBrightness[index].setAttribute('aria-label', `Brightness for color ${index + 1}`);
    });
    shadeCountOutput.value = `${activeShadeCount} / ${customColors.length}`;
    removeShadeButton.disabled = activeShadeCount === 1;
    addShadeButton.disabled = activeShadeCount === customColors.length;
    updateCustomPreview();
  }

  function updateExtremeNotice() {
    if (!extremeMode) return;
    const tempo = Number(speedRange.value);
    const experimentalTempo = tempo < 50;
    extremeNotice.classList.toggle('warning', experimentalTempo);
    extremeNotice.textContent = tempo === 25
      ? 'Tempo 25 is the fastest setting available for now. Values below 50 are experimental.'
      : experimentalTempo
        ? `Tempo ${tempo} is below the trial-tested stable floor of 50 and may behave unpredictably.`
        : 'Extreme mode enables structured wild palettes and tempo down to 25. Values below 50 are experimental.';
  }

  function setLabMode(mode) {
    extremeMode = mode === 'extreme';
    document.body.classList.toggle('extreme-mode', extremeMode);
    const currentTempo = Number(speedRange.value);
    speedRange.min = extremeMode ? '25' : '50';
    if (!extremeMode && currentTempo < 50) speedRange.value = '50';
    labModeButtons.forEach(button => {
      const selected = button.dataset.labMode === mode;
      button.classList.toggle('selected', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
    wildPaletteButton.classList.toggle('hidden', !extremeMode);
    extremeNotice.classList.toggle('hidden', !extremeMode);
    document.getElementById('tempo-range-label').textContent = extremeMode
      ? '3-942 · lower is faster'
      : '50-942 · lower is faster';
    document.getElementById('speed-value').textContent = speedRange.value;
    updateExtremeNotice();
    updateCustomPreview();
  }

  function hslToHex(hue, saturation, lightness) {
    const chroma = (1 - Math.abs(2 * lightness - 1)) * saturation;
    const sector = hue / 60;
    const secondary = chroma * (1 - Math.abs((sector % 2) - 1));
    const rgb = sector < 1 ? [chroma, secondary, 0]
      : sector < 2 ? [secondary, chroma, 0]
        : sector < 3 ? [0, chroma, secondary]
          : sector < 4 ? [0, secondary, chroma]
            : sector < 5 ? [secondary, 0, chroma]
              : [chroma, 0, secondary];
    const offset = lightness - chroma / 2;
    return `#${rgb.map(channel => Math.round((channel + offset) * 255).toString(16).padStart(2, '0')).join('')}`;
  }

  function generateWildPalette() {
    const baseHue = Math.random() * 360;
    customColors.slice(0, activeShadeCount).forEach((input, index) => {
      const rawHue = baseHue + index * 137.508 + (Math.random() - 0.5) * 18;
      const hue = ((rawHue % 360) + 360) % 360;
      const saturation = 0.82 + Math.random() * 0.16;
      const lightness = index % 4 === 0
        ? 0.45 + Math.random() * 0.12
        : 0.52 + Math.random() * 0.13;
      input.value = hslToHex(hue, saturation, lightness);
      const brightness = Math.round(45 + Math.random() * 55);
      customBrightness[index].value = String(brightness);
      brightnessOutputs[index].value = `${brightness}%`;
    });
    paletteSource.value = '';
    paletteName.value = 'Wild mix';
    updatePaletteButtons();
    updateCustomPreview();
    showToast('Wild mix generated in preview. Apply only when you are ready.');
  }

  function populatePaletteSources(selectedValue = '') {
    paletteSource.replaceChildren(new Option('Choose a palette', ''));
    const baselines = document.createElement('optgroup');
    baselines.label = 'Curated color palettes';
    presets.filter(preset => !preset.name.includes(' / ')).forEach(preset => {
      baselines.append(new Option(preset.name, `baseline:${preset.id}`));
    });
    paletteSource.append(baselines);
    const saved = document.createElement('optgroup');
    saved.label = 'My palettes';
    savedPalettes.forEach(palette => saved.append(new Option(palette.name, `saved:${palette.id}`)));
    paletteSource.append(saved);
    paletteSource.value = selectedValue;
    updatePaletteButtons();
  }

  function expandPalette(colors, count) {
    if (count === 1) return [colors[0]];
    if (colors.length === 1) return Array(count).fill(colors[0]);
    return Array.from({ length: count }, (_, index) => {
      const position = index * (colors.length - 1) / (count - 1);
      const start = Math.floor(position);
      const end = Math.min(start + 1, colors.length - 1);
      const amount = position - start;
      const channels = [1, 3, 5].map(offset => {
        const from = parseInt(colors[start].slice(offset, offset + 2), 16);
        const to = parseInt(colors[end].slice(offset, offset + 2), 16);
        return Math.round(from + (to - from) * amount).toString(16).padStart(2, '0');
      });
      return `#${channels.join('')}`;
    });
  }

  function expandBrightness(values, count) {
    const levels = Array.isArray(values) && values.length ? values : [100];
    if (count === 1) return [levels[0]];
    if (levels.length === 1) return Array(count).fill(levels[0]);
    return Array.from({ length: count }, (_, index) => {
      const position = index * (levels.length - 1) / (count - 1);
      const start = Math.floor(position);
      const end = Math.min(start + 1, levels.length - 1);
      const amount = position - start;
      return Math.round(levels[start] + (levels[end] - levels[start]) * amount);
    });
  }

  function brightenHex(hex, brightness) {
    const factor = Math.max(0, Math.min(100, Number(brightness))) / 100;
    const channels = [1, 3, 5].map(offset => {
      const channel = parseInt(hex.slice(offset, offset + 2), 16);
      return Math.round(channel * factor).toString(16).padStart(2, '0');
    });
    return `#${channels.join('')}`;
  }

  function loadPaletteIntoLab(item, name = item.name) {
    if (item.speed < 50) setLabMode('extreme');
    const palette = item.palette.slice(0, customColors.length);
    setShadeCount(palette.length);
    expandPalette(palette, palette.length).forEach((color, index) => {
      customColors[index].value = color;
    });
    expandBrightness(item.brightness, palette.length).forEach((level, index) => {
      customBrightness[index].value = String(level);
      brightnessOutputs[index].value = `${level}%`;
    });
    paletteName.value = name;
    const legacyFallbacks = { strobe: 'breathe', glitch: 'polyphase' };
    const effectInput = [...document.querySelectorAll('.effect-option input')]
      .find(input => input.value === (legacyFallbacks[item.effect] || item.effect));
    if (effectInput) {
      effectInput.checked = true;
      document.querySelectorAll('.effect-option').forEach(option => {
        option.classList.toggle('selected', option.contains(effectInput));
      });
    }
    speedRange.value = item.speed;
    document.getElementById('speed-value').textContent = speedRange.value;
    updateExtremeNotice();
    updateCustomPreview();
    updatePaletteButtons();
  }

  function loadPaletteSource() {
    const [kind, id] = paletteSource.value.split(':', 2);
    const item = kind === 'baseline'
      ? presets.find(preset => preset.id === id)
      : savedPalettes.find(palette => palette.id === id);
    if (item) loadPaletteIntoLab(item);
  }

  function editPresetInColorLab(preset) {
    loadPaletteIntoLab(preset, `${preset.name} Copy`);
    paletteSource.value = '';
    updatePaletteButtons();
    document.querySelector('[data-view-target="create"]').click();
    showToast(`Editing a copy of ${preset.name}. Save it as a new palette.`);
  }

  function currentPaletteRecord() {
    return {
      name: paletteName.value.trim(),
      palette: customColors.slice(0, activeShadeCount).map(input => input.value),
      brightness: customBrightness.slice(0, activeShadeCount).map(input => Number(input.value)),
      effect: document.querySelector('.effect-option input:checked').value,
      speed: Number(speedRange.value),
    };
  }

  async function savePalette(method, id = '') {
    const record = currentPaletteRecord();
    if (!record.name) {
      showToast('Give this palette a name before saving.', true);
      paletteName.focus();
      return;
    }
    const url = id ? `/api/palettes/${encodeURIComponent(id)}` : '/api/palettes';
    try {
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify(record),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || 'Could not save palette.');
      savedPalettes = result.palettes;
      populatePaletteSources(`saved:${result.palette.id}`);
      showToast(`Saved “${result.palette.name}”.`);
    } catch (error) {
      showToast(error.message || 'Could not save palette.', true);
    }
  }

  function setActivePreview(card) {
    grid.querySelectorAll('.preset-card.preview-active').forEach(active => {
      if (active !== card) active.classList.remove('preview-active');
    });
    if (card) card.classList.add('preview-active');
  }

  function selectedPreviewCard() {
    return [...grid.children].find(card => card.dataset.presetId === selectedPresetId) || null;
  }

  function makeCard(preset) {
    const card = document.createElement('article');
    card.className = 'preset-card';
    card.dataset.effect = preset.effect;
    card.dataset.presetId = preset.id;
    card.style.setProperty('--motion-duration', previewDuration(preset.speed));
    if (preset.id === selectedPresetId) card.classList.add('preview-active');

    const art = document.createElement('div');
    art.className = 'preset-art';
    art.style.setProperty('--a', preset.palette[0]);
    art.style.setProperty('--b', preset.palette[1]);
    art.style.setProperty('--c', preset.palette[2]);
    const artOrbit = document.createElement('span');
    artOrbit.className = 'art-orbit';
    artOrbit.textContent = '✧';
    art.append(artOrbit);

    const meta = document.createElement('div');
    meta.className = 'preset-meta';
    const title = document.createElement('h3');
    title.textContent = preset.name;
    const effect = document.createElement('span');
    effect.className = 'effect-pill';
    effect.textContent = preset.effect.charAt(0).toUpperCase() + preset.effect.slice(1);
    meta.append(title, effect);

    const palette = document.createElement('div');
    palette.className = 'palette-row';
    palette.setAttribute('aria-label', 'Palette colors');
    preset.palette.forEach(color => palette.append(swatch(color)));

    const tags = document.createElement('div');
    tags.className = 'preset-tags';
    preset.tags.forEach(tag => {
      const label = document.createElement('span');
      label.textContent = tag;
      tags.append(label);
    });

    const apply = document.createElement('button');
    apply.className = 'apply-preset';
    apply.type = 'button';
    const applyText = document.createElement('span');
    applyText.textContent = 'Apply palette';
    const arrow = document.createElement('b');
    arrow.textContent = '↗';
    apply.append(applyText, arrow);
    apply.addEventListener('click', () => {
      selectedPresetId = preset.id;
      setActivePreview(card);
      applyTheme({ preset_id: preset.id }, apply);
    });

    const edit = document.createElement('button');
    edit.className = 'edit-preset';
    edit.type = 'button';
    edit.setAttribute('aria-label', `Edit ${preset.name} in Color Lab`);
    edit.title = 'Edit a copy in Color Lab';
    edit.textContent = '✎';
    edit.addEventListener('click', event => {
      event.stopPropagation();
      editPresetInColorLab(preset);
    });

    art.append(edit);
    card.append(art, meta, palette, tags, apply);
    return card;
  }

  function filterPresets() {
    const query = search.value.trim().toLowerCase();
    const filtered = presets.filter(preset => {
      const matchesFilter = activeFilter === 'All' || preset.tags.includes(activeFilter);
      const matchesEffect = activeEffect === 'All' || preset.effect === activeEffect;
      const matchesQuery = `${preset.name} ${preset.tags.join(' ')} ${preset.effect}`
        .toLowerCase().includes(query);
      return matchesFilter && matchesEffect && matchesQuery;
    });
    const cards = filtered.map(preset => makeCard(preset));
    grid.replaceChildren(...cards);
    setActivePreview(selectedPreviewCard());
    resultCount.textContent = String(filtered.length);
    emptyState.classList.toggle('hidden', filtered.length !== 0);
  }

  paletteSource.addEventListener('change', updatePaletteButtons);
  loadPaletteButton.addEventListener('click', loadPaletteSource);
  savePaletteButton.addEventListener('click', () => savePalette('POST'));
  updatePaletteButton.addEventListener('click', () => {
    const id = paletteSource.value.slice('saved:'.length);
    savePalette('PUT', id);
  });
  deletePaletteButton.addEventListener('click', async () => {
    const id = paletteSource.value.slice('saved:'.length);
    const selected = savedPalettes.find(palette => palette.id === id);
    if (!selected || !window.confirm(`Delete “${selected.name}”?`)) return;
    try {
      const response = await fetch(`/api/palettes/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: { 'X-CSRF-Token': csrfToken },
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || 'Could not delete palette.');
      savedPalettes = result.palettes;
      populatePaletteSources();
      paletteName.value = '';
      showToast(`Deleted “${selected.name}”.`);
    } catch (error) {
      showToast(error.message || 'Could not delete palette.', true);
    }
  });

  grid.addEventListener('pointerover', event => {
    if (event.pointerType === 'touch') return;
    const card = event.target.closest('.preset-card');
    if (card) setActivePreview(card);
  });
  grid.addEventListener('pointerout', event => {
    if (event.pointerType === 'touch') return;
    const card = event.target.closest('.preset-card');
    const nextCard = event.relatedTarget instanceof Element
      ? event.relatedTarget.closest('.preset-card') : null;
    if (card && card !== nextCard) {
      setActivePreview(nextCard || grid.querySelector('.preset-card:focus-within') || selectedPreviewCard());
    }
  });
  grid.addEventListener('focusin', event => {
    const card = event.target.closest('.preset-card');
    if (card) setActivePreview(card);
  });
  grid.addEventListener('focusout', event => {
    const card = event.target.closest('.preset-card');
    const nextCard = event.relatedTarget instanceof Element
      ? event.relatedTarget.closest('.preset-card') : null;
    if (card && card !== nextCard) {
      setActivePreview(nextCard || grid.querySelector('.preset-card:hover') || selectedPreviewCard());
    }
  });

  async function applyTheme(payload, button) {
    const status = await fetch('/api/status').then(response => response.json()).catch(() => null);
    if (!status || !status.connected) {
      showToast('No supported controller is connected. Nothing was written.', true);
      return;
    }
    if (button) {
      button.disabled = true;
      button.classList.add('working');
    }
    try {
      const response = await fetch('/api/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || 'Could not apply palette.');
      showToast(`${result.name} applied · ${result.effect} effect`);
      await refreshDiagnostics();
    } catch (error) {
      showToast(error.message || 'Could not reach AlienFX Studio.', true);
    } finally {
      if (button) {
        button.disabled = false;
        button.classList.remove('working');
      }
    }
  }

  function setDeviceStatus(status) {
    const dot = document.getElementById('connection-dot');
    const name = document.getElementById('device-name');
    const state = document.getElementById('device-state');
    const zones = document.getElementById('device-zones');
    dot.classList.toggle('connected', Boolean(status.connected));
    name.textContent = status.connected ? status.name : 'Controller not found';
    state.textContent = status.connected ? 'Connected · ready to glow' : 'Lighting preview is still available';
    zones.textContent = status.connected ? `${status.zones.length} mapped zones · ${status.zones.slice(0, 3).join(' / ')}` : 'Connect a supported AlienFX device';
  }

  function renderDiagnostics(data) {
    const select = document.getElementById('zone-select');
    const map = document.getElementById('zone-map');
    const testButton = document.getElementById('run-zone-test');
    const restoreButton = document.getElementById('restore-zone-test');
    const profileLabel = document.getElementById('restore-profile-label');
    const currentZone = data.test_zone || select.value;
    map.replaceChildren();
    select.replaceChildren();

    if (!data.connected) {
      select.add(new Option('No supported controller', ''));
      select.disabled = true;
      map.innerHTML = '<div class="zone-placeholder">No supported controller detected. No scan was run.</div>';
      profileLabel.textContent = 'Restore profile: unavailable';
      testButton.disabled = true;
      restoreButton.disabled = true;
      document.getElementById('probe-controller').disabled = true;
      document.getElementById('probe-result').textContent = 'No controller detected';
      document.getElementById('probe-detail').textContent = data.message;
      return;
    }

    const zones = data.controller.zones;
    const observationKey = `${data.controller.vendor_id}:${data.controller.product_id}`;
    document.getElementById('probe-result').textContent = `${data.controller.name} detected`;
    document.getElementById('probe-detail').textContent =
      `USB ${observationKey} · protocol rev ${data.controller.revision} · ${data.controller.packet_length}-byte packets · ${zones.length} mapped zones`;
    document.getElementById('probe-orb').classList.add('ready');
    zones.forEach((zone, index) => {
      const option = new Option(`${zone.name}${zone.power_zone ? ' · power state' : ''} (${zone.code})`, zone.name);
      select.add(option);
      const chip = document.createElement('div');
      chip.className = `zone-chip${zone.name === data.test_zone ? ' selected' : ''}`;
      const dot = document.createElement('span');
      dot.className = 'zone-chip-dot';
      dot.style.setProperty('--zone-color', ['#9c7aff', '#47dbdb', '#e969d2', '#b6eb55', '#ff9a61'][index % 5]);
      const name = document.createElement('span');
      name.className = 'zone-chip-name';
      name.textContent = zone.name;
      const code = document.createElement('code');
      code.textContent = zone.code;
      const observed = (observedZones[observationKey] || {})[zone.name];
      const result = document.createElement('span');
      result.className = `zone-result${observed ? ` ${observed}` : ''}`;
      result.textContent = observed === 'yes' ? 'LIT' : observed === 'no' ? 'NO' : '';
      chip.append(dot, name, code, result);
      map.append(chip);
    });
    if (zones.some(zone => zone.name === currentZone)) select.value = currentZone;
    select.disabled = data.test_active || zones.length === 0;
    const restorePending = data.restore_pending || data.restore_failed;
    profileLabel.textContent = restorePending
      ? 'Selected zone restore: pending'
      : data.profile_available ? 'Restore profile: ready' : 'Restore profile: required';
    profileLabel.style.color = restorePending ? '#ffc476' : data.profile_available ? '#79e6bc' : '#ffc476';
    testButton.disabled = !data.profile_available || data.test_active || restorePending || zones.length === 0;
    restoreButton.disabled = !restorePending && !data.profile_available;
    document.getElementById('probe-controller').disabled = data.test_active || restorePending;
    restoreButton.textContent = data.restore_failed ? 'Retry selected-zone restore'
      : restorePending ? 'Restore selected zone' : 'Reapply saved theme';
    testButton.querySelector('span').textContent = data.test_active
      ? `Testing ${data.test_zone || 'zone'}…`
      : 'Start 8-second test';
    if (data.test_active) startCountdown(data.restore_after_seconds || 8);
    else {
      stopCountdown();
      if (data.restore_pending) {
        const output = document.getElementById('test-countdown');
        output.textContent = 'Test window ended · selected zone stays changed until you restore it.';
        output.classList.remove('hidden');
      }
    }
    if (data.restore_failed) showToast('No automatic retry was sent. Restore the selected zone when ready.', true);
  }

  async function refreshDiagnostics() {
    try {
      const response = await fetch('/api/diagnostics');
      const data = await response.json();
      renderDiagnostics(data);
      return data;
    } catch (error) {
      showToast('Could not read diagnostics status.', true);
      return null;
    }
  }

  function startCountdown(seconds) {
    stopCountdown();
    let remaining = seconds;
    const output = document.getElementById('test-countdown');
    output.textContent = `Test window · ${remaining}s. Only this zone changes; restore is manual.`;
    output.classList.remove('hidden');
    countdownTimer = setInterval(() => {
      remaining -= 1;
      output.textContent = remaining > 0
        ? `Test window · ${remaining}s. Only this zone changes; restore is manual.`
        : 'Test window ended · selected zone stays changed until you restore it.';
      if (remaining <= 0) {
        stopCountdown();
        setTimeout(async () => {
          const state = await refreshDiagnostics();
          if (pendingZone && state && !state.restore_failed) showZoneFeedback(pendingZone);
        }, 350);
      }
    }, 1000);
  }

  function stopCountdown() {
    clearInterval(countdownTimer);
    countdownTimer = null;
    document.getElementById('test-countdown').classList.add('hidden');
  }

  function showZoneFeedback(zoneName) {
    document.getElementById('zone-feedback-question').textContent =
      `Did “${zoneName}” visibly illuminate during the temporary test?`;
    document.getElementById('zone-feedback').classList.remove('hidden');
  }

  async function diagnosticPost(endpoint, payload = {}) {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.error || result.message || 'Diagnostic request failed.');
    return result;
  }

  function updateCustomPreview() {
    const colors = customColors.slice(0, activeShadeCount).map(input => input.value);
    const brightness = customBrightness.slice(0, activeShadeCount).map(input => Number(input.value));
    const visibleColors = colors.map((color, index) => brightenHex(color, brightness[index]));
    const preview = document.getElementById('custom-preview');
    const middleColor = visibleColors[Math.floor((visibleColors.length - 1) / 2)];
    preview.dataset.effect = document.querySelector('.effect-option input:checked').value;
    preview.style.setProperty('--motion-duration', previewDuration(speedRange.value));
    preview.style.setProperty('--preview-a', `${visibleColors[0]}88`);
    preview.style.setProperty('--preview-b', `${middleColor}88`);
    preview.style.setProperty('--preview-c', visibleColors[visibleColors.length - 1]);
    preview.querySelectorAll('.keyboard-row i').forEach((key, index) => {
      const colorIndex = index % visibleColors.length;
      key.style.backgroundColor = visibleColors[colorIndex];
      key.style.boxShadow = `0 0 7px ${visibleColors[colorIndex]}`;
      key.style.opacity = String(brightness[colorIndex] / 100);
    });
    document.querySelector('.preview-device').style.boxShadow = `0 20px 35px #0008, 0 0 28px ${visibleColors[0]}40`;
  }

  search.addEventListener('input', filterPresets);
  quitButton.addEventListener('click', async () => {
    quitButton.disabled = true;
    try {
      const response = await fetch('/api/shutdown', {
        method: 'POST',
        headers: { 'X-CSRF-Token': csrfToken },
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || 'Could not stop AlienFX Studio.');
      showToast('AlienFX Studio is stopping. You can close this tab.');
    } catch (error) {
      quitButton.disabled = false;
      showToast(error.message || 'Could not stop AlienFX Studio.', true);
    }
  });
  labModeButtons.forEach(button => {
    button.addEventListener('click', () => setLabMode(button.dataset.labMode));
  });
  wildPaletteButton.addEventListener('click', generateWildPalette);
  addShadeButton.addEventListener('click', () => setShadeCount(activeShadeCount + 1));
  removeShadeButton.addEventListener('click', () => setShadeCount(activeShadeCount - 1));
  effectFilter.addEventListener('change', () => {
    activeEffect = effectFilter.value;
    filterPresets();
  });
  document.getElementById('filter-list').addEventListener('click', event => {
    const button = event.target.closest('[data-filter]');
    if (!button) return;
    activeFilter = button.dataset.filter;
    document.querySelectorAll('.filter-chip').forEach(chip => chip.classList.toggle('selected', chip === button));
    filterPresets();
  });

  document.querySelectorAll('[data-view-target]').forEach(button => {
    button.addEventListener('click', () => {
      const target = button.dataset.viewTarget;
      document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.dataset.view === target));
      document.querySelectorAll('.nav-item').forEach(nav => nav.classList.toggle('active', nav === button));
      document.getElementById('crumb-current').textContent = target.toUpperCase();
      window.scrollTo({ top: 0, behavior: 'smooth' });
      if (target === 'diagnostics') refreshDiagnostics();
    });
  });

  document.querySelectorAll('.effect-option input').forEach(input => {
    input.addEventListener('change', () => {
      document.querySelectorAll('.effect-option').forEach(option => option.classList.toggle('selected', option.contains(input) && input.checked));
      if (input.checked) {
        const defaults = {
          fixed: 75,
          morph: 75,
          breathe: 75,
          ripple: 75,
          spectrum: 75,
          aurora: 150,
          shimmer: 220,
          pulse: 300,
          blink: 220,
          comet: 50,
          orbit: 180,
          prism: 180,
          polyphase: 180,
        };
        speedRange.value = defaults[input.value] || 75;
        document.getElementById('speed-value').textContent = speedRange.value;
      }
      updateCustomPreview();
    });
  });

  speedRange.addEventListener('input', () => {
    document.getElementById('speed-value').textContent = speedRange.value;
    updateExtremeNotice();
    updateCustomPreview();
  });
  customColors.forEach(input => input.addEventListener('input', updateCustomPreview));
  customBrightness.forEach((input, index) => input.addEventListener('input', () => {
    brightnessOutputs[index].value = `${input.value}%`;
    updateCustomPreview();
  }));
  setShadeCount(activeShadeCount);

  document.getElementById('apply-custom').addEventListener('click', event => {
    const effect = document.querySelector('.effect-option input:checked').value;
    applyTheme({
      preset_id: 'custom',
      palette: customColors.slice(0, activeShadeCount).map(input => input.value),
      brightness: customBrightness.slice(0, activeShadeCount).map(input => Number(input.value)),
      effect,
      speed: Number(speedRange.value),
    }, event.currentTarget);
  });

  document.getElementById('probe-controller').addEventListener('click', async event => {
    const button = event.currentTarget;
    const result = document.getElementById('probe-result');
    const detail = document.getElementById('probe-detail');
    const orb = document.getElementById('probe-orb');
    button.disabled = true;
    result.textContent = 'Probing…';
    detail.textContent = 'Sending one read-only GET_STATUS request.';
    orb.classList.remove('ready', 'failed');
    try {
      const outcome = await diagnosticPost('/api/diagnostics/probe');
      result.textContent = outcome.status;
      detail.textContent = outcome.status_code
        ? `${outcome.detail} Response ${outcome.status_code} · ${outcome.response_length} bytes.`
        : outcome.detail;
      orb.classList.add(outcome.ready ? 'ready' : 'failed');
      showToast(
        outcome.ready ? 'Controller is ready.'
          : outcome.ok ? 'Controller responded but is busy; no lighting changes were sent.'
            : outcome.status,
        !outcome.ok,
      );
    } catch (error) {
      result.textContent = 'Probe failed';
      detail.textContent = error.message;
      orb.classList.add('failed');
      showToast(error.message, true);
    } finally {
      button.disabled = false;
    }
  });

  document.getElementById('run-zone-test').addEventListener('click', async event => {
    const button = event.currentTarget;
    button.disabled = true;
    pendingZone = document.getElementById('zone-select').value;
    document.getElementById('zone-feedback').classList.add('hidden');
    try {
      const result = await diagnosticPost('/api/diagnostics/zone-test', {
        zone: document.getElementById('zone-select').value,
        color: document.getElementById('zone-test-color').value,
      });
      showToast(`${result.zone} test started. Only this zone changed; restore is manual.`);
      await refreshDiagnostics();
    } catch (error) {
      showToast(error.message, true);
      await refreshDiagnostics();
    }
  });

  document.getElementById('restore-zone-test').addEventListener('click', async event => {
    event.currentTarget.disabled = true;
    try {
      const result = await diagnosticPost('/api/diagnostics/restore');
      showToast(result.message);
    } catch (error) {
      showToast(error.message, true);
    }
    const state = await refreshDiagnostics();
    if (pendingZone && state && !state.restore_failed) showZoneFeedback(pendingZone);
  });

  document.getElementById('zone-feedback').addEventListener('click', event => {
    const answer = event.target.closest('[data-zone-result]');
    if (!answer || !pendingZone) return;
    const key = document.getElementById('probe-detail').textContent.match(/USB ([0-9a-f]{4}:[0-9a-f]{4})/i)?.[1];
    if (key) {
      observedZones[key] = observedZones[key] || {};
      observedZones[key][pendingZone] = answer.dataset.zoneResult;
      try { localStorage.setItem('alienfx-zone-observations-v1', JSON.stringify(observedZones)); } catch (_) {}
    }
    document.querySelectorAll('.zone-chip').forEach(chip => {
      if (chip.querySelector('.zone-chip-name')?.textContent !== pendingZone) return;
      const result = chip.querySelector('.zone-result');
      result.className = `zone-result ${answer.dataset.zoneResult}`;
      result.textContent = answer.dataset.zoneResult === 'yes' ? 'LIT' : 'NO';
    });
    document.getElementById('zone-feedback').classList.add('hidden');
    showToast(answer.dataset.zoneResult === 'yes' ? `${pendingZone} confirmed working.` : `${pendingZone} marked as unresponsive.`);
    pendingZone = null;
  });

  document.addEventListener('keydown', event => {
    if (event.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
      event.preventDefault();
      search.focus();
    }
    if (event.key === 'Escape' && document.activeElement === search) search.blur();
  });

  Promise.all([
    fetch('/api/status').then(response => response.json()),
    fetch('/api/themes').then(response => response.json()),
    fetch('/api/diagnostics').then(response => response.json()),
    fetch('/api/palettes').then(response => response.json()),
  ]).then(([status, catalog, diagnostics, library]) => {
    setDeviceStatus(status);
    renderDiagnostics(diagnostics);
    presets = catalog;
    savedPalettes = library;
    populatePaletteSources();
    document.querySelector('.nav-count').textContent = String(presets.length);
    document.getElementById('result-count').textContent = String(presets.length);
    document.querySelector('.hero-stats strong').textContent = String(presets.length);
    document.querySelector('[data-filter="All"] span').textContent = String(presets.length);
    filterPresets();
  }).catch(() => {
    showToast('Studio could not load its palette catalog.', true);
  });
})();
