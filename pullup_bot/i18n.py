from aiogram import F

STRINGS = {
    "ru": {
        # Buttons - main
        "btn_train": "🏋️ Тренировка",
        "btn_stats": "📊 Статистика",
        "btn_friends": "👥 Друзья",
        "btn_ai": "🤖 ИИ-совет",
        "btn_settings": "⚙️ Настройки",
        "btn_bug": "🐛 Сообщить о баге",
        "btn_back": "◀️ Назад",
        "btn_entrance": "◀️ Назад",
        # Buttons - landing
        "btn_login": "💪 Войти в Турникмен",
        "btn_about": "ℹ️ О боте",
        "btn_exit": "🚪 Выйти",
        # Buttons - training
        "btn_undo": "↩️ Отменить подход",
        "btn_manual": "✏️ Ввести вручную",
        "btn_finish": "✅ Завершить тренировку",
        "btn_cancel_train": "🚫 Отменить тренировку",
        "btn_skip": "⏭️ Пропустить",
        # Buttons - settings
        "btn_notify_time": "🔔 Время уведомлений",
        "btn_change_base": "📊 Изменить базу",
        "btn_change_weight": "⚖️ Изменить вес",
        "btn_edit_day": "📝 Редактировать день",
        "btn_skip_reason": "📅 Причина пропуска",
        "btn_logout": "🚪 Выйти из системы",
        "btn_language": "🌐 Язык / Language",
        # Start
        "welcome_intro": (
            "💪 *Турникмен*\n\n"
            "Привет! Я твой персональный тренер по подтягиваниям. Я помогу тебе следить за прогрессом, "
            "адаптировать план тренировок и не терять мотивацию. Давай начнём с регистрации или входа в систему!\n\n"
            "⚠️ _Бот на стадии Бета-тестирования. Возможны баги и недоработки. "
            "Если бот перестал работать, напишите в чате /start для перезапуска._⚠️\n\n"
            "Если вы нашли баг или у вас есть идеи как улучшить бота — напишите через кнопку:\n\n"
            "🐛 Сообщить о баге"
        ),
        "welcome": (
            "💪 *Турникмен*\n\n"
            "Привет! Я твой персональный тренер по подтягиваниям. Я помогу тебе следить за прогрессом, "
            "адаптировать план тренировок и не терять мотивацию. Давай начнём с регистрации или входа в систему!\n\n"
            "⚠️ _Бот на стадии Бета-тестирования. Возможны баги и недоработки. "
            "Если бот перестал работать, напишите в чате /start для перезапуска._⚠️\n\n"
            "Если вы нашли баг или у вас есть идеи как улучшить бота — напишите через кнопку:\n\n"
            "🐛 Сообщить о баге \n\n"
            "Выбери действие:"
        ),
        "about": (
            "💪 *Турникмен — персональный тренер по подтягиваниям*\n\n"
            "Бот помогает системно увеличить количество подтягиваний через "
            "умную прогрессию нагрузки.\n\n"
            "🔥 *Волновой 7-дневный цикл*\n"
            "Средний → Лёгкий → Тяжёлый → Отдых → Плотность → Лёгкий → Отдых\n"
            "Чередование нагрузки не даёт телу привыкнуть и ускоряет рост.\n\n"
            "📈 *Автоматическая прогрессия*\n"
            "После стабильного цикла база +5%. Если RPE высокий — нагрузка снижается, "
            "если низкий и всё выполняется — повышается. Бот адаптируется под тебя.\n\n"
            "⚖️ *Учёт веса тела*\n"
            "Вес используется ИИ-тренером для персонализации советов.\n\n"
            "📊 *RPE-оценка после каждой тренировки*\n"
            "Скользящее среднее за 3 сессии — план корректируется плавно, без резких скачков.\n\n"
            "🧊 *Токены заморозки*\n"
            "Если пропустил день — потрать токен, чтобы сохранить стрик.\n"
            "Заработать новый токен можно тремя способами:\n"
            "• 🔥 каждые 7 дней стрика подряд\n"
            "• ⬆️ при повышении уровня\n"
            "• 🏆 при новом личном рекорде\n"
            "Максимум — 5 токенов.\n\n"
            "🤖 *ИИ-тренер*\n"
            "Советы от Llama 3.3 70B (Groq) с учётом твоей истории, веса и стрика.\n\n"
            "🌱 *Бот — не волшебная таблетка*\n"
            "Турникмен даёт тебе структуру и мотивацию, но результат строится на фундаменте. "
            "Высыпайся, ешь достаточно белка, давай мышцам восстанавливаться и береги здоровье. "
            "Бот — это мощный инструмент поверх твоего уже правильного образа жизни. "
            "Сложи их вместе — и прогресс не заставит себя ждать. 💪\n\n"
            "⚠️ _Бот в стадии бета-тестирования._"
        ),
        "btn_guide": "📖 Как начать",
        "btn_guide_step1": "Шаг 1 →",
        "btn_guide_step2": "Шаг 2 →",
        "btn_guide_step3": "Шаг 3 →",
        "btn_guide_step4": "Шаг 4 →",
        "btn_guide_extra": "Дополнительно →",
        "guide_intro": (
            "📖 *Руководство для новичка*\n\n"
            "Бот помогает систематически увеличивать количество подтягиваний. "
            "Он строит план, отслеживает прогресс и адаптирует нагрузку под тебя."
        ),
        "guide_step1": (
            "📋 *Шаг 1 — Регистрация*\n\n"
            "1. Нажми «💪 Войти в Турникмен»\n"
            "2. Введи секретный код _(получи у организатора)_\n"
            "3. Укажи имя и вес\n"
            "4. Укажи дневную норму подтягиваний _(например: 80)_\n"
            "5. Укажи день программы _(1 — если только начинаешь)_"
        ),
        "guide_step2": (
            "📅 *Шаг 2 — Ежедневный план*\n\n"
            "Бот чередует нагрузку по 7-дневному циклу:\n"
            "• Средний — ~100% нормы\n"
            "• Лёгкий — ~60–70% нормы\n"
            "• Тяжёлый — ~120–130% нормы\n"
            "• Отдых — восстановление\n"
            "• Плотность — много коротких подходов"
        ),
        "guide_step3": (
            "🏋️ *Шаг 3 — Тренировка*\n\n"
            "1. Нажми «🏋️ Тренировка»\n"
            "2. Делай подходы — нажимай на цифры или «✏️ Ввести вручную»\n"
            "3. Нажми «✅ Завершить тренировку» когда закончишь"
        ),
        "guide_step4": (
            "📊 *Шаг 4 — RPE (оценка усилия)*\n\n"
            "После тренировки бот спросит: насколько тяжело было?\n"
            "1–3 = легко · 4–6 = нормально · 7–8 = тяжело · 9–10 = на пределе\n\n"
            "Бот использует эти оценки чтобы корректировать план автоматически."
        ),
        "guide_extra": (
            "🔥 *Стрик и токены заморозки*\n\n"
            "Стрик — количество дней подряд с тренировкой. Не прерывай его!\n"
            "Если пропустил день — потрать токен заморозки, чтобы сохранить серию.\n\n"
            "Как заработать новый токен заморозки:\n"
            "• 🔥 каждые 7 дней стрика подряд — автоматически\n"
            "• ⬆️ при повышении уровня — после тренировки\n"
            "• 🏆 при новом личном рекорде по подтягиваниям\n"
            "_(максимум 5 токенов)_\n\n"
            "📈 *Статистика и история*\n\n"
            "• «📊 Статистика» — прогресс, XP, уровень, стрик\n"
            "• «🗓 История» — все прошлые тренировки по неделям\n\n"
            "🤖 *ИИ-тренер*\n\n"
            "Нажми «🤖 ИИ-совет» — получи совет с учётом твоей истории, веса и стрика.\n\n"
            "💡 *Совет*\n\n"
            "Начни с консервативной нормы (50–80 подтягиваний в день). "
            "Бот сам повысит её, когда ты будешь готов."
        ),
        "bye": "👋 Ты вышел из аккаунта.\n\n⏸ Уведомления и стрик поставлены на паузу.\nДанные сохранены — нажми «Войти в Турникмен», чтобы вернуться 💪",
        "main_menu": "👋 Главное меню:",
        "register_first": "Сначала зарегистрируйся — /start",
        "nothing_to_cancel": "Нечего отменять.",
        "cancelled": "❌ Действие отменено.",
        # Login / Registration
        "enter_secret": "Введи секретный код для регистрации:\n_(/cancel — отменить)_",
        "wrong_code": "❌ Неверный код. Попробуй ещё раз: ({attempts} из 3)",
        "wrong_code_locked": "🔒 Слишком много попыток. Попробуй снова через 1 час.",
        "poke_already_today": "⏳ Ты уже отправил мотивацию {name} сегодня. Можно снова завтра.",
        "code_accepted": "✅ Код принят!\n\nКак тебя зовут?\n_(Введите минимум 3 символа)_",
        "hello_name": "👋 Привет, *{name}*!\n\nВведи свой вес в кг:\n_Можно изменить позже в настройках._",
        "enter_base": "Сколько подтягиваний твоя *дневная норма*?",
        "enter_start_day": (
            "Какой сейчас *день программы*?\n\n"
            "_(1 — если это твой первый день тренировок на турнике\n"
            "22 — если ты уже 22 дня в программе\n\n"
            "Это нужно чтобы бот знал на каком этапе цикла ты находишься.\n"
            "Можно изменить позже в Настройках.)_"
        ),
        "welcome_user": "🎉 *Добро пожаловать, {name}!*\n\nНорма: *{base}* подтягиваний\nУровень: {level} — начинаем! 💪",
        "welcome_back": "👋 С возвращением, *{name}*!\n\nУровень: {level} ⭐ XP: {xp}\n🔥 Стрик: {streak} дней",
        "enter_number": "❌ Введи число, например: {example}",
        # Training
        "train_day": "{'🟢' if day_type != 'Отдых' else '😴'} *{day_type} день*",
        "train_goal": "🎯 Цель: *{planned}* подтягиваний",
        "train_done_today": "✅ Сделано за сегодня: *{done}*",
        "train_done_now": "🏋️ Сделано сейчас: *{done}*",
        "train_in_progress": "🏋️ *Тренировка идёт...*\n_Нажми на число или введи вручную:_",
        "train_no_sets": "❌ Нечего отменять — подходов ещё нет.",
        "train_enter_reps": "Введи количество повторений в подходе:",
        "train_rate_rpe": "Оцени по шкале от 1 до 10, насколько тяжелыми были подтягивания:\n1 = очень легко · 10 = полный отказ",
        "train_rpe_invalid": "❌ Введи число 1-10 или нажми ⏭️ Пропустить.",
        "train_extra_activity": "Была ли дополнительная активность сегодня?\n_(бег, зал, кардио — повлияет на план завтра)_",
        "train_how_long": "Сколько минут занял *{act}*? (например: 45)",
        "train_enter_mins": "❌ Введи число минут:",
        "train_cancelled": "🚫 Тренировка отменена.",
        "train_confirm_cancel": "⚠️ Уверены что хотите отменить?\n\nВы потеряете *{done}* подтягиваний за {sets} подходов.",
        "train_yes_cancel": "❌ Да, отменить тренировку",
        "train_continue": "↩️ Нет, продолжить тренировку",
        "train_already_done": "Тренировка уже завершена.",
        "train_lets_go": "💪 Продолжаем!",
        "train_reduction": "\n⬇️ Снижено {pct}% за вчерашнюю активность",
        "train_complete": (
            "{em} *Тренировка завершена!*\n\n"
            "📊 Сделано: *{done}* / {planned} ({pct})\n"
            "📦 Подходов: {sets}\n"
            "💪 RPE: {rpe}/10{rpe_comment}\n\n"
            "⭐ XP: +{xp_gained} (всего {xp_total})\n"
            "🏅 Уровень: {level} [{bar}] {to_next} до след.\n"
            "🔥 Стрик: {streak} дней"
        ),
        "train_extra_note": "\n🏃 Доп. активность: {act} {mins} мин",
        "train_rpe_trending_high": "\n⚠️ Средний RPE {avg:.1f} за 3 сессии — нагрузка слишком высокая. База снижена до {base} (−5%).",
        "train_rpe_trending_low": "\n🚀 Средний RPE {avg:.1f} за 3 сессии — форма отличная! База повышена до {base} (+3%).",
        "train_progression": "\n🎯 Цикл завершён! Стабильный прогресс — база повышена до {base} (+5%).",
        "density_hint": "💡 _День плотности: много коротких подходов, минимум отдыха между ними. Цель — набрать объём равномерно в течение дня._",
        "train_friend_notify": "📣 *{name}* завершил тренировку!\n🎯 Цель: {planned} | Выполнено: {done} | Подходов: {sets}",
        # Rest day override
        "rest_day_prompt": "😴 Сегодня день отдыха. Что хочешь сделать?",
        "rest_day_train": "💪 Тренироваться",
        "rest_day_rest": "😴 Отдыхать",
        # Stats
        "stats_title": "📊 *Статистика — {name}*",
        # Friends
        "friends_title": "👥 *Все участники:*",
        "friends_empty": "👥 *Участники*\n\nПока никого нет — ты первый! 💪",
        "friends_poke_sent": "✅ Мотивация другу {name} отправлена! 💪",
        "friends_not_found": "❌ Участник не найден.",
        "friends_blocked": "❌ Пользователь заблокировал бота.",
        "friends_error": "❌ Не удалось отправить.",
        # AI
        "ai_thinking": "🤖 Анализирую твои данные...",
        "ai_no_data": "Сначала запиши несколько тренировок!",
        "ai_unavailable": "⚠️ ИИ временно недоступен.",
        "ai_system_prompt": (
            "Ты персональный тренер по подтягиваниям. Анализируй данные атлета и давай "
            "конкретные, персонализированные советы на русском языке (4-5 предложений). "
            "Учитывай вес тела, усталость по RPE, стрик и тип завтрашнего дня. "
            "Будь прямым, мотивирующим и честным. Не давай общих советов."
        ),
        "ai_user_prompt": (
            "Атлет: {name}, вес {weight}кг\n"
            "Стрик: {streak} дней | Уровень: {level} | База: {base} подтяг/день\n"
            "День программы: {program_day} | Завтра: {next_day}\n\n"
            "Последние тренировки:\n{summary}\n\n"
            "Дай конкретный совет с учётом всех данных — что делать завтра и почему."
        ),
        # Settings
        "settings_title": "⚙️ *Настройки*\n\nБаза: {base} подтягиваний\nВес: {weight} кг\nУведомления: {notify}\nЗаморозок: {freeze}",
        "set_time_prompt": "Текущее время уведомлений: *{current}*\n\nВведи новое время в формате *ЧЧ:ММ* (например: 09:00):",
        "set_time_ok": "✅ Напоминания в *{time}*",
        "set_time_bad": "❌ Неверный формат. Введи как: 09:00",
        "set_base_prompt": "Текущая норма: *{base}* подтягиваний/день\n\nВведи новое значение:",
        "set_base_ok": "✅ Норма обновлена: *{base}* подтягиваний/день",
        "set_base_range": "❌ Введи число от 1 до 2000:",
        "set_weight_prompt": "Текущий вес: *{weight}* кг\n\nВведи новый вес:",
        "set_weight_ok": "✅ Вес обновлён: *{weight}* кг",
        "set_weight_range": "❌ Введи вес от 30 до 300 кг:",
        "edit_date_prompt": "Введи дату в формате *ДД.ММ*:",
        "edit_date_bad": "❌ Неверный формат. Введи как: 14.03",
        "edit_done_prompt": "Сколько подтягиваний сделано *{date}*?",
        "edit_rpe_prompt": "Оцени RPE (1-10) для того дня:",
        "edit_ok": "✅ День *{date}* обновлён: {done} подтягиваний, RPE {rpe}",
        "edit_deleted": "🗑 Тренировка за *{date}* удалена.",
        "edit_no_date": "❌ Ошибка: дата не найдена.",
        "edit_ask_extras": "Добавить дополнительную активность и заметки к этой тренировке?",
        "btn_yes_add": "✅ Да, добавить",
        "btn_no_save": "⏭️ Нет, сохранить",
        "skip_date_prompt": "За какую дату добавить причину? Формат *ДД.ММ*:\n_(до 3 дней назад)_",
        "skip_date_range": "❌ Можно добавить причину только за последние 3 дня.",
        "skip_choose_reason": "Выбери причину:",
        "skip_ok": "✅ Причина добавлена за *{date}*: {reason}\n🔥 Стрик восстановлен!",
        "skip_day_msg": "📅 День пропущен. Стрик сброшен.\n💪 Начни заново завтра!",
        "freeze_ok": "🧊 Стрик заморожен! Осталось заморозок: {tokens}",
        "freeze_none": "❌ Нет заморозок!",
        # Skip reasons
        "reason_study": "📚 Учёба/работа",
        "reason_sick": "🤒 Болезнь",
        "reason_overtrain": "😴 Перетренированность",
        "reason_travel": "✈️ Путешествие",
        "reason_weather": "🌧 Погода",
        "reason_gym": "💪 Тренировка в зале",
        # Bug reports
        "bug_prompt": "🐛 *Сообщить о баге / Предложить улучшение*\n\nЕсли вы нашли баг или у вас есть идеи как улучшить бота — опишите здесь:\n— Что случилось или что хотите предложить?\n— Если баг: что делали и что пошло не так?\n\n_/cancel — отменить_",
        "bug_ok": "✅ *Спасибо! Баг отправлен.* 🙏",
        "bug_enter_text": "❌ Введи описание бага.",
        # Confirm
        "confirm_logout": "⚠️ Уверен, что хочешь выйти?",
        "confirm_yes": "✅ Да",
        "confirm_no": "❌ Отмена",
        # Account deletion
        "btn_change_name": "✏️ Изменить имя",
        "set_name_prompt": "Текущее имя: *{name}*\n\nВведи новое имя:",
        "set_name_ok": "✅ Имя изменено на *{name}*",
        "set_name_bad": "❌ Имя не может быть пустым.",
        "btn_delete_account": "🗑 Удалить аккаунт",
        "delete_account_warning": (
            "⚠️ *Удаление аккаунта*\n\n"
            "Это действие удалит *все твои данные*:\n"
            "тренировки, стрик, уровень, XP, заметки — всё.\n\n"
            "Отменить невозможно.\n\n"
            "Вернуться можно в любой момент — просто введи секретный код снова."
        ),
        "delete_confirm_yes": "🗑 Да, удалить всё",
        "delete_confirm_no": "◀️ Отмена",
        "delete_account_done": "✅ Аккаунт удалён. Все данные стёрты.\n\nЕсли захочешь вернуться — введи /start и секретный код. 💪",
        # Help
        "help": (
            "📖 *Команды бота:*\n\n"
            "/start — главное меню\n"
            "/cancel — отменить текущее действие\n"
            "/edit — редактировать прошлый день\n"
            "/help — список команд\n"
            "/version — версия бота (admin)\n"
            "/bugs — баг-репорты (admin)\n"
            "/fixbug — закрыть баг (admin)"
        ),
        # Reminders
        "reminder_rest": "😴 Сегодня день отдыха. Восстанавливайся!",
        "reminder_train": "🔔 Не забудь про подтягивания!\n📋 {day_type} день: {planned} подтягиваний\n{status}",
        "reminder_done": "✅ Сделано: {done}",
        "reminder_not_started": "⏳ Ещё не начинал",
        # Language
        "lang_prompt": "🌐 Выбери язык / Choose language:",
        "lang_ok": "✅ Язык: Русский 🇷🇺",
        # History browser
        "btn_history": "📋 История",
        "history_title": "📋 *История — {date_from}–{date_to}*",
        "history_week_total": "📊 Неделя: {done}/{planned} ({pct}%)",
        "history_no_data": "📋 *История*\n\nНет записей.",
        "history_no_week_data": "📋 *История*\n\nПока нет данных за эту неделю.\nЗавершишь несколько тренировок — и здесь появится статистика 💪",
        "history_empty_day": "нет данных",
        # Poke messages
        "poke_msgs": [
            "💪 Вставай на турник! Тебя ждёт прогресс!",
            "🔥 Не забудь про подтягивания! Ты можешь!",
            "⚡ Враг отдыхает пока ты лежишь на диване 😈",
            "🏆 Один подтяг уже лучше нуля. Начни!",
            "💥 Стрик не сам себя поддержит — вперёд!",
        ],
        # New user broadcast
        "new_user_joined": "👋 *{name}* присоединился к Турникмен! Поприветствуйте! 💪",
        "welcome_greet_sent": "Вы поприветствовали {name}, мотивашка отправлена👌.",
        "welcome_greet_received": "{name} поприветствовал вас! Теперь вы в команде турникменов💪!",
        "welcome_greet_already": "Вы уже поприветствовали {name}.",
        "welcome_greet_missing": "Не удалось отправить приветствие: пользователь недоступен.",
        "welcome_greet_self": "Себя приветствовать не нужно 😄",
        # Personal record
        "personal_best": "🏆 Рекорд",
        "new_pr": "\n\n🏆 *Новый рекорд дня: {done} подтягиваний!* 🎉",
        # Workout notes
        "train_notes_prompt": "📝 Заметки к тренировке?\n_(Что чувствовал, условия, мысли — любой текст)_",
        "train_skip_notes": "⏭️ Без заметок",
        "train_saving": "⏳ Сохраняю...",
        # Upcoming schedule
        "stats_schedule_title": "📅 *Ближайшие 7 дней:*",
        "stats_schedule_rest": "😴 Отдых",
        # Progress chart
        "stats_chart_title": "📈 *График (7 дней):*",
        # Weekly summary
        "weekly_summary_title": "📊 *Итоги недели*",
        "weekly_summary_body": (
            "🏋️ Подтягиваний: *{done}* / {planned} ({pct}%)\n"
            "🔥 Лучший день: {best_day} — {best_done} подтяг\n"
            "💪 Средний RPE: {avg_rpe}\n"
            "🔥 Стрик: *{streak}* дней\n"
            "🧊 Заморозок: {freeze}"
        ),
        "weekly_summary_no_workouts": "📊 На прошлой неделе тренировок не было. Не сдавайся! 💪",
        # Freeze token mechanic
        "freeze_prompt": "🧊 Стрик вот-вот прервётся!\n\nИспользовать заморозку чтобы сохранить стрик?\n_(Осталось заморозок: {tokens})_",
        "freeze_yes_btn": "🧊 Да, заморозить",
        "freeze_no_btn": "❌ Нет, сбросить",
        "freeze_used": "🧊 Заморозка использована! Стрик *{streak}* дней сохранён.\nОсталось заморозок: {tokens}",
        "freeze_empty": "❌ Нет заморозок. Стрик сброшен. Начни заново! 💪",
        "token_earned_level": "\n\n🧊 *+1 заморозка* — за повышение уровня! _(всего: {tokens})_",
        "token_earned_streak": "\n\n🧊 *+1 заморозка* — за {streak} дней стрика подряд! _(всего: {tokens})_",
        "token_earned_pr": "\n\n🧊 *+1 заморозка* — за новый личный рекорд! _(всего: {tokens})_",
        # Leaderboard
        "btn_leaderboard": "🏆 Рейтинг",
        "leaderboard_title": "🏆 *Рейтинг — неделя*",
        "leaderboard_empty": "🏆 *Рейтинг*\n\nПока никого нет — ты первый! 💪",
        "leaderboard_you_marker": " ← ты",
    },
    "en": {
        # Buttons - main
        "btn_train": "🏋️ Training",
        "btn_stats": "📊 Statistics",
        "btn_friends": "👥 Friends",
        "btn_ai": "🤖 AI Advice",
        "btn_settings": "⚙️ Settings",
        "btn_bug": "🐛 Report a Bug",
        "btn_back": "◀️ Back",
        "btn_entrance": "◀️ Back",
        # Buttons - landing
        "btn_login": "💪 Join Pullup Pro",
        "btn_about": "ℹ️ About",
        "btn_exit": "🚪 Exit",
        # Buttons - training
        "btn_undo": "↩️ Undo Set",
        "btn_manual": "✏️ Enter Manually",
        "btn_finish": "✅ Finish Training",
        "btn_cancel_train": "🚫 Cancel Training",
        "btn_skip": "⏭️ Skip",
        # Buttons - settings
        "btn_notify_time": "🔔 Notification Time",
        "btn_change_base": "📊 Change Base",
        "btn_change_weight": "⚖️ Change Weight",
        "btn_edit_day": "📝 Edit Day",
        "btn_skip_reason": "📅 Skip Reason",
        "btn_logout": "🚪 Log Out",
        "btn_language": "🌐 Язык / Language",
        # Start
        "welcome_intro": (
            "💪 *Pullup Pro*\n\n"
            "Hey! I'm your personal pullup coach. I'll help you track progress, "
            "adapt your training plan, and stay motivated. Let's start with registration!\n\n"
            "⚠️ _Bot is in Beta. Bugs are possible. "
            "If the bot stops working, type /start to restart._⚠️\n\n"
            "Found a bug? Report it via: \n\n"
            "🐛 Report a Bug"
        ),
        "welcome": (
            "💪 *Pullup Pro*\n\n"
            "Hey! I'm your personal pullup coach. I'll help you track progress, "
            "adapt your training plan, and stay motivated. Let's start with registration!\n\n"
            "⚠️ _Bot is in Beta. Bugs are possible. "
            "If the bot stops working, type /start to restart._⚠️\n\n"
            "Found a bug? Report it via: \n\n"
            "🐛 Report a Bug \n\n"
            "Choose an action:"
        ),
        "about": (
            "💪 *Pullup Pro — personal pullup coach*\n\n"
            "The bot helps you systematically increase your pullup count "
            "through smart progressive overload.\n\n"
            "🔥 *7-day wave cycle*\n"
            "Medium → Light → Heavy → Rest → Density → Light → Rest\n"
            "Alternating load prevents adaptation and accelerates growth.\n\n"
            "📈 *Automatic progression*\n"
            "After a stable cycle your base goes up 5%. High RPE reduces load, "
            "low RPE with full completion raises it. The bot adapts to you.\n\n"
            "⚖️ *Body weight tracking*\n"
            "Your weight is used by the AI coach to personalize advice.\n\n"
            "📊 *RPE rating after every session*\n"
            "3-session rolling average — plan adjusts smoothly, no sudden spikes.\n\n"
            "🧊 *Freeze tokens*\n"
            "Miss a day? Spend a token to protect your streak.\n"
            "Earn new tokens three ways:\n"
            "• 🔥 every 7-day streak milestone\n"
            "• ⬆️ each time you level up\n"
            "• 🏆 when you set a new personal record\n"
            "Maximum 5 tokens.\n\n"
            "🤖 *AI coach*\n"
            "Advice from Llama 3.3 70B (Groq) based on your history, weight and streak.\n\n"
            "🌱 *This bot is not a magic pill*\n"
            "Turnikmen gives you structure and keeps you accountable, but real progress is built on a solid foundation. "
            "Sleep well, eat enough protein, let your muscles recover, and take care of your body. "
            "Think of this bot as a powerful tool on top of an already healthy lifestyle — "
            "combine the two and the results will speak for themselves. 💪\n\n"
            "⚠️ _Bot is in beta testing._"
        ),
        "btn_guide": "📖 Getting Started",
        "btn_guide_step1": "Step 1 →",
        "btn_guide_step2": "Step 2 →",
        "btn_guide_step3": "Step 3 →",
        "btn_guide_step4": "Step 4 →",
        "btn_guide_extra": "More →",
        "guide_intro": (
            "📖 *Beginner's Guide*\n\n"
            "The bot helps you systematically increase your pullup count. "
            "It builds your plan, tracks progress, and automatically adapts load to you."
        ),
        "guide_step1": (
            "📋 *Step 1 — Registration*\n\n"
            "1. Tap «💪 Join Pullup Pro»\n"
            "2. Enter the secret code _(get it from your organizer)_\n"
            "3. Enter your name and weight\n"
            "4. Enter your daily pullup target _(e.g.: 80)_\n"
            "5. Enter your program day _(1 if you're just starting out)_"
        ),
        "guide_step2": (
            "📅 *Step 2 — Your Daily Plan*\n\n"
            "The bot alternates load on a 7-day wave cycle:\n"
            "• Medium — ~100% of your target\n"
            "• Light — ~60–70% of your target\n"
            "• Heavy — ~120–130% of your target\n"
            "• Rest — recovery day\n"
            "• Density — many short sets"
        ),
        "guide_step3": (
            "🏋️ *Step 3 — Training*\n\n"
            "1. Tap «🏋️ Training»\n"
            "2. Do sets — tap the numbers or «✏️ Enter Manually»\n"
            "3. Tap «✅ Finish Training» when done"
        ),
        "guide_step4": (
            "📊 *Step 4 — RPE (Effort Rating)*\n\n"
            "After each session the bot asks: how hard was it?\n"
            "1–3 = easy · 4–6 = moderate · 7–8 = hard · 9–10 = near maximum\n\n"
            "The bot uses these ratings to automatically adjust your plan."
        ),
        "guide_extra": (
            "🔥 *Streak & Freeze Tokens*\n\n"
            "Your streak counts days trained in a row. Keep it alive!\n"
            "Miss a day? Use a freeze token to protect your streak.\n\n"
            "How to earn new freeze tokens:\n"
            "• 🔥 every 7-day streak milestone — automatically\n"
            "• ⬆️ each time you level up — after a workout\n"
            "• 🏆 when you set a new personal record\n"
            "_(maximum 5 tokens)_\n\n"
            "📈 *Stats & History*\n\n"
            "• «📊 Statistics» — progress, XP, level, streak\n"
            "• «🗓 History» — all past workouts by week\n\n"
            "🤖 *AI Coach*\n\n"
            "Tap «🤖 AI Advice» for personalized coaching based on your history, weight, and streak.\n\n"
            "💡 *Tip*\n\n"
            "Start with a conservative target (50–80 pullups per day). "
            "The bot will raise it automatically when you're ready."
        ),
        "bye": "👋 You've logged out.\n\n⏸ Notifications and streak are paused.\nYour data is saved — tap «Join Turnikmen» to come back 💪",
        "main_menu": "👋 Main menu:",
        "register_first": "Register first — /start",
        "nothing_to_cancel": "Nothing to cancel.",
        "cancelled": "❌ Action cancelled.",
        # Login / Registration
        "enter_secret": "Enter the secret code to register:\n_(/cancel to cancel)_",
        "wrong_code": "❌ Wrong code. Try again: ({attempts} of 3)",
        "wrong_code_locked": "🔒 Too many attempts. Try again in 1 hour.",
        "poke_already_today": "⏳ You already sent motivation to {name} today. Try again tomorrow.",
        "code_accepted": "✅ Code accepted!\n\nWhat's your name?\n_(Enter at least 3 characters)_",
        "hello_name": "👋 Hi, *{name}*!\n\nEnter your weight in kg:\n_You can change it later in settings._",
        "enter_base": "What's your *daily pullup target*?",
        "enter_start_day": (
            "What *program day* are you on?\n\n"
            "_(1 — if this is your very first day of pullup training\n"
            "22 — if you've already been training for 22 days\n\n"
            "This tells the bot where you are in the wave cycle.\n"
            "You can change it later in Settings.)_"
        ),
        "welcome_user": "🎉 *Welcome, {name}!*\n\nTarget: *{base}* pullups\nLevel: {level} — let's go! 💪",
        "welcome_back": "👋 Welcome back, *{name}*!\n\nLevel: {level} ⭐ XP: {xp}\n🔥 Streak: {streak} days",
        "enter_number": "❌ Enter a number, e.g.: {example}",
        # Training
        "train_day": "{'🟢' if day_type != 'Rest' else '😴'} *{day_type} day*",
        "train_goal": "🎯 Goal: *{planned}* pullups",
        "train_done_today": "✅ Done today: *{done}*",
        "train_done_now": "🏋️ Done now: *{done}*",
        "train_in_progress": "🏋️ *Training in progress...*\n_Tap a number or enter manually:_",
        "train_no_sets": "❌ Nothing to undo — no sets yet.",
        "train_enter_reps": "Enter the number of reps:",
        "train_rate_rpe": "Rate from 1 to 10 how hard the pullups were:\n1 = very easy · 10 = total failure",
        "train_rpe_invalid": "❌ Enter a number 1-10 or tap ⏭️ Skip.",
        "train_extra_activity": "Any extra activity today?\n_(running, gym, cardio — affects tomorrow's plan)_",
        "train_how_long": "How many minutes was *{act}*? (e.g.: 45)",
        "train_enter_mins": "❌ Enter number of minutes:",
        "train_cancelled": "🚫 Training cancelled.",
        "train_confirm_cancel": "⚠️ Are you sure you want to cancel?\n\nYou'll lose *{done}* pullups from {sets} sets.",
        "train_yes_cancel": "❌ Yes, cancel training",
        "train_continue": "↩️ No, continue training",
        "train_already_done": "Training already finished.",
        "train_lets_go": "💪 Let's go!",
        "train_reduction": "\n⬇️ Reduced {pct}% due to yesterday's activity",
        "train_complete": (
            "{em} *Training complete!*\n\n"
            "📊 Done: *{done}* / {planned} ({pct})\n"
            "📦 Sets: {sets}\n"
            "💪 RPE: {rpe}/10{rpe_comment}\n\n"
            "⭐ XP: +{xp_gained} (total {xp_total})\n"
            "🏅 Level: {level} [{bar}] {to_next} to next\n"
            "🔥 Streak: {streak} days"
        ),
        "train_extra_note": "\n🏃 Extra activity: {act} {mins} min",
        "train_rpe_trending_high": "\n⚠️ Avg RPE {avg:.1f} over 3 sessions — load too high. Base reduced to {base} (−5%).",
        "train_rpe_trending_low": "\n🚀 Avg RPE {avg:.1f} over 3 sessions — great form! Base raised to {base} (+3%).",
        "train_progression": "\n🎯 Cycle complete! Consistent progress — base raised to {base} (+5%).",
        "density_hint": "💡 _Density day: many short sets, minimal rest between them. Goal — accumulate volume spread throughout the day._",
        "train_friend_notify": "📣 *{name}* finished training!\n🎯 Goal: {planned} | Done: {done} | Sets: {sets}",
        # Rest day override
        "rest_day_prompt": "😴 Today is a rest day. What do you want to do?",
        "rest_day_train": "💪 Train anyway",
        "rest_day_rest": "😴 Rest",
        # Stats
        "stats_title": "📊 *Statistics — {name}*",
        # Friends
        "friends_title": "👥 *All participants:*",
        "friends_empty": "👥 *Participants*\n\nNo one yet — you're the first! 💪",
        "friends_poke_sent": "✅ Motivation sent to {name}! 💪",
        "friends_not_found": "❌ Participant not found.",
        "friends_blocked": "❌ User blocked the bot.",
        "friends_error": "❌ Failed to send.",
        # AI
        "ai_thinking": "🤖 Analyzing your data...",
        "ai_no_data": "Log some workouts first!",
        "ai_unavailable": "⚠️ AI is temporarily unavailable.",
        "ai_system_prompt": (
            "You are a personal pullup coach. Analyze the athlete's data and give "
            "specific, personalized advice in English (4-5 sentences). "
            "Consider body weight, fatigue from RPE, streak, and tomorrow's session type. "
            "Be direct, motivating and honest. No generic tips."
        ),
        "ai_user_prompt": (
            "Athlete: {name}, weight {weight}kg\n"
            "Streak: {streak} days | Level: {level} | Base: {base} pullups/day\n"
            "Program day: {program_day} | Tomorrow: {next_day}\n\n"
            "Recent workouts:\n{summary}\n\n"
            "Give specific advice considering all the data — what to do tomorrow and why."
        ),
        # Settings
        "settings_title": "⚙️ *Settings*\n\nBase: {base} pullups\nWeight: {weight} kg\nNotifications: {notify}\nFreezes: {freeze}",
        "set_time_prompt": "Current notification time: *{current}*\n\nEnter new time as *HH:MM* (e.g.: 09:00):",
        "set_time_ok": "✅ Reminders at *{time}*",
        "set_time_bad": "❌ Invalid format. Enter as: 09:00",
        "set_base_prompt": "Current target: *{base}* pullups/day\n\nEnter new value:",
        "set_base_ok": "✅ Target updated: *{base}* pullups/day",
        "set_base_range": "❌ Enter a number from 1 to 2000:",
        "set_weight_prompt": "Current weight: *{weight}* kg\n\nEnter new weight:",
        "set_weight_ok": "✅ Weight updated: *{weight}* kg",
        "set_weight_range": "❌ Enter weight from 30 to 300 kg:",
        "edit_date_prompt": "Enter date as *DD.MM*:",
        "edit_date_bad": "❌ Invalid format. Enter as: 14.03",
        "edit_done_prompt": "How many pullups done on *{date}*?",
        "edit_rpe_prompt": "Rate RPE (1-10) for that day:",
        "edit_ok": "✅ Day *{date}* updated: {done} pullups, RPE {rpe}",
        "edit_deleted": "🗑 Workout for *{date}* deleted.",
        "edit_no_date": "❌ Error: date not found.",
        "edit_ask_extras": "Add extra activity and notes to this session?",
        "btn_yes_add": "✅ Yes, add",
        "btn_no_save": "⏭️ No, save",
        "skip_date_prompt": "For which date? Format *DD.MM*:\n_(up to 3 days ago)_",
        "skip_date_range": "❌ Can only add reason for the last 3 days.",
        "skip_choose_reason": "Choose a reason:",
        "skip_ok": "✅ Reason added for *{date}*: {reason}\n🔥 Streak restored!",
        "skip_day_msg": "📅 Day skipped. Streak reset.\n💪 Start again tomorrow!",
        "freeze_ok": "🧊 Streak frozen! Freezes left: {tokens}",
        "freeze_none": "❌ No freezes left!",
        # Skip reasons
        "reason_study": "📚 Study/Work",
        "reason_sick": "🤒 Illness",
        "reason_overtrain": "😴 Overtraining",
        "reason_travel": "✈️ Travel",
        "reason_weather": "🌧 Weather",
        "reason_gym": "💪 Gym workout",
        # Bug reports
        "bug_prompt": "🐛 *Report a Bug / Share an Idea*\n\nFound a bug or have ideas on how to improve the bot? Type it here:\n— Bug: what were you doing and what went wrong?\n— Idea: describe what you'd like to see.\n\n_/cancel to cancel_",
        "bug_ok": "✅ *Thanks! Bug reported.* 🙏",
        "bug_enter_text": "❌ Enter a bug description.",
        # Confirm
        "confirm_logout": "⚠️ Are you sure you want to log out?",
        "confirm_yes": "✅ Yes",
        "confirm_no": "❌ Cancel",
        # Account deletion
        "btn_change_name": "✏️ Change Name",
        "set_name_prompt": "Current name: *{name}*\n\nEnter new name:",
        "set_name_ok": "✅ Name changed to *{name}*",
        "set_name_bad": "❌ Name cannot be empty.",
        "btn_delete_account": "🗑 Delete Account",
        "delete_account_warning": (
            "⚠️ *Delete Account*\n\n"
            "This will permanently delete *all your data*:\n"
            "workouts, streak, level, XP, notes — everything.\n\n"
            "This cannot be undone.\n\n"
            "You can come back anytime — just enter the secret code again."
        ),
        "delete_confirm_yes": "🗑 Yes, delete everything",
        "delete_confirm_no": "◀️ Cancel",
        "delete_account_done": "✅ Account deleted. All data erased.\n\nIf you want to come back — type /start and enter the secret code. 💪",
        # Help
        "help": (
            "📖 *Bot commands:*\n\n"
            "/start — main menu\n"
            "/cancel — cancel current action\n"
            "/edit — edit a past day\n"
            "/help — command list\n"
            "/version — bot version (admin)\n"
            "/bugs — bug reports (admin)\n"
            "/fixbug — close bug (admin)"
        ),
        # Reminders
        "reminder_rest": "😴 Today is a rest day. Recover!",
        "reminder_train": "🔔 Don't forget pullups!\n📋 {day_type} day: {planned} pullups\n{status}",
        "reminder_done": "✅ Done: {done}",
        "reminder_not_started": "⏳ Haven't started yet",
        # Language
        "lang_prompt": "🌐 Выбери язык / Choose language:",
        "lang_ok": "✅ Language: English 🇬🇧",
        # History browser
        "btn_history": "📋 History",
        "history_title": "📋 *History — {date_from}–{date_to}*",
        "history_week_total": "📊 Week: {done}/{planned} ({pct}%)",
        "history_no_data": "📋 *History*\n\nNo records yet.",
        "history_no_week_data": "📋 *History*\n\nNo data for this week yet.\nComplete a few workouts and your stats will appear here 💪",
        "history_empty_day": "no data",
        # Poke messages
        "poke_msgs": [
            "💪 Get on the bar! Progress awaits!",
            "🔥 Don't forget pullups! You got this!",
            "⚡ The enemy rests while you're on the couch 😈",
            "🏆 One pullup is better than zero. Start!",
            "💥 The streak won't maintain itself — go!",
        ],
        # Personal record
        # New user broadcast
        "new_user_joined": "👋 *{name}* just joined Pullup Pro! Welcome them! 💪",
        "welcome_greet_sent": "You welcomed {name}, motivation sent👌.",
        "welcome_greet_received": "{name} welcomed you! Now you're part of the pullup team💪!",
        "welcome_greet_already": "You already welcomed {name}.",
        "welcome_greet_missing": "Couldn't send greeting: user is unavailable.",
        "welcome_greet_self": "No need to welcome yourself 😄",
        "personal_best": "🏆 Best",
        "new_pr": "\n\n🏆 *New day record: {done} pullups!* 🎉",
        # Workout notes
        "train_notes_prompt": "📝 Any notes about this workout?\n_(How you felt, conditions, thoughts — anything)_",
        "train_skip_notes": "⏭️ Skip notes",
        "train_saving": "⏳ Saving...",
        # Upcoming schedule
        "stats_schedule_title": "📅 *Next 7 days:*",
        "stats_schedule_rest": "😴 Rest",
        # Progress chart
        "stats_chart_title": "📈 *Chart (7 days):*",
        # Weekly summary
        "weekly_summary_title": "📊 *Weekly Summary*",
        "weekly_summary_body": (
            "🏋️ Pullups: *{done}* / {planned} ({pct}%)\n"
            "🔥 Best day: {best_day} — {best_done} pullups\n"
            "💪 Avg RPE: {avg_rpe}\n"
            "🔥 Streak: *{streak}* days\n"
            "🧊 Freezes: {freeze}"
        ),
        "weekly_summary_no_workouts": "📊 No workouts last week. Don't give up! 💪",
        # Freeze token mechanic
        "freeze_prompt": "🧊 Your streak is about to break!\n\nUse a freeze token to protect your streak?\n_(Freezes left: {tokens})_",
        "freeze_yes_btn": "🧊 Yes, freeze it",
        "freeze_no_btn": "❌ No, reset",
        "freeze_used": "🧊 Freeze used! Streak *{streak}* days protected.\nFreezes left: {tokens}",
        "freeze_empty": "❌ No freezes left. Streak reset. Start fresh! 💪",
        "token_earned_level": "\n\n🧊 *+1 freeze token* — for reaching a new level! _(total: {tokens})_",
        "token_earned_streak": "\n\n🧊 *+1 freeze token* — for a {streak}-day streak! _(total: {tokens})_",
        "token_earned_pr": "\n\n🧊 *+1 freeze token* — for a new personal record! _(total: {tokens})_",
        # Leaderboard
        "btn_leaderboard": "🏆 Leaderboard",
        "leaderboard_title": "🏆 *Leaderboard — this week*",
        "leaderboard_empty": "🏆 *Leaderboard*\n\nNo one yet — you're first! 💪",
        "leaderboard_you_marker": " ← you",
    },
}

# Day type translations
DAY_NAMES = {
    "ru": {"Средний": "Средний", "Лёгкий": "Лёгкий", "Тяжёлый": "Тяжёлый",
           "Отдых": "Отдых", "Плотность": "Плотность"},
    "en": {"Средний": "Medium", "Лёгкий": "Light", "Тяжёлый": "Heavy",
           "Отдых": "Rest", "Плотность": "Density"},
}


def t(key: str, lang: str = "ru", **kwargs) -> str:
    val = STRINGS.get(lang, STRINGS["ru"]).get(key)
    if val is None:
        val = STRINGS["ru"].get(key, key)
    if isinstance(val, str) and kwargs:
        try:
            return val.format(**kwargs)
        except (KeyError, IndexError):
            return val
    return val


def day_name(name_ru: str, lang: str = "ru") -> str:
    return DAY_NAMES.get(lang, DAY_NAMES["ru"]).get(name_ru, name_ru)


def text_filter(key: str):
    """Match button text in any registered language."""
    texts = []
    for lang_dict in STRINGS.values():
        val = lang_dict.get(key)
        if val and isinstance(val, str):
            texts.append(val)
    return F.text.in_(texts)
