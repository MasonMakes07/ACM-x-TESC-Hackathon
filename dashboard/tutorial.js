export default function(component) {
  const {data} = component;
  // Keep position through widget reruns, without sending tutorial clicks to Python.
  // A view change can remount the component, so retain this page's singleton
  // tour state outside its DOM host. A full page reload starts a fresh session.
  const previous = window.__earthwatchTour;
  if (previous) previous.cleanup();
  if (!data.run) return;
  if (previous?.closed && previous.run === data.run) return;
  const identity = `${data.run}:${data.view}`;
  const state = previous && previous.identity === identity
    ? previous : {identity, run: data.run, index: 0, closed: false};
  window.__earthwatchTour = state;
  if (state.closed) return;

  const root = document.createElement('div');
  root.setAttribute('data-earthwatch-tutorial', '');
  // App-level overlay is intentional: a tour must point outside its component.
  root.innerHTML = `
    <style>
      .ew-tour-card {position:fixed;z-index:2147483647;box-sizing:border-box;width:min(370px,calc(100vw - 32px));
        padding:20px;background:#fffdf7;color:#29392d;border:1px solid #8c9b78;
        border-radius:16px;box-shadow:0 12px 48px #0008;font:15px/1.55 system-ui;}
      .ew-tour-card h2 {font:600 21px/1.3 system-ui;margin:6px 0 12px;color:inherit;}
      .ew-tour-card p {margin:0 0 12px;}
      .ew-tour-card small {color:#65705f;}
      .ew-tour-actions {display:flex;gap:10px;margin-top:16px;align-items:center;}
      .ew-tour-card button {border:1px solid #a8ae99;border-radius:8px;background:transparent;
        color:inherit;padding:8px 12px;cursor:pointer;font:inherit;}
      .ew-tour-card button:focus-visible {outline:3px solid #304a35;outline-offset:3px;}
      .ew-tour-card button:disabled {opacity:.45;cursor:default;}
      .ew-tour-card [data-next] {background:#dce5ce;color:#304a35;margin-left:auto;}
      .ew-tour-ring {position:fixed;z-index:2147483645;box-sizing:border-box;border:3px solid #52734a;
        border-radius:10px;box-shadow:0 0 0 5px #52734a33;pointer-events:none;}
      .ew-tour-pointer {position:fixed;z-index:2147483646;pointer-events:none;
        color:#dce5ce;filter:drop-shadow(0 2px 3px #000);transition:left .65s ease,top .65s ease;}
      @media(prefers-reduced-motion:reduce) {.ew-tour-pointer {transition:none;}}
    </style>
    <div class="ew-tour-ring" aria-hidden="true"></div>
    <svg class="ew-tour-pointer" aria-hidden="true" width="32" height="38" viewBox="0 0 32 38">
      <path d="M2 2 L3 30 L11 23 L18 36 L24 33 L17 21 L29 20 Z" fill="currentColor" stroke="#304a35" stroke-width="2"/>
    </svg>
    <section class="ew-tour-card" role="region" aria-label="EarthWatch guided tutorial">
      <small data-progress></small><div aria-live="polite" aria-atomic="true">
      <h2 tabindex="-1"></h2><p data-description></p><small data-unavailable></small></div>
      <div class="ew-tour-actions"><button data-exit>Exit</button><button data-back>Back</button><button data-next>Next</button></div>
    </section>`;
  document.body.appendChild(root);
  const card = root.querySelector('.ew-tour-card');
  const ring = root.querySelector('.ew-tour-ring');
  const pointer = root.querySelector('.ew-tour-pointer');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const returnFocus = document.activeElement;
  let target = null;
  let timer;
  let frame;
  let stopped = false;
  const visible = el => el && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
  const text = el => el.textContent.trim();
  function findTarget(step) {
    if (step.expander) return [...document.querySelectorAll('[data-testid="stExpander"] summary')].find(el => text(el) === step.expander || el.querySelector('p')?.textContent.trim() === step.expander);
    if (step.tab) return [...document.querySelectorAll('[role="tab"]')].find(el => text(el) === step.tab);
    if (step.button) return [...document.querySelectorAll('button')].find(el => !root.contains(el) && (text(el) === step.button || el.querySelector('p')?.textContent.trim() === step.button) && visible(el));
    if (step.label) {
      const label = [...document.querySelectorAll('[data-testid="stWidgetLabel"]')].find(el => text(el) === step.label);
      return label?.closest('[data-testid="stElementContainer"]') || label;
    }
    return [...document.querySelectorAll(step.selector || 'h1')].find(visible);
  }
  function position() {
    if (stopped) return;
    const rect = visible(target) ? target.getBoundingClientRect() : null;
    ring.hidden = pointer.hidden = !rect;
    if (rect) {
      Object.assign(ring.style, {left:`${rect.left-5}px`, top:`${rect.top-5}px`, width:`${rect.width+10}px`, height:`${rect.height+10}px`});
      pointer.style.left = `${Math.max(4, Math.min(innerWidth-36, rect.left + Math.min(rect.width/2, 100)))}px`;
      pointer.style.top = `${Math.max(4, Math.min(innerHeight-40, rect.top + rect.height/2))}px`;
    }
    // Place the explanation on the opposite side of the highlighted control.
    const left = rect && rect.left > innerWidth/2;
    card.style.left = left ? '16px' : 'auto';
    card.style.right = left ? 'auto' : '16px';
    card.style.bottom = '16px';
    card.style.maxHeight = 'calc(100dvh - 32px)';
    card.style.overflowY = 'auto';
    if (rect && rect.right > 16 && rect.left < innerWidth-16) {
      const panel = card.getBoundingClientRect();
      if (rect.bottom > panel.top && rect.top < panel.bottom && rect.right > panel.left && rect.left < panel.right) {
        card.style.bottom = 'auto'; card.style.top = '16px';
      } else card.style.top = 'auto';
    } else card.style.top = 'auto';
  }
  function render(focus = true) {
    const step = data.steps[state.index];
    root.querySelector('[data-progress]').textContent = `Step ${state.index+1} of ${data.steps.length} · ${data.view}`;
    root.querySelector('h2').textContent = step.title;
    root.querySelector('[data-description]').textContent = step.text;
    root.querySelector('[data-back]').disabled = state.index === 0;
    root.querySelector('[data-next]').textContent = state.index === data.steps.length-1 ? 'Finish' : 'Next';
    target = findTarget(step);
    // Optional settings are grouped in expanders; reveal them before pointing.
    let details = target?.closest('details');
    while (details) {
      if (!details.open) details.querySelector('summary')?.click();
      details = details.parentElement?.closest('details');
    }
    if (target?.closest('[data-testid="stSidebar"]')) {
      const expand = document.querySelector('[data-testid="stExpandSidebarButton"] button');
      if (expand && visible(expand)) expand.click();
    }
    if (step.tab && target && target.getAttribute('aria-selected') !== 'true') target.click();
    if (visible(target)) target.scrollIntoView({behavior:reducedMotion ? 'instant' : 'smooth', block:'center', inline:'nearest'});
    root.querySelector('[data-unavailable]').textContent = visible(target) ? 'Follow the pointer, or click Next to keep learning.' : 'This section appears when its prerequisites are available. You can continue with Next.';
    if (focus) root.querySelector('h2').focus({preventScroll:true});
    position();
  }
  function close() {
    state.closed = true;
    state.cleanup();
    const start = document.querySelector('.st-key-start_tutorial button');
    if (start) start.focus({preventScroll:true});
    else if (returnFocus?.isConnected) returnFocus.focus({preventScroll:true});
  }
  function next() {
    if (state.index === data.steps.length-1) close();
    else {state.index++; render();}
  }
  root.querySelector('[data-next]').onclick = next;
  root.querySelector('[data-back]').onclick = () => {state.index = Math.max(0,state.index-1); render();};
  root.querySelector('[data-exit]').onclick = close;
  function keydown(e) {
    if (e.key === 'Escape') {e.preventDefault(); close();}
    if (root.contains(e.target) && e.key === 'ArrowRight') {e.preventDefault(); next();}
    if (root.contains(e.target) && e.key === 'ArrowLeft') {e.preventDefault(); state.index=Math.max(0,state.index-1); render();}
  }
  document.addEventListener('keydown', keydown);
  window.addEventListener('resize', position);
  document.addEventListener('scroll', position, true);
  // Reacquire targets after Streamlit updates widgets or loads conditional sections.
  timer = setInterval(() => {
    const found = findTarget(data.steps[state.index]);
    if (found !== target) render(false);
    else position();
  }, 250);
  state.cleanup = () => {
    stopped = true;
    clearInterval(timer);
    cancelAnimationFrame(frame);
    document.removeEventListener('keydown', keydown);
    window.removeEventListener('resize', position);
    document.removeEventListener('scroll', position, true);
    root.remove();
  };
  frame = requestAnimationFrame(() => render());
  return state.cleanup;
}
