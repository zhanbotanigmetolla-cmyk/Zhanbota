/* Turnikmen Mini App. No dependencies; live data comes only from the authenticated API. */
(() => {
  'use strict';
  const tg = window.Telegram?.WebApp;
  const initData = tg?.initData || '';
  const launchParams = new URLSearchParams(location.hash.replace(/^#/, ''));
  const queryParams = new URLSearchParams(location.search);
  const telegramLaunch = ['tgWebAppData', 'tgWebAppPlatform', 'tgWebAppVersion'].some(key => launchParams.has(key) || queryParams.has(key));
  const demo = !initData && !telegramLaunch;
  const app = document.querySelector('#app');
  const modal = document.querySelector('#modal');
  const nav = document.querySelector('#navigation');
  const ui = { tab: 'today', selected: 'pullups', progressTab: 'personal', historyLimit: 8, filter: '', session: null, receipt: null, rpe: 6, busy: false, restSeconds: 75, error: '', modal: '', theme: null };
  let state = null;
  let lastFocus = null;
  let toastTimer;
  ui.draft = null;
  ui.storageWarning = false;
  const labels = {
    pullups: ['Подтягивания', 'Pull-ups'], pushups: ['Отжимания', 'Push-ups'], dips: ['Брусья', 'Dips'], squats: ['Приседания', 'Squats'],
    pullups_weighted: ['Подтягивания + вес', 'Weighted pull-ups'], dips_weighted: ['Брусья + вес', 'Weighted dips'], rest: ['Восстановление', 'Recovery'],
  };
  const weights = { pullups: 1, pushups: .5, dips: .75, squats: .25, pullups_weighted: 1, dips_weighted: .75 };
  const lang = () => state?.language || 'ru';
  const tr = (ru, en) => lang() === 'en' ? en : ru;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  const number = value => Number.isFinite(Number(value)) ? Number(value) : 0;
  const fmt = value => new Intl.NumberFormat(lang() === 'en' ? 'en-US' : 'ru-RU').format(number(value));
  const pct = (value, max) => Math.max(0, Math.min(100, max > 0 ? value / max * 100 : 0));
  const sum = values => values.reduce((total, value) => total + number(value), 0);
  const nameOf = id => labels[id]?.[lang() === 'en' ? 1 : 0] || id;
  const dayLabel = value => lang() === 'en' ? ({ 'Средний': 'Moderate', 'Средний день': 'Moderate day', 'Лёгкий': 'Light', 'Тяжёлый': 'Heavy', 'Плотность': 'Density', 'Отдых': 'Rest' }[value] || value) : value;
  const telegramAtLeast = version => !demo && Boolean(tg?.isVersionAtLeast?.(version));
  const dateFrom = value => new Date(`${value}T12:00:00`);
  const dateText = (value, options = { day: 'numeric', month: 'short' }) => dateFrom(value).toLocaleDateString(lang() === 'en' ? 'en-GB' : 'ru-RU', options);
  const keyDate = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  const dayShift = (key, delta) => { const d = dateFrom(key); d.setDate(d.getDate() + delta); return keyDate(d); };
  const uid = () => typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => { const n = crypto.getRandomValues(new Uint8Array(1))[0] & 15; return (c === 'x' ? n : (n & 3) | 8).toString(16); });
  const getExercise = () => state?.exercises?.find(ex => ex.id === ui.selected) || state?.exercises?.[0];
  const icon = (name, cls = '') => {
    const paths = {
      home: '<path d="m3 10 9-7 9 7v10H3Z"/><path d="M9 20v-7h6v7"/>',
      chart: '<path d="M4 20V10m8 10V4m8 16v-8"/>', user: '<circle cx="12" cy="7" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
      arrow: '<path d="M4 12h15m-6-6 6 6-6 6"/>', back: '<path d="m14 5-7 7 7 7"/>', check: '<path d="m5 12 4 4L19 6"/>',
      flame: '<path d="M12 2c2 6-4 7-2 11 2-1 3-3 3-5 7 5 8 12 1 14C3 24 1 12 7 7c-1 5 2 5 2 5-1-4 2-6 3-10Z"/>',
      bolt: '<path d="m14 2-10 12h7l-1 8 10-12h-7Z"/>',
      star: '<path d="m12 2 3 6 7 1-5 5 1 8-6-4-6 4 1-8-5-5 7-1Z"/>',
      plus: '<path d="M12 5v14M5 12h14"/>', close: '<path d="m6 6 12 12M6 18 18 6"/>',
      clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>', undo: '<path d="M5 9h9a6 6 0 1 1 0 12M5 9l5-5M5 9l5 5"/>',
      leaf: '<path d="M20 3C7 2 1 8 5 16c7 7 15 1 15-13Z"/><path d="M4 21 15 10"/>', share: '<path d="M12 16V2m-5 5 5-5 5 5M5 12H3v10h18V12h-2"/>',
      trophy: '<path d="M7 3h10v7a5 5 0 0 1-10 0ZM7 5H3v4a4 4 0 0 0 5 4m9-8h4v4a4 4 0 0 1-5 4M12 15v6m-5 0h10"/>',
      bar: '<path d="M3 5h18M5 5v16M19 5v16M9 10h6m-3-2v9m0 0-3 4m3-4 3 4"/>',
      alert: '<path d="m12 3 10 18H2ZM12 9v5m0 3v1"/>', heart: '<path d="M20 4c-4-3-8 1-8 3-1-4-7-5-9-1-4 7 9 15 9 15s15-11 8-17Z"/>',
      sun: '<circle cx="12" cy="12" r="4"/><path d="M12 1v2m0 18v2M1 12h2m18 0h2M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/>',
    };
    return `<svg class="${cls}" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.bar}</svg>`;
  };
  function exerciseIcon(id) {
    const paths = {
      pullups: '<path d="M3 4h26M8 4v8l8 5 8-5V4m-8 13v8m0 0-5 5m5-5 5 5"/><circle cx="16" cy="9" r="3"/>',
      pushups: '<path d="m6 20 8-8 8 6 5 9M14 12l-4 14m-6 1h25"/><circle cx="25" cy="13" r="3"/>',
      dips: '<path d="M3 18h10m7 0h9M6 18v11m20-11v11M11 13l-1 8 6 4 6-4-1-8M16 25v4"/><circle cx="16" cy="8" r="4"/>',
      squats: '<circle cx="18" cy="6" r="3"/><path d="m16 10-5 9 10 3-3 7m-7-10-6 3v7m9-15 11 2"/>',
    };
    const base = id.replace('_weighted', '');
    const mark = id.includes('weighted') ? '<circle cx="26" cy="26" r="5" fill="var(--card)"/><path d="M23 26h6m-3-3v6"/>' : '';
    return `<svg class="exercise-icon" width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[base] || paths.pullups}${mark}</svg>`;
  }
  const athlete = () => `<svg class="hero-art" viewBox="0 0 220 260" fill="none" aria-hidden="true"><ellipse class="halo" cx="119" cy="137" rx="77" ry="89" transform="rotate(-18 119 137)"/><path d="M31 49h159M44 49v183m133-183v183" stroke="#65754d" stroke-width="3" stroke-linecap="round"/><path d="M30 233h162" stroke="#65754d" stroke-width="2" stroke-linecap="round" opacity=".4"/><g class="athlete" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"><path d="m80 49-4 46 28 20m42-66 3 46-29 20"/><path d="m101 159-8 32 7 36m18-68 12 31-6 37"/><path d="M101 106h20l8 46c-10 11-26 10-36 0Z" fill="#fcfff5" stroke-width="3"/><path d="m97 148 27-1" stroke-width="4"/></g><circle cx="110" cy="86" r="13" fill="#24291f"/><path d="m98 72 6-4 14 2 6 8" stroke="#24291f" stroke-width="5" stroke-linecap="round"/><path d="m45 23 4 7m126-10-4 7M197 120h9M18 127h8" stroke="#65754d" stroke-width="2" stroke-linecap="round"/><path d="m172 178 2 5 5 2-5 2-2 5-2-5-5-2 5-2Z" fill="#24291f"/></svg>`;
  function haptic(type = 'light') { try { if (telegramAtLeast('6.1')) tg.HapticFeedback.impactOccurred(type); } catch {} }
  function closingConfirmation(enabled) { try { if (telegramAtLeast('6.2')) enabled ? tg.enableClosingConfirmation() : tg.disableClosingConfirmation(); } catch {} }
  function toast(text) { const el = document.querySelector('#toast'); el.textContent = text; el.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('show'), 4000); }
  function applyTheme() {
    const dark = ui.theme ? ui.theme === 'dark' : (demo ? matchMedia('(prefers-color-scheme: dark)').matches : tg?.colorScheme === 'dark');
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    const color = dark ? '#171b16' : '#f6f6f0';
    document.querySelector('meta[name=theme-color]').content = color;
    try { if (telegramAtLeast('6.1')) { tg.setHeaderColor(telegramAtLeast('6.9') ? color : 'bg_color'); tg.setBackgroundColor(color); } } catch {}
  }
  function setBackButton() { try { if (telegramAtLeast('6.1')) (ui.session || ui.receipt || ui.modal || ui.tab !== 'today') ? tg.BackButton.show() : tg.BackButton.hide(); } catch {} }
  function renderHeader() {
    const name = state?.user?.name || state?.telegram_user?.first_name || 'Т';
    document.querySelector('#app-header').innerHTML = `<a class="brand" href="#" data-action="home" aria-label="${tr('Турникмен — главная', 'Turnikmen home')}"><span class="brand-mark">${icon('bar')}</span><div><div class="brand-name">${tr('турникмен', 'turnikmen')}<span style="color:var(--muted)">.</span></div><div class="brand-tag">A LITTLE STRONGER. EVERY DAY.</div></div></a><button class="avatar" data-action="tab" data-tab="profile" aria-label="${tr('Открыть профиль', 'Open profile')}">${esc(name.slice(0, 1).toUpperCase())}</button>`;
    const banner = document.querySelector('#demo-banner');
    banner.hidden = !demo;
    if (demo) banner.innerHTML = `<span class="status-dot"></span>${tr('Демо · данные не сохраняются', 'Demo · changes are not saved')}<button class="demo-reset" data-action="reset-demo">${tr('Сбросить', 'Reset')}</button>`;
  }
  function render() {
    if (!state) return;
    document.documentElement.lang = lang();
    nav.setAttribute('aria-label', tr('Главная навигация', 'Main navigation'));
    renderHeader(); setBackButton();
    app.setAttribute('aria-busy', 'false');
    const onboarding = !state.registered;
    nav.hidden = onboarding || Boolean(ui.session || ui.receipt);
    if (onboarding) app.innerHTML = renderOnboarding();
    else if (ui.receipt) app.innerHTML = renderSuccess();
    else if (ui.session) app.innerHTML = renderSession();
    else app.innerHTML = ui.tab === 'progress' ? renderProgress() : ui.tab === 'profile' ? renderProfile() : renderToday();
    if (ui.draft && !ui.session && !ui.receipt) app.insertAdjacentHTML('afterbegin', draftBanner());
    closingConfirmation(Boolean(ui.session?.sets.length || ui.session?.pending));
    if (!nav.hidden) nav.innerHTML = [['today', 'home', tr('Сегодня', 'Today')], ['progress', 'chart', tr('Прогресс', 'Progress')], ['profile', 'user', tr('Профиль', 'Profile')]].map(([tab, image, title]) => `<button class="nav-item ${ui.tab === tab ? 'active' : ''}" data-action="tab" data-tab="${tab}" ${ui.tab === tab ? 'aria-current="page"' : ''}>${icon(image)}<span>${title}</span></button>`).join('');
    updateTimer();
  }
  function weekStrip() {
    return `<div class="week-strip" aria-label="${tr('Активность за последние 7 дней', 'Activity over the last 7 days')}">${Array.from({ length: 7 }, (_, i) => {
      const day = dayShift(state.date, i - 6); const done = state.history.some(row => row.date === day && (row.completed > 0 || row.exercise === 'rest'));
      return `<div class="week-day ${done ? 'done' : ''} ${i === 6 ? 'current' : ''}"><span>${esc(dateText(day, { weekday: 'short' }).replace('.', ''))}</span><span class="week-dot">${done ? icon('check') : dateFrom(day).getDate()}</span></div>`;
    }).join('')}</div>`;
  }
  function renderToday() {
    const ex = getExercise(); const done = number(ex.today_completed); const planned = number(ex.today_planned); const rest = state.today.is_rest;
    return `<div class="page"><p class="greeting">${tr('Хороший день стать сильнее', 'A good day to get stronger')}, ${esc(state.user.name.split(' ')[0])}.</p><div class="intro"><h1>${tr('Твой темп.<br><em>Твой прогресс.</em>', 'Your pace.<br><em>Your progress.</em>')}</h1><span class="tiny-seal">${icon('sun')}</span></div>${weekStrip()}
    ${state.user.is_logged_out ? `<div class="notice">${tr('Тренировки на паузе. Вернись в свой ритм.', 'Your training is paused. Ready to get back?')}<button class="button" style="margin-top:12px" data-action="resume">${tr('Продолжить', 'Resume')}</button></div>` : ''}
    ${state.bot_session?.active ? `<div class="notice">${tr('В боте открыт диалог. Заверши его или отправь /cancel перед сохранением тренировки.', 'Finish your current bot conversation or send /cancel before saving a workout.')}</div>` : ''}
    <section class="hero" aria-label="${tr('План на сегодня', 'Today’s plan')}"><div class="eyebrow"><span class="status-dot"></span>${esc(dayLabel(state.today.label || state.today.day_type))} · ${dateText(state.date, { day: 'numeric', month: 'short' })}</div><div class="hero-title">${rest ? tr('Восстановление —<br>тоже прогресс.', 'Recovery is<br>progress, too.') : esc(nameOf(ex.id))}</div>${athlete()}<div class="hero-number"><strong>${fmt(done)}</strong><span>/ ${fmt(planned || ex.base)}</span></div><div class="hero-caption">${rest ? tr('сегодня можно замедлиться', 'permission to take it easy') : tr('повторений в твоём темпе', 'repetitions at your own pace')}</div><div class="hero-progress" role="progressbar" aria-label="${tr('Дневная цель', 'Daily goal')}" aria-valuenow="${Math.round(pct(done, planned))}" aria-valuemin="0" aria-valuemax="100"><span style="width:${pct(done, planned)}%"></span></div><button class="button ink" data-action="${rest ? 'rest' : ex.configured ? 'start' : 'setup'}" ${ui.busy ? 'disabled' : ''}>${icon(rest ? 'leaf' : 'plus')} ${rest ? tr('Отметить день отдыха', 'Complete rest day') : ex.configured ? (done ? tr('Добавить подходы', 'Add more sets') : tr('Начать тренировку', 'Start workout')) : tr('Настроить упражнение', 'Set up exercise')}</button><div class="hero-footer"><span>${rest ? tr('Сон. Прогулка. Немного заботы.', 'Sleep. A walk. A little self-care.') : tr('Каждый подход имеет значение', 'Every set is a step forward')}</span><span>${rest ? '↗' : `${Math.round(pct(done, planned))}%`}</span></div></section>
    <div class="metrics"><div class="metric"><span class="metric-icon">${icon('flame')}</span><div><div class="metric-value">${fmt(state.user.streak)} <span style="font-size:11px;font-weight:500">${tr('дн.', 'days')}</span></div><div class="metric-label">${tr('серия без пропусков', 'current streak')}</div></div></div><div class="metric"><span class="metric-icon">${icon('bolt')}</span><div><div class="metric-value">${fmt(state.user.xp)} <span style="font-size:11px;font-weight:500">XP</span></div><div class="metric-label">${esc(state.user.level_name)}</div></div></div></div>
    <section class="section"><div class="section-heading"><h2>${tr('Выбери движение', 'Choose your movement')}</h2><span class="eyebrow muted">${tr('6 упражнений', '6 exercises')}</span></div><div class="exercise-grid">${state.exercises.map(item => `<button class="exercise ${item.id === ui.selected ? 'selected' : ''}" data-action="select" data-id="${esc(item.id)}" aria-pressed="${item.id === ui.selected}">${exerciseIcon(item.id)}<span class="exercise-label">${esc(nameOf(item.id))}</span><span class="exercise-value">${item.configured ? `${fmt(item.today_completed)} / ${fmt(item.today_planned || item.base)} ${tr('повт.', 'reps')}` : tr('Настроить ↗', 'Set up ↗')}</span></button>`).join('')}</div>${rest ? `<button class="text-button" style="margin:10px auto" data-action="${ex.configured ? 'start' : 'setup'}">${tr('Всё-таки потренироваться', 'Train anyway')} ${icon('arrow')}</button>` : ''}</section>
    <section class="section"><div class="section-heading"><h2>${tr('В твоём ритме', 'Find your rhythm')}</h2><button class="text-button" data-action="plan">${tr('План недели', 'Weekly plan')} ${icon('arrow')}</button></div><div class="note-card">${icon('leaf')}<div><strong>${tr('Регулярность важнее рекордов.', 'Consistency beats a single record.')}</strong><p>${tr('Не обязательно делать всё за раз. Добавляй подходы в течение дня — мы сложим результат.', 'No need to do it all at once. Add sets throughout the day; every repetition counts.')}</p></div></div></section><p class="footer-note">${tr('Ты соревнуешься только со вчерашним собой.', 'The only competition is yesterday’s you.')}</p></div>`;
  }
  function rankCard() {
    const progress = number(state.user.level_progress);
    return `<div class="card rank-card"><div class="row"><span class="rank-badge">${icon('star')}</span><div><p class="eyebrow muted" style="margin-bottom:7px">${tr('Твой уровень', 'Your rank')}</p><h2>${esc(state.user.level_name)}</h2></div></div><div class="rank-progress"><span style="width:${Math.min(100, progress)}%"></span></div><div class="row between small"><span>${fmt(state.user.xp)} XP</span><span class="muted">${state.user.next_level_xp ? `${fmt(Math.max(0, state.user.next_level_xp - state.user.xp))} XP ${tr('до следующего', 'to next rank')}` : tr('Высший ранг', 'Top rank')}</span></div></div>`;
  }
  function renderProgress() {
    const team = ui.progressTab === 'team';
    const days = Array.from({ length: 7 }, (_, i) => dayShift(state.date, i - 6));
    const totals = days.map(date => sum(state.history.filter(row => row.date === date).map(row => row.completed)));
    const maximum = Math.max(1, ...totals);
    const history = state.history.filter(row => !ui.filter || row.exercise === ui.filter);
    const achievements = [[state.stats.total_workouts >= 1, 'check', tr('Первый шаг', 'First step'), tr('1 тренировка', '1 workout')], [state.user.max_streak >= 7, 'flame', tr('В ритме', 'On a roll'), tr('7 дней подряд', '7-day streak')], [state.stats.total_reps >= 1000, 'trophy', tr('Тысяча', 'The thousand'), tr('1 000 повторов', '1,000 reps')]];
    return `<div class="page"><div class="page-head"><h1>${tr('Сильнее, чем вчера.', 'Stronger than yesterday.')}</h1><p>${tr('Маленькие шаги. Большие изменения.', 'Small steps. Real change.')}</p></div>${rankCard()}<div class="segmented"><button class="${!team ? 'active' : ''}" data-action="progress-tab" data-tab="personal">${tr('Мой прогресс', 'My progress')}</button><button class="${team ? 'active' : ''}" data-action="progress-tab" data-tab="team">${tr('Команда', 'Community')}</button></div>${team ? renderTeam() : `<div class="card"><div class="chart-top"><div><p class="eyebrow muted">${tr('Последние 7 дней', 'Last 7 days')}</p><div class="chart-value">${fmt(sum(totals))} <small>${tr('повторений', 'repetitions')}</small></div></div><span class="badge">${tr('Твоя активность', 'Your activity')}</span></div><div class="chart" aria-label="${tr('Повторения по дням', 'Daily repetitions')}">${days.map((day, i) => `<div class="chart-column ${i === 6 ? 'current' : ''}" title="${dateText(day)}: ${fmt(totals[i])}"><div class="bar-track"><div class="bar" style="height:${Math.max(3, totals[i] / maximum * 100)}%"></div></div><span>${dateText(day, { weekday: 'short' }).replace('.', '')}</span><span class="sr-only">${fmt(totals[i])} ${tr('повторов', 'reps')}</span></div>`).join('')}</div><div class="stats-grid"><div><strong>${fmt(state.stats.total_workouts)}</strong><span>${tr('тренировок', 'workouts')}</span></div><div><strong>${fmt(state.stats.total_reps)}</strong><span>${tr('всего повторов', 'total reps')}</span></div><div><strong>${fmt(state.user.max_streak)}</strong><span>${tr('лучшая серия', 'best streak')}</span></div></div></div><section class="section"><div class="section-heading"><h2>${tr('Твои маленькие победы', 'Your little wins')}</h2></div><div class="milestones">${achievements.map(([earned, symbol, title, subtitle]) => `<div class="milestone ${earned ? 'earned' : ''}" aria-label="${esc(title)}: ${earned ? tr('достигнуто', 'achieved') : tr('впереди', 'not yet')} "><div class="milestone-symbol">${icon(symbol)}</div><strong>${title}</strong><small>${subtitle}</small></div>`).join('')}</div></section><section class="section"><div class="section-heading"><h2>${tr('История', 'History')}</h2><select class="filter-select" id="history-filter" aria-label="${tr('Фильтр упражнений', 'Filter exercises')}"><option value="">${tr('Все упражнения', 'All exercises')}</option>${state.exercises.map(ex => `<option value="${ex.id}" ${ui.filter === ex.id ? 'selected' : ''}>${esc(nameOf(ex.id))}</option>`).join('')}</select></div><div class="card" style="padding:4px 18px">${history.length ? history.slice(0, ui.historyLimit).map(row => `<div class="history-row"><span class="history-icon">${row.exercise === 'rest' ? icon('leaf') : exerciseIcon(row.exercise)}</span><div class="history-details"><strong>${esc(nameOf(row.exercise))}${row.weight_kg ? ` +${fmt(row.weight_kg)} ${tr('кг', 'kg')}` : ''}</strong><small>${esc(dateText(row.date))} · ${row.exercise === 'rest' ? tr('День отдыха', 'Rest day') : `${number(row.sets?.length)} ${tr('подх.', 'sets')} · RPE ${number(row.rpe)}`}</small></div><div class="history-count">${fmt(row.completed)}<small>+${fmt(row.xp)} XP</small></div></div>`).join('') : `<div class="empty">${icon('chart')}${tr('Здесь появится твоя первая тренировка.', 'Your first workout will appear here.')}</div>`}</div>${history.length > ui.historyLimit ? `<button class="text-button" style="margin:8px auto" data-action="history-more">${tr('Показать ещё', 'Show more')}</button>` : ''}<p class="footer-note">${tr('История за последние 90 дней', 'History from the last 90 days')}</p></section>`}</div>`;
  }
  function renderTeam() {
    const rows = state.leaderboard || [];
    return `<section class="card"><div class="section-heading"><div><h2>${tr('Двигаемся вместе', 'Better together')}</h2><p class="small muted" style="margin-top:6px">${tr('XP за эту неделю · понедельник — воскресенье', 'This week’s XP · Monday to Sunday')}</p></div>${icon('trophy')}</div>${rows.length ? rows.map(row => `<div class="leader-row ${row.is_me ? 'me' : ''}"><span class="leader-position">${number(row.rank)}</span><span class="avatar">${esc(row.name?.slice(0, 1).toUpperCase())}</span><div class="history-details"><strong>${esc(row.name)}${row.is_me ? ` · ${tr('ты', 'you')}` : ''}${row.is_weekly_champ ? ' ♛' : ''}</strong><small>${number(row.streak)} ${tr('дн. в ритме', 'day streak')}</small></div><span class="history-count">${fmt(row.xp)} <small>XP</small></span></div>`).join('') : `<div class="empty">${tr('Новая неделя — новый старт. Первая тренировка откроет рейтинг.', 'A fresh week, a fresh start. Complete a workout to join the board.')}</div>`}</section><div class="section note-card">${icon('heart')}<div><strong>${tr('Поддержка вместо сравнения.', 'Encouragement over comparison.')}</strong><p>${tr('У каждого свой старт. Важнее всего — продолжать приходить.', 'Everyone starts somewhere. What matters most is showing up again.')}</p></div></div>`;
  }
  function renderProfile() {
    const s = state.settings;
    return `<div class="page"><div class="profile-hero"><span class="avatar">${esc(state.user.name.slice(0, 1).toUpperCase())}</span><div><h1>${esc(state.user.name)}</h1><p>${esc(state.user.level_name)} · ${tr('Всё начинается с тебя', 'It all starts with you')}</p></div></div><div class="note-card" style="margin-bottom:23px">${icon('star')}<div><strong>${fmt(state.user.freeze_tokens)} ${tr('заморозок серии', 'streak freezes')}</strong><p>${tr('Небольшая страховка на случай, когда жизнь вносит свои планы.', 'A little breathing room for the days when life gets in the way.')}</p></div></div><form id="settings-form" class="card"><div class="section-heading"><h2>${tr('Твой ритм', 'Your routine')}</h2>${icon('user')}</div><div class="form-group"><label for="profile-name">${tr('Как тебя называть', 'Your name')}</label><input class="input" id="profile-name" name="name" value="${esc(s.name || state.user.name)}" minlength="3" maxlength="64" required autocomplete="given-name"></div><div class="form-group"><label for="program">${tr('Программа', 'Program')}</label><select class="input" id="program" name="program_type">${programOptions(s.program_type)}</select><small class="input-help">${tr('Чередуем нагрузку и восстановление. Норма адаптируется к твоим результатам.', 'Training and recovery in balance. Targets adapt to your progress.')}</small></div><div class="form-row"><div class="form-group"><label for="notify-time">${tr('Напоминание', 'Reminder')}</label><input class="input" type="time" id="notify-time" name="notify_time" value="${esc(s.notify_time || '09:00')}" required><small class="input-help">${esc(state.timezone)}</small></div><div class="form-group"><label for="language">${tr('Язык', 'Language')}</label><select class="input" id="language" name="language"><option value="ru" ${lang() === 'ru' ? 'selected' : ''}>Русский</option><option value="en" ${lang() === 'en' ? 'selected' : ''}>English</option></select></div></div><label class="toggle-label" for="notify-workouts"><span>${tr('Новости команды', 'Community updates')}<small>${tr('Узнавай о тренировках других участников в боте', 'Hear about other members’ workouts in the bot')}</small></span><input id="notify-workouts" class="switch" name="notify_workouts" type="checkbox" ${s.notify_workouts ? 'checked' : ''}></label><p id="settings-error" class="inline-error" role="alert"></p><button class="button" type="submit" ${ui.busy ? 'disabled' : ''}>${tr('Сохранить настройки', 'Save settings')}</button></form><section class="section"><div class="section-heading"><h2>${tr('Мои упражнения', 'My exercises')}</h2></div><div class="card" style="padding:9px 20px">${state.exercises.map(ex => `<button class="profile-exercise" data-action="setup" data-id="${ex.id}">${exerciseIcon(ex.id)}<span>${esc(nameOf(ex.id))}<small>${ex.configured ? `${tr('База', 'Base')}: ${fmt(ex.base)}${ex.weighted ? ` · +${fmt(ex.weight_kg)} ${tr('кг', 'kg')}` : ''}` : tr('Пока не настроено', 'Not configured yet')}</small></span><span class="chevron">↗</span></button>`).join('')}</div></section>${demo ? `<section class="section"><button class="button outline" data-action="theme">${icon('sun')}${tr('Переключить тему', 'Switch theme')}</button><button class="text-button" style="margin:8px auto" data-action="demo-onboarding">${tr('Посмотреть первый запуск', 'Preview onboarding')}</button></section>` : ''}<section class="section"><button class="button outline" data-action="open-bot">${tr('Открыть Telegram-бота', 'Open Telegram bot')} ${icon('arrow')}</button></section><p class="footer-note">${tr('Турникмен · маленький шаг каждый день', 'Turnikmen · a little stronger every day')}<br>${tr('Твои тренировки синхронизируются с ботом.', 'Your workouts sync with the bot.')}</p></div>`;
  }
  function programOptions(selected) { return [['standard', tr('Стандарт · 5 дней в неделю', 'Standard · 5 days per week')], ['beginner', tr('Начинающий · 3 дня в неделю', 'Beginner · 3 days per week')], ['advanced', tr('Продвинутый · 6 дней в неделю', 'Advanced · 6 days per week')]].map(([value, label]) => `<option value="${value}" ${selected === value ? 'selected' : ''}>${label}</option>`).join(''); }
  function renderOnboarding() {
    return `<div class="page onboarding"><div class="onboarding-art">${athlete()}</div><div class="eyebrow">START WHERE YOU ARE</div><h1>${tr('Твоя новая<br>хорошая привычка.', 'Your next<br>good habit.')}</h1><p>${tr('Без сложных программ. Только ты, твой темп и ещё один подход.', 'No complicated plans. Just you, your own pace, and one more set.')}</p><form id="onboarding-form" class="card"><div class="form-group"><label for="onboard-name">${tr('Как тебя зовут?', 'What’s your name?')}</label><input class="input" id="onboard-name" name="name" placeholder="${tr('Твоё имя', 'Your name')}" value="${esc(state.telegram_user?.first_name || '')}" minlength="3" maxlength="64" required autocomplete="given-name"></div><div class="form-group"><label for="onboard-max">${tr('Сколько раз подтягиваешься за подход?', 'Your maximum pull-ups in one set?')}</label><input class="input" id="onboard-max" name="max_pullups" type="number" inputmode="numeric" min="1" max="200" value="5" required><small class="input-help">${tr('Честный максимум, без рывков. Начнём с посильной нагрузки.', 'A comfortable, honest maximum. We’ll build a manageable plan.')}</small></div><div class="form-group"><label for="onboard-program">${tr('Выбери ритм', 'Choose your pace')}</label><select class="input" id="onboard-program" name="program_type">${programOptions('standard')}</select></div><div class="form-group"><label for="onboard-language">${tr('Язык', 'Language')}</label><select class="input" id="onboard-language" name="language"><option value="ru" ${lang() === 'ru' ? 'selected' : ''}>Русский</option><option value="en" ${lang() === 'en' ? 'selected' : ''}>English</option></select></div><p id="onboarding-error" class="inline-error" role="alert"></p><button class="button ink" type="submit" ${ui.busy ? 'disabled' : ''}>${tr('Мой первый шаг', 'Let’s take the first step')} ${icon('arrow')}</button></form></div>`;
  }
  function renderSession() {
    const s = ui.session; const total = sum(s.sets); const todayTotal = total + s.doneBefore;
    if (s.exercise === 'rest') return `<div class="page success"><div class="success-art">${icon('leaf')}</div><h1>${tr('Подтвердим отдых.', 'Let’s confirm your rest.')}</h1><p>${tr('Сохраним день восстановления в твоём плане. Если связь прервалась, повтор не засчитает день дважды.', 'Save your recovery day. If the connection dropped, retrying won’t count it twice.')}</p>${ui.error ? `<p class="inline-error" role="alert">${esc(ui.error)}</p>` : ''}<button class="button ink" data-action="save-rest">${tr('Повторить сохранение', 'Retry saving')}</button><button class="button secondary" data-action="back">${tr('Назад', 'Back')}</button></div>`;
    return `<div class="page"><div class="session-head"><button class="icon-button" data-action="back" aria-label="${tr('Назад', 'Back')}">${icon('back')}</button><div><h1>${esc(nameOf(s.exercise))}</h1><p>${tr('Сейчас только ты и следующий подход.', 'Just you and your next set.')}${s.weight ? ` · +${fmt(s.weight)} ${tr('кг', 'kg')}` : ''}</p></div></div><div class="session-target"><span>${tr('Дневная цель', 'Daily goal')}</span><strong>${fmt(todayTotal)} / ${fmt(s.planned)}</strong></div><div class="session-progress"><span style="width:${pct(todayTotal, s.planned)}%"></span></div><div class="counter-caption">${tr('ПОДХОД', 'SET')} ${s.sets.length + 1}</div><div class="rep-counter"><button data-action="rep-minus" aria-label="${tr('Уменьшить повторы', 'Decrease repetitions')}">−</button><label class="sr-only" for="rep-input">${tr('Повторов в подходе', 'Repetitions in this set')}</label><input id="rep-input" type="number" inputmode="numeric" min="1" max="${state.limits.max_reps}" value="${s.reps}" aria-label="${tr('Повторов в подходе', 'Repetitions in this set')}"><button data-action="rep-plus" aria-label="${tr('Добавить повтор', 'Increase repetitions')}">+</button></div><div class="counter-caption">${tr('повторений — столько, сколько получилось', 'repetitions — every single one counts')}</div><div class="quick-reps">${[5, 8, 10, 12, 15].map(value => `<button data-action="quick-reps" data-value="${value}" class="${s.reps === value ? 'selected' : ''}">${value}</button>`).join('')}</div><div class="rest-panel"><div class="row between"><div><p class="eyebrow muted" style="margin-bottom:6px">${tr('Выдохни. Отдохни.', 'Breathe. Recover.')}</p><div class="rest-value" id="rest-value">${timerText()}</div></div><div class="rest-options">${[60, 75, 90].map(value => `<button data-action="rest-duration" data-value="${value}" class="${ui.restSeconds === value ? 'selected' : ''}" aria-label="${value} ${tr('секунд отдыха', 'seconds rest')}">${value}${tr('с', 's')}</button>`).join('')}</div></div><div class="timer-track"><span id="rest-progress"></span></div></div><div class="section-heading"><h2>${tr('Твои подходы', 'Your sets')}</h2><button class="text-button" data-action="undo" ${!s.sets.length || s.pending ? 'disabled' : ''}>${icon('undo')} ${tr('Отменить', 'Undo')}</button></div><div class="set-list">${s.sets.length ? s.sets.map((reps, i) => `<button class="set-pill" data-action="edit-set" data-index="${i}" ${s.pending ? 'disabled' : ''} aria-label="${tr('Изменить подход', 'Edit set')} ${i + 1}: ${reps}"><small>${i + 1}</small><strong>${reps}</strong>${icon('check')}</button>`).join('') : `<p class="small muted" style="padding:15px 0">${tr('Первый подход — самое важное начало.', 'The first set is a great place to start.')}</p>`}</div>${ui.error ? `<p class="inline-error" role="alert">${esc(ui.error)}</p>` : ''}<div class="session-actions"><button class="button ink" data-action="add-set" ${s.pending || s.sets.length >= state.limits.max_sets ? 'disabled' : ''}>${icon('plus')} ${tr('Записать подход', 'Log this set')}</button><button class="button secondary" data-action="finish" ${!s.sets.length || ui.busy ? 'disabled' : ''}>${s.pending ? tr('Повторить сохранение', 'Retry saving') : tr('Завершить тренировку', 'Finish workout')} ${icon('arrow')}</button></div><p class="session-summary-note">${tr('Нажми на подход, чтобы исправить число.', 'Tap a set to change its repetitions.')}<br>${demo ? tr('Демо: тренировка останется только на этой странице.', 'Demo: this workout stays on this page only.') : tr('Сохраним в боте после завершения тренировки.', 'We’ll save it to your bot when you finish.')}</p></div>`;
  }
  function renderSuccess() {
    const r = ui.receipt; const rest = r.exercise === 'rest';
    return `<div class="page success"><div class="success-art">${icon(rest ? 'leaf' : 'check')}</div><h1>${rest ? tr('Отдых — часть пути.', 'Rest is part of the journey.') : tr('Ещё на шаг<br>сильнее.', 'One step<br>stronger.')}</h1><p>${rest ? tr('Восстановись. Увидимся на следующей тренировке.', 'Recharge. We’ll see you at the next workout.') : tr('Ты сделал главное — пришёл и сделал.<br>Пусть это станет твоим ритмом.', 'You showed up. You did the work.<br>Keep that good thing going.')}</p><div class="card"><div class="row between"><h3>${esc(nameOf(r.exercise))}</h3><span class="badge">${esc(dateText(r.date))}</span></div><div class="stats-grid" style="margin-top:24px"><div><strong>${fmt(r.sessionReps ?? r.completed)}</strong><span>${tr('повторений', 'repetitions')}</span></div><div><strong>${fmt(r.setsCount)}</strong><span>${tr('подходов', 'sets')}</span></div><div><strong>${fmt(r.rpe)}</strong><span>RPE</span></div></div></div><div class="success-xp"><span>${tr('Сегодня ты заработал', 'You earned today')}</span><strong>+${fmt(r.xp_gained)} XP</strong></div><button class="button ink" data-action="done">${tr('Отлично. Продолжаем.', 'Feels good. Keep going.')} ${icon('arrow')}</button><button class="button outline" data-action="share">${icon('share')}${tr('Поделиться результатом', 'Share result')}</button><p class="footer-note">${demo ? tr('Демонстрационный результат · не сохранён в боте', 'Demo result · not saved to the bot') : tr('Сохранено. В боте уже тот же результат.', 'Saved. Your bot is already up to date.')}</p></div>`;
  }
  function showModal(kind, html) { lastFocus = document.activeElement; ui.modal = kind; modal.innerHTML = `<div class="modal-handle"></div><button class="modal-close" data-action="close-modal" aria-label="${tr('Закрыть', 'Close')}">${icon('close')}</button>${html}`; if (!modal.open) modal.showModal(); setBackButton(); }
  function closeModal() { if (ui.busy) return; modal.close(); ui.modal = ''; setBackButton(); (lastFocus?.isConnected ? lastFocus : app)?.focus?.({ preventScroll: true }); }
  function rpeModal() {
    showModal('rpe', `<h2 id="modal-title">${tr('Как ощущения?', 'How did it feel?')}</h2><p>${tr('Оцени усилие от 1 до 10. Это поможет подобрать следующую нагрузку.', 'Rate your effort from 1 to 10. It helps us adjust your next workout.')}</p><div class="rpe-buttons">${Array.from({ length: 10 }, (_, i) => `<button data-action="rpe" data-value="${i + 1}" aria-pressed="${ui.rpe === i + 1}" class="${ui.rpe === i + 1 ? 'selected' : ''}">${i + 1}</button>`).join('')}</div><div class="rpe-legend"><span>${tr('Легко', 'Easy')}</span><span>${tr('На пределе', 'Maximum effort')}</span></div><div class="rpe-description" id="rpe-description">${rpeDescription()}</div><p id="save-error" class="inline-error" role="alert"></p><div class="modal-actions"><button class="button ink" data-action="save-workout">${tr('Сохранить тренировку', 'Save workout')} ${icon('check')}</button></div>`);
  }
  function rpeDescription() { return ui.rpe <= 3 ? tr('Легко. Сил ещё много.', 'Easy. Plenty left in the tank.') : ui.rpe <= 6 ? tr('Рабочая нагрузка. Есть запас.', 'Solid work. Some energy left.') : ui.rpe <= 8 ? tr('Непросто. Ещё 1–2 повтора в запасе.', 'Challenging. 1–2 reps left.') : tr('Почти предел. Восстановление особенно важно.', 'Near your limit. Make time for recovery.'); }
  function setupModal(id) {
    const ex = state.exercises.find(item => item.id === id) || getExercise();
    showModal('setup', `<h2 id="modal-title">${esc(nameOf(ex.id))}</h2><p>${tr('Отталкиваемся от твоих возможностей, а не от чужих рекордов.', 'Start with what you can do, not someone else’s records.')}</p><form id="exercise-form" data-exercise="${ex.id}"><div class="form-group"><label for="exercise-max">${tr('Максимум за один подход', 'Maximum in a single set')}</label><input class="input" id="exercise-max" name="max_reps" type="number" inputmode="numeric" min="1" max="200" value="${ex.configured ? Math.max(1, Math.round(ex.base / 3)) : 5}" required><small class="input-help">${tr('Базовая дневная цель: максимум × 3.', 'Base daily target: your maximum × 3.')}</small></div>${ex.weighted ? `<div class="form-group"><label for="exercise-weight">${tr('Дополнительный вес, кг', 'Added weight, kg')}</label><input class="input" id="exercise-weight" name="weight_kg" type="number" inputmode="decimal" min="0" max="100" step="0.5" value="${number(ex.weight_kg)}" ${ex.weight_locked ? 'disabled' : ''}><small class="input-help">${ex.weight_locked ? tr('Сегодня уже есть подходы. Новый вес можно выбрать завтра.', 'You’ve logged sets today. Choose a different weight tomorrow.') : tr('Только дополнительный вес, без веса тела.', 'Added load only, not your body weight.')}</small></div>` : ''}<p id="exercise-error" class="inline-error" role="alert"></p><div class="modal-actions"><button class="button ink" type="submit">${tr('Сохранить', 'Save')}</button></div></form>`);
  }
  function persistSession() {
    if (demo || !state?.user) return;
    try {
      const key = `turnikmen-session-${state.user.id}`;
      if (ui.session) { ui.session.restSeconds = ui.restSeconds; localStorage.setItem(key, JSON.stringify({ userId: state.user.id, savedAt: Date.now(), session: ui.session })); }
      else localStorage.removeItem(key);
    } catch {
      if (!ui.storageWarning && ui.session) {
        ui.storageWarning = true;
        toast(tr('Черновик остаётся только в открытом приложении. Заверши тренировку перед закрытием.', 'This draft only stays in the open app. Finish your workout before closing.'));
      }
    }
  }
  function restoreDraft() {
    if (demo || !state.registered) return;
    try {
      const key = `turnikmen-session-${state.user.id}`;
      const wrapper = JSON.parse(localStorage.getItem(key) || 'null');
      if (!wrapper) return;
      const s = wrapper.session;
      const age = Date.now() - wrapper.savedAt;
      const valid = wrapper.userId === state.user.id && age >= 0 && (age <= 86400000 || s?.pending) && s
        && typeof s.id === 'string' && /^[a-f0-9-]{36}$/i.test(s.id)
        && typeof s.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s.date) && !Number.isNaN(dateFrom(s.date).getTime())
        && (s.exercise === 'rest' || state.exercises.some(ex => ex.id === s.exercise))
        && Array.isArray(s.sets) && s.sets.length <= state.limits.max_sets
        && s.sets.every(reps => Number.isInteger(reps) && reps >= 1 && reps <= state.limits.max_reps)
        && sum(s.sets) <= (state.limits.max_total_reps || 10000)
        && (!s.pending || (s.pending.session_id === s.id && s.pending.exercise === s.exercise && s.pending.date === s.date));
      if (!valid) { localStorage.removeItem(key); return; }
      s.reps = Math.max(1, Math.min(state.limits.max_reps, Math.floor(number(s.reps) || 10)));
      ui.draft = s;
    } catch { /* Storage may be unavailable; the active session still works in memory. */ }
  }
  function draftBanner() {
    return `<section class="notice" aria-label="${tr('Незавершённая тренировка', 'Unfinished workout')}"><strong>${tr('Ты уже начал. Продолжим?', 'You already started. Keep going?')}</strong><p style="margin-top:5px">${esc(nameOf(ui.draft.exercise))} · ${sum(ui.draft.sets)} ${tr('повторов', 'reps')} · ${esc(dateText(ui.draft.date))}${ui.draft.pending ? `<br>${tr('Проверим сохранение без повторного начисления.', 'Confirm the save without counting anything twice.')}` : ''}</p><div class="row" style="margin-top:13px"><button class="button ink" data-action="resume-draft">${tr('Продолжить', 'Resume')}</button><button class="icon-button" data-action="discard-draft" aria-label="${tr('Удалить черновик', 'Discard draft')}">${icon('close')}</button></div></section>`;
  }
  function startSession() {
    if (ui.draft) { toast(tr('Сначала продолжи или удали незавершённую тренировку.', 'Resume or discard your unfinished workout first.')); return; }
    if (state.user.is_logged_out) { toast(tr('Сначала возобнови тренировки.', 'Resume training first.')); return; }
    if (state.bot_session?.active) { toast(tr('Заверши диалог в боте или отправь /cancel.', 'Finish the bot conversation or send /cancel.')); return; }
    const ex = getExercise(); if (!ex.configured) return setupModal(ex.id);
    ui.session = { id: uid(), exercise: ex.id, date: state.date, sets: [], reps: 10, doneBefore: number(ex.today_completed), planned: number(ex.today_planned || ex.base), weight: number(ex.weight_locked ? ex.today_weight_kg : ex.weight_kg), restEnd: 0, pending: null };
    ui.error = ''; ui.rpe = 6; persistSession(); haptic('medium'); render(); window.scrollTo(0, 0);
  }
  function timerText() { const remain = ui.session?.restEnd ? Math.max(0, Math.ceil((ui.session.restEnd - Date.now()) / 1000)) : ui.restSeconds; return `${Math.floor(remain / 60)}:${String(remain % 60).padStart(2, '0')}`; }
  function updateTimer() { const text = document.querySelector('#rest-value'); if (!text || !ui.session) return; text.textContent = timerText(); const remain = ui.session.restEnd ? Math.max(0, (ui.session.restEnd - Date.now()) / 1000) : ui.restSeconds; document.querySelector('#rest-progress').style.width = `${pct(remain, ui.restSeconds)}%`; if (ui.session.restEnd && remain === 0 && !ui.session.restNotified) { ui.session.restNotified = true; haptic('medium'); toast(tr('Можно переходить к следующему подходу.', 'Ready for your next set.')); } }
  function setReps(value) { if (!ui.session) return; ui.session.reps = Math.max(1, Math.min(state.limits.max_reps, Math.floor(number(value)))); const input = document.querySelector('#rep-input'); if (input) input.value = ui.session.reps; document.querySelectorAll('[data-action=quick-reps]').forEach(btn => btn.classList.toggle('selected', Number(btn.dataset.value) === ui.session.reps)); }
  function addSet() {
    const s = ui.session; if (!s || s.pending) return;
    const reps = Number(document.querySelector('#rep-input').value);
    if (!Number.isInteger(reps) || reps < 1 || reps > state.limits.max_reps) return toast(tr(`Введи от 1 до ${state.limits.max_reps} повторов.`, `Enter 1–${state.limits.max_reps} repetitions.`));
    if (s.sets.length >= state.limits.max_sets || sum(s.sets) + reps > (state.limits.max_total_reps || 10000)) return toast(tr('Достигнут лимит тренировки. Заверши её.', 'Workout limit reached. Finish this workout.'));
    s.sets.push(reps); s.reps = reps; s.restEnd = Date.now() + ui.restSeconds * 1000; s.restNotified = false; persistSession(); haptic('medium'); render();
  }
  function back() {
    if (ui.busy) return;
    if (ui.modal) return closeModal();
    if (ui.receipt) { ui.receipt = null; return render(); }
    if (ui.session?.sets.length || ui.session?.pending) return showModal('cancel', `<h2 id="modal-title">${tr('Выйти из тренировки?', 'Leave this workout?')}</h2><p>${ui.session.pending ? tr('Результат мог уже сохраниться. Лучше повторить сохранение — подходы не продублируются.', 'Your result may already be saved. Retry saving to confirm; sets won’t be duplicated.') : tr('Подходы этой сессии ещё не сохранены. Можно продолжить или завершить тренировку.', 'These sets haven’t been saved yet. You can keep going or finish the workout.')}</p><div class="modal-actions"><button class="button ink" data-action="close-modal">${tr('Продолжить тренировку', 'Keep training')}</button><button class="button secondary" data-action="finish">${tr('Завершить и сохранить', 'Finish and save')}</button>${!ui.session.pending ? `<button class="button danger" data-action="discard">${tr('Удалить эту сессию', 'Discard this session')}</button>` : ''}</div>`);
    if (ui.session) { ui.session = null; persistSession(); closingConfirmation(false); }
    ui.tab = 'today'; render(); window.scrollTo(0, 0);
  }
  async function api(endpoint, payload) {
    if (demo) return demoApi(endpoint, payload);
    const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(`/api/miniapp/${endpoint}`, { method: payload === undefined ? 'GET' : 'POST', headers: { Authorization: `tma ${initData}`, ...(payload !== undefined ? { 'Content-Type': 'application/json' } : {}) }, body: payload === undefined ? undefined : JSON.stringify(payload), signal: controller.signal, credentials: 'same-origin', cache: 'no-store' });
      let result; try { result = await response.json(); } catch { throw new Error(tr('Сервер не ответил. Попробуй ещё раз.', 'The server didn’t respond. Try again.')); }
      if (!response.ok || !result.ok) { const error = new Error(result.error?.message || tr('Не удалось сохранить.', 'Could not save.')); error.code = result.error?.code; throw error; }
      return result;
    } catch (error) { if (error.name === 'AbortError' || error instanceof TypeError) { const e = new Error(tr('Связь прервалась. Подходы на месте — повтори сохранение.', 'Connection lost. Your sets are safe here — retry saving.')); e.code = 'network'; throw e; } throw error; }
    finally { clearTimeout(timeout); }
  }
  const friendlyError = error => ({ bot_session_active: tr('Заверши текущий диалог в боте или отправь /cancel.', 'Finish your current bot conversation or send /cancel.'), expired_auth: tr('Сессия Telegram истекла. Закрой и снова открой приложение из бота.', 'Your Telegram session expired. Reopen the app from the bot.'), invalid_auth: tr('Открой приложение через кнопку в Telegram-боте.', 'Open the app using the button in the Telegram bot.'), date_changed: tr('Начался новый день. Подходы сохранены на экране; обнови дату и отправь их за сегодня.', 'A new day has started. Your sets are still here; update the date and save them for today.'), weight_locked: tr('Вес уже зафиксирован сегодняшней тренировкой. Обнови приложение.', 'Today’s workout already locked the weight. Refresh the app.'), maintenance: tr('Небольшой перерыв на обслуживание. Попробуй чуть позже.', 'A short maintenance break. Please try again later.'), rate_limited: tr('Слишком быстро. Подожди немного и повтори.', 'A little too fast. Wait a moment and try again.') })[error.code] || error.message;
  function setBusy(value) { ui.busy = value; document.querySelectorAll('dialog button,dialog input,dialog select').forEach(el => { el.disabled = value; }); modal.setAttribute('aria-busy', String(value)); }
  async function saveWorkout() {
    if (ui.busy || !ui.session) return;
    const s = ui.session;
    if (!s.pending) s.pending = { session_id: s.id, exercise: s.exercise, date: s.date, sets: [...s.sets], rpe: ui.rpe, weight_kg: s.weight };
    persistSession(); setBusy(true);
    try {
      const result = await api('workout', s.pending); state = result.state;
      ui.receipt = { ...result.receipt, sessionReps: sum(s.sets), setsCount: s.sets.length, rpe: s.pending.rpe };
      ui.session = null; persistSession(); closingConfirmation(false); setBusy(false); if (modal.open) closeModal(); ui.error = ''; haptic('heavy'); render(); window.scrollTo(0, 0);
    } catch (error) {
      setBusy(false); ui.error = friendlyError(error);
      const target = document.querySelector('#save-error'); if (target) target.textContent = ui.error; else toast(ui.error);
      // A definitive rejection permits editing. Network errors retain the exact
      // request and UUID so a lost successful response cannot duplicate a workout.
      if (['date_changed', 'weight_locked', 'exercise_not_configured', 'rest_not_available'].includes(error.code)) { s.pending = null; persistSession(); }
      if (s.pending) {
        modal.querySelectorAll('[data-action=rpe]').forEach(button => { button.disabled = true; });
        const retry = modal.querySelector('[data-action=save-workout]');
        if (retry) retry.textContent = tr('Повторить это сохранение', 'Retry this exact save');
      }
      render();
      if (['date_changed', 'weight_locked'].includes(error.code)) showModal('recover-session', `<h2 id="modal-title">${tr('Обновим план?', 'Update your session?')}</h2><p>${esc(ui.error)}</p><p>${tr('Подходы останутся на месте. Обновим дату и вес по твоему текущему плану.', 'Your sets will stay here. We’ll update the date and weight to match your current plan.')}</p><div class="modal-actions"><button class="button ink" data-action="refresh-date">${tr('Обновить и продолжить', 'Update and continue')}</button></div>`);
    }
  }
  async function submitForm(form) {
    if (ui.busy || !form.reportValidity()) return;
    const data = new FormData(form); let payload; let endpoint; let errorId;
    if (form.id === 'onboarding-form') { endpoint = 'onboarding'; errorId = 'onboarding-error'; payload = { name: data.get('name').trim(), max_pullups: Number(data.get('max_pullups')), language: data.get('language'), program_type: data.get('program_type') }; }
    else if (form.id === 'settings-form') { endpoint = 'settings'; errorId = 'settings-error'; payload = { name: data.get('name').trim(), language: data.get('language'), program_type: data.get('program_type'), notify_time: data.get('notify_time'), notify_workouts: data.has('notify_workouts') }; }
    else if (form.id === 'exercise-form') { endpoint = 'settings'; errorId = 'exercise-error'; const config = { max_reps: Number(data.get('max_reps')) }; if (data.has('weight_kg')) config.weight_kg = Number(data.get('weight_kg')); payload = { exercises: { [form.dataset.exercise]: config } }; }
    else if (form.id === 'edit-set-form') { const reps = Number(data.get('reps')); const index = Number(form.dataset.index); if (ui.session.pending) return; if (sum(ui.session.sets) - ui.session.sets[index] + reps > (state.limits.max_total_reps || 10000)) return toast(tr('Превышен лимит повторов.', 'Repetition limit exceeded.')); ui.session.sets[index] = reps; persistSession(); closeModal(); render(); return; }
    else return;
    const button = form.querySelector('button[type=submit]'); const oldText = button.innerHTML; button.disabled = true; button.innerHTML = `<span class="spinner"></span>${tr('Сохраняем…', 'Saving…')}`; ui.busy = true;
    try { const result = await api(endpoint, payload); state = result.state; if (endpoint === 'onboarding') ui.tab = 'today'; ui.busy = false; if (modal.open) closeModal(); render(); toast(tr('Готово. Всё сохранено.', 'Done. All saved.')); haptic(); }
    catch (error) { document.querySelector(`#${errorId}`).textContent = friendlyError(error); button.innerHTML = oldText; button.disabled = false; }
    finally { ui.busy = false; }
  }
  async function shareResult() {
    const r = ui.receipt; const text = `${demo ? tr('Демо · ', 'Demo · ') : ''}${tr('Турникмен', 'Turnikmen')} — ${nameOf(r.exercise)}: ${r.sessionReps ?? r.completed} ${tr('повторений', 'repetitions')}, +${r.xp_gained} XP. ${tr('Ещё на шаг сильнее.', 'One step stronger.')}`;
    try { if (navigator.share) await navigator.share({ title: tr('Моя тренировка', 'My workout'), text }); else if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); toast(tr('Результат скопирован — отправь его друзьям.', 'Result copied — share it with a friend.')); } else showModal('share', `<h2 id="modal-title">${tr('Твой результат', 'Your result')}</h2><p style="user-select:all;color:var(--ink)">${esc(text)}</p>`); } catch (error) { if (error.name !== 'AbortError') toast(tr('Не удалось поделиться. Попробуй ещё раз.', 'Couldn’t share. Try again.')); }
  }
  async function dispatch(button) {
    const action = button.dataset.action; if (button.disabled || ui.busy) return;
    if (action === 'home' || action === 'tab') { if (ui.session) return back(); ui.receipt = null; ui.tab = button.dataset.tab || 'today'; haptic(); render(); window.scrollTo(0, 0); }
    else if (action === 'select') { ui.selected = button.dataset.id; haptic(); render(); }
    else if (action === 'start') startSession();
    else if (action === 'setup') setupModal(button.dataset.id || ui.selected);
    else if (action === 'plan') showModal('plan', `<h2 id="modal-title">${tr('План на 7 дней', 'Your next 7 days')}</h2><p>${tr('Нагрузка волной: усилие, лёгкий день, восстановление.', 'Training comes in waves: effort, lighter days, recovery.')}</p><div class="planned-list">${state.week_plan.map(day => `<div class="planned-day"><div><strong>${esc(dayLabel(day.label || day.day_type))}</strong><small>${esc(dateText(day.date, { weekday: 'short', day: 'numeric', month: 'short' }))}</small></div><span>${day.is_rest ? tr('Восстановление', 'Recovery') : `${fmt(day.targets?.[ui.selected])} ${tr('повт.', 'reps')}`}</span></div>`).join('')}</div>`);
    else if (action === 'progress-tab') { ui.progressTab = button.dataset.tab; render(); }
    else if (action === 'history-more') { ui.historyLimit += 12; render(); }
    else if (action === 'theme') { ui.theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; applyTheme(); }
    else if (action === 'back') back();
    else if (action === 'close-modal') closeModal();
    else if (action === 'rep-plus') { setReps(number(document.querySelector('#rep-input').value) + 1); haptic(); }
    else if (action === 'rep-minus') { setReps(number(document.querySelector('#rep-input').value) - 1); haptic(); }
    else if (action === 'quick-reps') { setReps(Number(button.dataset.value)); haptic(); }
    else if (action === 'add-set') addSet();
    else if (action === 'undo' && !ui.session.pending) { ui.session.sets.pop(); persistSession(); render(); haptic(); }
    else if (action === 'edit-set') { const index = Number(button.dataset.index); showModal('edit-set', `<h2 id="modal-title">${tr('Подход', 'Set')} ${index + 1}</h2><p>${tr('Исправить число — это нормально.', 'It’s always okay to correct a number.')}</p><form id="edit-set-form" data-index="${index}"><div class="form-group"><label for="edit-reps">${tr('Повторения', 'Repetitions')}</label><input class="input" id="edit-reps" name="reps" type="number" inputmode="numeric" min="1" max="${state.limits.max_reps}" value="${ui.session.sets[index]}" required></div><div class="modal-actions"><button class="button ink" type="submit">${tr('Сохранить подход', 'Save set')}</button><button class="button danger" type="button" data-action="delete-set" data-index="${index}">${tr('Удалить подход', 'Delete set')}</button></div></form>`); }
    else if (action === 'delete-set' && !ui.session.pending) { ui.session.sets.splice(Number(button.dataset.index), 1); persistSession(); closeModal(); render(); }
    else if (action === 'rest-duration') { ui.restSeconds = Number(button.dataset.value); if (ui.session.restEnd) { ui.session.restEnd = Date.now() + ui.restSeconds * 1000; ui.session.restNotified = false; } persistSession(); render(); }
    else if (action === 'finish') { if (modal.open) closeModal(); if (ui.session.pending) await saveWorkout(); else rpeModal(); }
    else if (action === 'rpe') { ui.rpe = Number(button.dataset.value); modal.querySelectorAll('[data-action=rpe]').forEach(el => { const selected = Number(el.dataset.value) === ui.rpe; el.classList.toggle('selected', selected); el.setAttribute('aria-pressed', String(selected)); }); document.querySelector('#rpe-description').textContent = rpeDescription(); haptic(); }
    else if (action === 'save-workout') await saveWorkout();
    else if (action === 'discard') { ui.session = null; persistSession(); closingConfirmation(false); closeModal(); render(); }
    else if (action === 'done') { ui.receipt = null; ui.tab = 'today'; render(); window.scrollTo(0, 0); }
    else if (action === 'share') await shareResult();
    else if (action === 'rest') { if (ui.draft) return toast(tr('Сначала продолжи или удали незавершённую тренировку.', 'Resume or discard your unfinished workout first.')); showModal('rest', `<h2 id="modal-title">${tr('День для восстановления', 'A day to recharge')}</h2><p>${tr('Отдых поддерживает серию и продвигает план. Сегодня можно просто позаботиться о себе.', 'Rest keeps your streak and advances your plan. Today, just take care of yourself.')}</p><div class="modal-actions"><button class="button ink" data-action="save-rest">${icon('leaf')}${tr('Отдых завершён', 'Rest day complete')}</button></div>`); }
    else if (action === 'save-rest') { if (ui.draft) return toast(tr('Сначала продолжи или удали незавершённую тренировку.', 'Resume or discard your unfinished workout first.')); if (!ui.session || ui.session.exercise !== 'rest') ui.session = { id: uid(), exercise: 'rest', date: state.date, sets: [], weight: 0, pending: null }; ui.rpe = 0; await saveWorkout(); }
    else if (action === 'resume-draft') { ui.session = ui.draft; ui.draft = null; ui.restSeconds = [60, 75, 90].includes(ui.session.restSeconds) ? ui.session.restSeconds : 75; ui.rpe = ui.session.pending?.rpe ?? 6; ui.error = ui.session.date === state.date ? '' : tr('Черновик за другой день. При сохранении проверим, был ли он уже засчитан.', 'This draft is from another day. Saving checks whether it has already been counted.'); render(); window.scrollTo(0, 0); }
    else if (action === 'discard-draft') showModal('discard-draft', `<h2 id="modal-title">${tr('Удалить черновик?', 'Discard this draft?')}</h2><p>${tr('Несохранённые подходы исчезнут с этого устройства. Уже отправленная в бот тренировка останется в истории.', 'Unsaved sets will be removed from this device. A workout already sent to the bot will stay in your history.')}</p><div class="modal-actions"><button class="button secondary" data-action="close-modal">${tr('Оставить', 'Keep it')}</button><button class="button danger" data-action="confirm-discard-draft">${tr('Удалить черновик', 'Discard draft')}</button></div>`);
    else if (action === 'confirm-discard-draft') { ui.draft = null; persistSession(); closeModal(); render(); }
    else if (action === 'open-bot') { if (telegramAtLeast('6.1')) tg.openTelegramLink('https://t.me/turnikmen_challenge_bot'); else window.open('https://t.me/turnikmen_challenge_bot', '_blank', 'noopener,noreferrer'); }
    else if (action === 'resume') { ui.busy = true; try { state = (await api('onboarding', {})).state; render(); } catch (error) { toast(friendlyError(error)); } finally { ui.busy = false; render(); } }
    else if (action === 'refresh-date') { ui.busy = true; try { state = (await api('state')).state; ui.session.date = state.date; ui.session.id = uid(); ui.session.pending = null; const ex = state.exercises.find(item => item.id === ui.session.exercise); ui.session.doneBefore = number(ex?.today_completed); ui.session.planned = number(ex?.today_planned || ex?.base); ui.session.weight = number(ex?.weight_locked ? ex.today_weight_kg : ui.session.weight); persistSession(); ui.error = ''; ui.busy = false; closeModal(); render(); } catch (error) { toast(friendlyError(error)); } finally { ui.busy = false; } }
    else if (action === 'retry') await load();
    else if (action === 'reset-demo' && demo) { state = makeDemo(); ui.session = null; ui.receipt = null; ui.tab = 'today'; render(); }
    else if (action === 'demo-onboarding' && demo) { state.registered = false; state.telegram_user.first_name = ''; render(); window.scrollTo(0, 0); }
  }
  function makeDemo() {
    const date = keyDate(new Date());
    const exs = Object.keys(weights).map((id, i) => ({ id, configured: i < 4, weighted: id.includes('weighted'), base: [30, 60, 30, 90, 15, 24][i], weight_kg: i >= 4 ? 10 : 0, today_planned: [30, 60, 30, 90, 0, 0][i], today_completed: i === 0 ? 18 : 0, today_sets: i === 0 ? [6, 6, 6] : [], today_weight_kg: 0, weight_locked: false, personal_record: [36, 65, 32, 100, 0, 0][i], set_record: [12, 25, 12, 30, 0, 0][i] }));
    const history = [18, 42, 0, 30, 65, 24, 0, 32, 40, 18].flatMap((completed, i) => completed ? [{ date: dayShift(date, -i), exercise: i % 3 === 1 ? 'pushups' : 'pullups', completed, planned: i % 3 === 1 ? 60 : 30, sets: [Math.floor(completed / 3), Math.floor(completed / 3), completed - Math.floor(completed / 3) * 2], rpe: 6 + i % 3, weight_kg: 0, xp: Math.round(completed * (i % 3 === 1 ? .5 : 1)), day_type: 'Средний' }] : []);
    return { registered: true, date, timezone: 'UTC+05:00', language: 'ru', telegram_user: { first_name: 'Саша' }, user: { id: 'demo', name: 'Саша', xp: 1580, level: 2, level_name: 'Silver III', next_level_xp: 1800, level_progress: 72.5, streak: 7, max_streak: 12, freeze_tokens: 3, is_logged_out: false }, today: { day_type: 'Средний', label: 'Средний день', is_rest: false, completed: 18, planned: 30 }, exercises: exs, history, stats: { total_workouts: 47, total_reps: 1248, week_workouts: 5, week_reps: 179, week_xp: 158, totals: {} }, week_plan: Array.from({ length: 7 }, (_, i) => ({ date: dayShift(date, i), day_type: ['Средний', 'Лёгкий', 'Тяжёлый', 'Отдых', 'Плотность', 'Лёгкий', 'Отдых'][i], label: ['Средний', 'Лёгкий', 'Тяжёлый', 'Отдых', 'Плотность', 'Лёгкий', 'Отдых'][i], is_rest: i === 3 || i === 6, targets: Object.fromEntries(exs.map(ex => [ex.id, Math.round(ex.base * [1, .5, 1.15, 0, 1, .5, 0][i])])) })), leaderboard: [{ rank: 1, name: 'Мира', xp: 280, streak: 14, is_weekly_champ: true }, { rank: 2, name: 'Саша', xp: 158, streak: 7, is_me: true }, { rank: 3, name: 'Тимур', xp: 124, streak: 5 }], friends: [], settings: { name: 'Саша', language: 'ru', notify_time: '09:00', notify_workouts: true, program_type: 'standard' }, bot_session: { active: false }, limits: { max_sets: 50, max_reps: 500, max_weight_kg: 100, max_total_reps: 10000 } };
  }
  const demoReceipts = new Map();
  async function demoApi(endpoint, data) {
    if (endpoint === 'state') return { ok: true, state };
    if (endpoint === 'settings' || endpoint === 'onboarding') {
      if (endpoint === 'onboarding' && !state.registered) { state = makeDemo(); state.user.xp = 0; state.user.level = 0; state.user.level_name = 'Silver I'; state.user.next_level_xp = 500; state.user.level_progress = 0; state.user.streak = 0; state.user.max_streak = 0; state.history = []; state.stats = { total_workouts: 0, total_reps: 0, week_workouts: 0, week_reps: 0, week_xp: 0 }; state.exercises.forEach(ex => { ex.configured = ex.id === 'pullups'; ex.today_completed = 0; ex.today_sets = []; ex.personal_record = 0; ex.set_record = 0; }); state.exercises[0].base = Math.max(5, data.max_pullups * 3); state.exercises[0].today_planned = state.exercises[0].base; }
      ['name', 'language', 'program_type', 'notify_time', 'notify_workouts'].forEach(key => { if (data[key] !== undefined) state.settings[key] = data[key]; });
      state.language = state.settings.language; state.user.name = state.settings.name; state.registered = true; state.user.is_logged_out = false;
      Object.entries(data.exercises || {}).forEach(([id, config]) => { const ex = state.exercises.find(item => item.id === id); ex.base = Math.max(5, config.max_reps * 3); ex.configured = true; if (config.weight_kg !== undefined) ex.weight_kg = config.weight_kg; if (!ex.today_completed) ex.today_planned = ex.base; });
      return { ok: true, state };
    }
    if (endpoint === 'workout') {
      if (demoReceipts.has(data.session_id)) return { ok: true, receipt: demoReceipts.get(data.session_id), state };
      const count = sum(data.sets); const ex = state.exercises.find(item => item.id === data.exercise); const xp = Math.round(count * (weights[data.exercise] || 0) * (ex?.weighted ? 1 + Math.min(data.weight_kg, 50) * .03 : 1));
      if (ex) { ex.today_completed += count; ex.today_sets.push(...data.sets); ex.today_weight_kg = data.weight_kg; ex.weight_locked = ex.weighted; ex.personal_record = Math.max(ex.personal_record, ex.today_completed); }
      const existing = state.history.find(row => row.date === data.date && row.exercise === data.exercise);
      if (existing) { existing.completed += count; existing.sets.push(...data.sets); existing.xp += xp; existing.rpe = data.rpe; }
      else state.history.unshift({ date: data.date, exercise: data.exercise, completed: count, planned: ex?.today_planned || 0, sets: [...data.sets], rpe: data.rpe, weight_kg: data.weight_kg, xp, day_type: state.today.day_type });
      state.user.xp += xp; state.stats.total_reps += count; state.stats.total_workouts += 1; state.user.level_progress = pct(state.user.xp - (state.user.level === 0 ? 0 : 1000), state.user.level === 0 ? 500 : 800);
      const receipt = { session_id: data.session_id, exercise: data.exercise, date: data.date, completed: ex?.today_completed || 0, xp_gained: xp, xp_total: state.user.xp };
      demoReceipts.set(data.session_id, receipt); return { ok: true, receipt, state };
    }
    throw new Error('Unsupported demo action');
  }
  async function load() {
    app.setAttribute('aria-busy', 'true');
    try {
      if (!initData && telegramLaunch) { const error = new Error(tr('Не удалось подключиться к Telegram. Закрой приложение и открой его снова кнопкой в боте.', 'Could not connect to Telegram. Close the app and reopen it using the bot button.')); error.code = 'invalid_auth'; throw error; }
      state = demo ? makeDemo() : (await api('state')).state;
      restoreDraft();
      render();
    } catch (error) { app.setAttribute('aria-busy', 'false'); renderHeader(); nav.hidden = true; app.innerHTML = `<section class="error-screen"><div class="error-icon">${icon('alert')}</div><h1>${tr('Нужно немного времени.', 'Just a little moment.')}</h1><p role="alert">${esc(friendlyError(error))}</p><button class="button ink" data-action="retry">${tr('Попробовать снова', 'Try again')}</button></section>`; }
  }
  document.addEventListener('click', event => { const button = event.target.closest('[data-action]'); if (button) { event.preventDefault(); Promise.resolve(dispatch(button)).catch(error => toast(friendlyError(error))); } });
  document.addEventListener('submit', event => { event.preventDefault(); submitForm(event.target).catch(error => toast(friendlyError(error))); });
  document.addEventListener('change', event => { if (event.target.id === 'history-filter') { ui.filter = event.target.value; ui.historyLimit = 8; render(); } if (event.target.id === 'rep-input') setReps(event.target.value); });
  modal.addEventListener('cancel', event => { event.preventDefault(); closeModal(); });
  modal.addEventListener('click', event => { if (event.target === modal && event.clientY < modal.getBoundingClientRect().top) closeModal(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) updateTimer(); });
  setInterval(updateTimer, 500);
  try { if (!demo) { tg?.ready?.(); tg?.expand?.(); if (telegramAtLeast('6.1')) tg.BackButton.onClick(back); tg?.onEvent?.('themeChanged', applyTheme); } } catch {}
  matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', () => { if (demo && !ui.theme) applyTheme(); });
  applyTheme(); load();
})();
