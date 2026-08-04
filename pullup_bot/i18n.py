from aiogram import F

STRINGS = {
    "ru": {
        # Buttons - main
        "btn_train": "🏋️ Тренировка",
        "btn_stats": "📊 Статистика",
        "btn_friends": "👥 Друзья",
        "btn_ai": "🤖 Турникмен AI",
        "btn_ai_advice": "💡 Получить совет",
        "btn_settings": "⚙️ Настройки",
        "btn_bug": "🐛 Сообщить о баге",
        "btn_back": "◀️ Назад",
        # Buttons - landing
        "btn_login": "💪 Войти в Турникмен",
        "btn_about": "ℹ️ О боте",
        # Buttons - training
        "btn_undo": "↩️ Отменить подход",
        "btn_manual": "✏️ Ввести вручную",
        "btn_finish": "✅ Завершить тренировку",
        "btn_cancel_train": "🚫 Отменить тренировку",
        "btn_skip": "⏭️ Пропустить",
        # Rest timer
        "btn_rest_fmt": "⏱ {sec} сек",
        "rest_timer_toast": "⏱ Отдых {sec} сек — таймер запущен",
        "rest_timer_running": "⏳ Отдых: осталось {sec} сек",
        "rest_timer_done": "✅ Отдых окончен — следующий подход! 💪",
        # Buttons - settings
        "btn_notify_time": "🔔 Время уведомлений",
        "btn_change_base": "📊 Изменить базу",
        "btn_edit_day": "📝 Редактировать день",
        "btn_skip_reason": "📅 Причина пропуска",
        "btn_logout": "🚪 Выйти из системы",
        "btn_language": "🌐 Язык / Language",
        "btn_notify_workouts_on": "🔔 Уведомления от друзей: ВКЛ",
        "btn_notify_workouts_off": "🔕 Уведомления от друзей: ВЫКЛ",
        "notify_workouts_enabled": "🔔 Уведомления о тренировках друзей *включены*. Ты будешь получать сообщение, когда кто-то завершит тренировку.",
        "notify_workouts_disabled": "🔕 Уведомления о тренировках друзей *выключены*.",
        # Exercises
        "ex_pullups": "Подтягивания",
        "ex_pushups": "Отжимания",
        "ex_dips": "Брусья",
        "ex_squats": "Приседания",
        "ex_pullups_weighted": "Подтягивания с весом",
        "ex_dips_weighted": "Брусья с весом",
        "ex_gen_pullups": "подтягиваний",
        "ex_gen_pushups": "отжиманий",
        "ex_gen_dips": "отжиманий на брусьях",
        "ex_gen_squats": "приседаний",
        "ex_gen_pullups_weighted": "подтягиваний с весом",
        "ex_gen_dips_weighted": "отжиманий на брусьях с весом",
        "train_pick_exercise": "🏋️ Что тренируем сегодня?",
        "ex_setup_prompt": (
            "Первый раз! 💪 Сколько {ex} ты можешь сделать *за один подход* максимум?\n"
            "_Введи честное число — программа подстроится под тебя._"
        ),
        "ex_setup_prompt_weighted": (
            "Первый раз с весом! 🏋️ Сколько {ex} ты можешь сделать *за один подход* "
            "с рабочим весом?\n"
            "_Обычно это 3–8 повторений. Дальше спрошу, сколько кг вешаешь._"
        ),
        "ex_setup_ok": "✅ Дневная норма — *{base}*. Начинаем!",
        # Weighted training
        "kg": "кг",
        "weight_setup_prompt": (
            "⚖️ Сколько килограммов ты вешаешь на пояс для {ex}?\n"
            "_Введи число, например 10 или 12.5. Если пока без веса — введи 0._"
        ),
        "weight_setup_ok": "✅ Рабочий вес — *+{weight} кг*. Поехали!",
        "weight_pick_prompt": (
            "⚖️ Вес на сегодня для {ex}\n\n"
            "Рабочий вес: *+{weight} кг*\n"
            "_Выбери кнопкой или введи своё число. Выбранный вес станет рабочим._"
        ),
        "weight_enter_number": "Введи вес в кг числом — от 0 до {max}. Например: 10 или 12.5",
        "train_with_weight": "⚖️ Вес: *+{weight} кг*",
        "new_weight_pr": (
            "\n\n🏋️ *НОВЫЙ РЕКОРД ПО ВЕСУ!* +{weight} кг в {ex} — "
            "такого ты ещё не поднимал!"
        ),
        "train_progression_weight_up": (
            "\n\n🏋️ *Прибавка веса!* Ты уверенно закрывал план — вешаем ещё "
            "2.5 кг: теперь *+{weight} кг* в {ex}, норма — {base} повторений.\n"
            "_Норма снижена намеренно: с новым весом повторений будет меньше, это нормально._"
        ),
        "train_progression_weight_down": (
            "\n\n⚖️ *Вес снижен.* План в {ex} закрывался меньше чем на 70% — "
            "снимаем 2.5 кг: теперь *+{weight} кг*.\n"
            "_Лучше сделать план с меньшим весом, чем недоделывать с большим._"
        ),
        # Start
        "welcome": (
            "💪 *Турникмен*\n\n"
            "Привет! Я твой персональный тренер по подтягиваниям, отжиманиям, брусьям и приседаниям. "
            "Я помогу тебе следить за прогрессом, адаптировать план тренировок и не терять мотивацию.\n\n"
            "Бот полностью бесплатный. Навсегда.\n\n"
            "🤖 Включает *Турникмен AI* — персональный ИИ-тренер на базе Google Gemini 3 Flash. "
            "Знает всю историю твоих тренировок, отвечает на любые вопросы.\n\n"
            "Выбери действие:\n\n"
            "📩 По вопросам о боте: @zhanbota102"
        ),
        "about": (
            "ℹ️ *О боте — 1/3*\n\n"
            "💪 Привет! Я — Турникмен, твой персональный тренер по подтягиваниям, отжиманиям, "
            "брусьям и приседаниям. Помогу следить за прогрессом, адаптировать план тренировок "
            "и не терять мотивацию.\n\n"
            "Бот полностью бесплатный. Навсегда.\n\n"
            "🤖 Включает *Турникмен AI* — персональный ИИ-тренер на базе Google Gemini 3 Flash. "
            "Знает всю историю твоих тренировок, отвечает на любые вопросы.\n\n"
            "🔄 *7-дневный волновой цикл:*\n"
            "Средний → Лёгкий → Тяжёлый → Отдых → Плотность → Лёгкий → Отдых\n\n"
            "Тип дня один для всех упражнений: он задаёт, насколько тяжело сегодня. "
            "А какое упражнение делать — выбираешь ты: одно, два или все четыре. "
            "День засчитан, если сделал хотя бы одно.\n\n"
            "📈 *Автоматическая прогрессия:*\n"
            "У каждого упражнения своя норма. Стабильно выполняешь цикл — норма +5%.\n"
            "Высокий RPE → нагрузка снижается. Низкий RPE → нагрузка повышается.\n\n"
            "_Программу можно сменить в Настройках: Стандарт (5х/нед), Новичок (3х/нед), Продвинутый (6х/нед)._\n\n"
            "📩 По вопросам о боте: @zhanbota102"
        ),
        "about_page2": (
            "ℹ️ *О боте — 2/3*\n\n"
            "📊 *RPE — оценка усилия:*\n"
            "После каждой тренировки оцени от 1 до 10 насколько было тяжело.\n"
            "Бот корректирует норму упражнения автоматически на основе скользящего среднего.\n\n"
            "🧊 *Токены заморозки:*\n"
            "Пропустил день — бот сам потратит токен, и стрик сохранится. Ничего нажимать не нужно.\n"
            "Как заработать: каждые 7 дней стрика подряд, при повышении ранга, при новом рекорде.\n"
            "Максимум — 5 токенов.\n\n"
            "🤖 *Турникмен AI:*\n"
            "ИИ персонализирован лично под тебя. Он анализирует все твои предыдущие тренировки, "
            "выполненные подходы, твой RPE, отдыхал ли ты, пропускал ли тренировки — и на основе "
            "этого даёт персональные советы. Или просто поговори: спроси про технику, план, "
            "как работает бот.\n\n"
            "🌱 *Важно:*\n"
            "Бот — это инструмент. Настоящий прогресс строится на сне, питании и восстановлении."
        ),
        "about_page3": (
            "ℹ️ *О боте — 3/4*\n\n"
            "⭐ *Как работает XP:*\n"
            "+1 XP за подтягивание\n"
            "+0.75 XP за отжимание на брусьях\n"
            "+0.5 XP за отжимание\n"
            "+0.25 XP за приседание\n"
            "+3% за каждый кг утяжеления (до 50 кг)\n"
            "+50 XP за каждый день стрика подряд\n\n"
            "🏅 *Ранги (как в CS:GO):*\n"
            "`Silver I                 0 XP`\n"
            "`Silver II              500 XP`\n"
            "`Silver III           1 000 XP`\n"
            "`Silver IV            1 800 XP`\n"
            "`Silver Elite         2 800 XP`\n"
            "`Silver Elite Master  4 000 XP`\n"
            "`Gold Nova I          5 500 XP`\n"
            "`Gold Nova II         7 500 XP`\n"
            "`Gold Nova III       10 000 XP`\n"
            "`Gold Nova Master    13 500 XP`\n"
            "`Master Guardian I   18 000 XP`\n"
            "`Master Guardian II  23 000 XP`\n"
            "`MG Elite            29 000 XP`\n"
            "`DMG                 36 000 XP`\n"
            "`Legendary Eagle     44 000 XP`\n"
            "`LEM                 53 000 XP`\n"
            "`SMFC                63 000 XP`\n"
            "`The Global Elite    70 000 XP`\n\n"
            "🎯 *До Global Elite:* ~1.5 года при ~70 XP в день со стриком\n"
            "_(например, 70 подтягиваний или 100 отжиманий + 20 подтягиваний)_\n\n"
            "🗑 *Удаление аккаунта:*\n"
            "Если ты решишь уйти — можно полностью удалить аккаунт через _Настройки_. "
            "Все данные будут стёрты навсегда."
        ),
        "about_page4": (
            "ℹ️ *О боте — 4/4*\n\n"
            "🏋️ *Тренировки с утяжелением*\n\n"
            "В боте шесть упражнений. Четыре со своим весом — подтягивания, "
            "отжимания, брусья, приседания — и два с дополнительным весом: "
            "*подтягивания с весом* и *брусья с весом*.\n\n"
            "Обычные упражнения работают ровно как раньше. Утяжеление — это "
            "отдельные упражнения со своей нормой, своим весом и своими рекордами. "
            "Можно вести только своим весом, только с утяжелением, или всё сразу.\n\n"
            "*Как это работает*\n\n"
            "• Выбираешь упражнение с весом → бот спрашивает, сколько кг на поясе\n"
            "• Вес сохраняется как рабочий — в следующий раз просто подтверждаешь\n"
            "• Каждый килограмм добавляет 3% XP за повторение (до 50 кг)\n"
            "• Бот отдельно помнит твой самый тяжёлый вес как рекорд\n\n"
            "*Прогрессия — двойная*\n\n"
            "Сначала растут повторения на текущем весе. Как только стабильно "
            "закрываешь план — бот добавляет 2.5 кг и снижает норму повторений, "
            "и цикл повторяется. Так вес растёт годами без застоя.\n\n"
            "📖 Подробный гайд — чем вешать вес, как надевать пояс, техника и "
            "безопасность — в _«📖 Как начать» → «🏋️ С утяжелением»_."
        ),
        "btn_about_next": "Далее →",
        "btn_guide": "📖 Как начать",
        "btn_guide_step1": "Шаг 1 →",
        "btn_guide_step2": "Шаг 2 →",
        "btn_guide_step3": "Шаг 3 →",
        "btn_guide_step4": "Шаг 4 →",
        "btn_guide_extra": "Дополнительно →",
        "btn_guide_weighted": "🏋️ С утяжелением →",
        "guide_weighted": (
            "🏋️ *Подтягивания и брусья с утяжелением*\n\n"
            "Когда своего веса становится мало, дальше растут не повторения, а вес. "
            "Это отдельные упражнения в боте — обычные подтягивания и брусья "
            "никуда не делись и работают как раньше.\n\n"
            "*Когда пора начинать*\n\n"
            "Ориентир — 12–15 чистых подтягиваний или 20 отжиманий на брусьях "
            "за подход. Раньше этого вес только испортит технику.\n\n"
            "*Чем вешать вес*\n\n"
            "🔗 *Пояс для отягощений (dip belt)* — основной вариант. Широкий пояс "
            "с цепью, цепь продевается через блины и застёгивается карабином. "
            "Цепь 80–90 см, блины висят между ног чуть ниже колен. "
            "Это самый удобный способ: вес висит свободно и не мешает движению.\n\n"
            "🎽 *Жилет-утяжелитель* — вес распределён по корпусу, ничего не "
            "раскачивается. Удобно для брусьев и для большого числа повторений, "
            "но обычно ограничен 20–30 кг и стоит дороже пояса.\n\n"
            "🎒 *Рюкзак с блинами или бутылками воды* — с чего начинают почти все. "
            "Бесплатно и работает до ~15 кг. Затяни лямки потуже, чтобы не болтался. "
            "Минус: тянет плечи назад и мешает вверху амплитуды.\n\n"
            "🦵 *Гантель между стоп или колен* — годится на 5–10 кг, если ничего "
            "другого нет. Держать её всё время неудобно, и уронить легко — "
            "не делай так с большим весом.\n\n"
            "*Как надевать пояс*\n\n"
            "1. Застегни пояс на бёдрах, а не на талии — он должен сидеть на тазу\n"
            "2. Продень цепь через отверстие блина\n"
            "3. Пристегни цепь карабином, отрегулируй длину\n"
            "4. Проверь, что блины не задевают перекладину и не бьют по коленям\n"
            "5. Повисни на месте пару секунд, прежде чем делать первое повторение\n\n"
            "*Техника*\n\n"
            "• Вес не отменяет амплитуду: внизу руки прямые, вверху подбородок над перекладиной\n"
            "• Никакого раскачивания и киппинга — с весом это прямой путь к травме плеча\n"
            "• Опускайся под контролем, 2–3 секунды. Именно это даёт рост\n"
            "• На брусьях не уходи слишком глубоко: плечо ниже локтя под весом опасно\n"
            "• Дыши: вдох внизу, выдох на подъёме\n\n"
            "*Безопасность*\n\n"
            "⚠️ Всегда разминайся без веса — 1–2 подхода обычных подтягиваний\n"
            "⚠️ Снимай вес до того, как спрыгнуть с перекладины\n"
            "⚠️ Заболело плечо или локоть — снимай вес, не терпи\n"
            "⚠️ Не проверяй максимум на один раз чаще раза в месяц\n\n"
            "*Как бот ведёт прогрессию*\n\n"
            "Здесь работает *двойная прогрессия* — сначала растут повторения, "
            "потом вес:\n"
            "• Закрываешь ≥95% плана и нагрузка не выше ожидаемой → *+2.5 кг*, "
            "а норма повторений падает на 10%\n"
            "• Закрываешь 80–95% → норма повторений +5%, вес прежний\n"
            "• Закрываешь <70% → *−2.5 кг*, норма прежняя\n\n"
            "То есть ты набираешь повторения на текущем весе, потом вешаешь блин "
            "и начинаешь набирать заново. Так вес растёт годами без застоя.\n\n"
            "*XP*\n\n"
            "Каждый килограмм добавляет 3% к XP за повторение (считается до 50 кг). "
            "Подтягивание с +20 кг = 1.6 XP вместо 1. "
            "Вес честно оплачивается — но и своим весом ранг набрать можно."
        ),
        "guide_intro": (
            "📖 *Руководство для новичка*\n\n"
            "Бот помогает систематически прогрессировать в шести упражнениях: "
            "подтягивания, отжимания, брусья, приседания, а также подтягивания "
            "и брусья *с утяжелением*. "
            "Он строит план, отслеживает прогресс и адаптирует нагрузку под тебя.\n\n"
            "🤖 Есть встроенный *Турникмен AI* — задавай любые вопросы про тренировки или бот."
        ),
        "guide_step1": (
            "📋 *Шаг 1 — Регистрация*\n\n"
            "1. Нажми «💪 Войти в Турникмен»\n"
            "2. Укажи своё имя\n"
            "3. Укажи максимальное количество подтягиваний за один подход\n\n"
            "_Остальные упражнения настроишь позже — бот спросит твой максимум, "
            "когда впервые выберешь их._"
        ),
        "guide_step2": (
            "📅 *Шаг 2 — Ежедневный план*\n\n"
            "У каждого дня есть тип — он общий для всех упражнений:\n"
            "• Средний — 100% нормы\n"
            "• Лёгкий — ~50–60% нормы\n"
            "• Тяжёлый — ~115% нормы\n"
            "• Отдых — восстановление\n"
            "• Плотность — много коротких подходов\n\n"
            "Какое упражнение делать сегодня — выбираешь ты. "
            "Хотя бы одно — и день засчитан."
        ),
        "guide_step3": (
            "🏋️ *Шаг 3 — Тренировка*\n\n"
            "1. Нажми «🏋️ Тренировка»\n"
            "2. Выбери упражнение — подтягивания, отжимания, брусья, приседания "
            "или их версии с утяжелением\n"
            "3. Для упражнений с весом бот спросит, сколько кг сегодня на поясе\n"
            "4. Делай подходы — нажимай на цифры или «✏️ Ввести вручную»\n"
            "5. Нажми «✅ Завершить тренировку» когда закончишь\n\n"
            "Хочешь ещё? Снова нажми «Тренировка» и выбери другое упражнение."
        ),
        "guide_step4": (
            "📊 *Шаг 4 — RPE (оценка усилия)*\n\n"
            "После тренировки бот спросит: насколько тяжело было?\n"
            "1–3 = легко · 4–6 = нормально · 7–8 = тяжело · 9–10 = на пределе\n\n"
            "Бот использует эти оценки чтобы корректировать план автоматически."
        ),
        "guide_extra": (
            "🔥 *Стрик и токены заморозки*\n\n"
            "Стрик — количество дней подряд с тренировкой (любое упражнение) "
            "или подтверждённым отдыхом. Не прерывай его!\n"
            "Пропустил день — бот сам потратит токен заморозки, и серия сохранится.\n\n"
            "Как заработать новый токен:\n"
            "• 🔥 каждые 7 дней стрика подряд\n"
            "• ⬆️ при повышении уровня\n"
            "• 🏆 при новом личном рекорде\n"
            "_(максимум 5 токенов)_\n\n"
            "📈 *Как меняется твоя норма*\n\n"
            "У каждого упражнения своя дневная норма. Она меняется автоматически "
            "и независимо от других упражнений.\n\n"
            "▲ *Повышается:*\n"
            "• +5% после завершения 7-дневного цикла, если среднее выполнение последних 5 тренировок ≥80%\n"
            "• +3% если последние 3 сессии дались заметно легче, чем предполагал тип дня, и все цели выполнены\n\n"
            "▼ *Понижается:*\n"
            "• −2% если последние 3 сессии стабильно тяжелее ожидаемого\n"
            "• −5% если они тяжелее ожидаемого больше чем на полтора балла RPE\n"
            "• Первая тренировка после перерыва 3–6 дней — план снижен на 25%\n"
            "• Первая тренировка после перерыва 7+ дней — план снижен на 40%\n\n"
            "❓ *Нужно ли 7 дней подряд без пропусков?*\n\n"
            "Нет. 7 дней цикла — это не 7 календарных дней, а 7 шагов программы. "
            "Шаг засчитывается когда ты тренируешься или подтверждаешь день отдыха в боте. "
            "Пропустил день без открытия бота — шаг не засчитался, но начинать с нуля не нужно. "
            "Просто продолжи с того же места.\n\n"
            "📊 *Как RPE влияет на план*\n\n"
            "Бот сравнивает твою оценку не с одним общим числом, а с тем, "
            "*насколько тяжёлым этот день должен был быть*:\n"
            "• Лёгкий день — ожидаем RPE ~5\n"
            "• Средний — ~6.5\n"
            "• Плотность — ~7\n"
            "• Тяжёлый — ~8\n\n"
            "Считается скользящее среднее отклонения за 3 последние сессии "
            "этого упражнения:\n"
            "• На балл легче ожидаемого и все цели закрыты → норма растёт (+3%)\n"
            "• Примерно как ожидалось → без изменений\n"
            "• На полбалла тяжелее → норма слегка снижается (−2%)\n"
            "• На полтора балла тяжелее → норма снижается (−5%)\n"
            "_Тяжёлый день на RPE 8 — это план работает как задумано, а не повод "
            "снижать норму. Одна тяжёлая тренировка ничего не изменит — важна "
            "тенденция за 3 подряд. Норма меняется не чаще раза в день._\n\n"
            "⭐ *XP за упражнения*\n\n"
            "• Подтягивание — 1 XP\n"
            "• Отжимание на брусьях — 0.75 XP\n"
            "• Отжимание — 0.5 XP\n"
            "• Приседание — 0.25 XP\n"
            "• С утяжелением — +3% за каждый кг (до 50 кг). "
            "Подтягивание с +20 кг = 1.6 XP\n"
            "• Каждый день стрика — +50 XP\n"
            "Рейтинг недели и «Кочка недели» считаются по XP за неделю.\n\n"
            "📈 *Статистика и история*\n\n"
            "• «📊 Статистика» — прогресс, XP, уровень, стрик\n"
            "• «📋 История» — все прошлые тренировки по неделям\n\n"
            "🤖 *Турникмен AI*\n\n"
            "Нажми «🤖 Турникмен AI» — задай любой вопрос про тренировки или бот. ИИ знает всю твою историю.\n\n"
            "💡 *Совет*\n\n"
            "Начни с консервативной нормы. Бот сам повысит её, когда ты будешь готов.\n\n"
            "🔑 *Главный принцип*\n\n"
            "Не успел сделать полную тренировку? Ничего страшного — залогируй хотя бы 10 повторений. "
            "Даже несколько повторений, сделанных в свободную минуту, на длинной дистанции дают огромный эффект. "
            "Мы здесь ради долгосрочного результата, а не идеального выполнения каждого дня. "
            "Последовательность важнее совершенства."
        ),
        "bye": "👋 Ты вышел из аккаунта.\n\n⏸ Уведомления и стрик поставлены на паузу.\nДанные сохранены — нажми «Войти в Турникмен», чтобы вернуться 💪",
        "main_menu": "👋 Главное меню:",
        "register_first": "Сначала зарегистрируйся — /start",
        "nothing_to_cancel": "Нечего отменять.",
        "cancelled": "❌ Действие отменено.",
        # Login / Registration
        "poke_already_today": "⏳ Ты уже отправил мотивацию {name} сегодня. Можно снова завтра.",
        "code_accepted": "Как тебя зовут?\n_(Введите минимум 3 символа)_",
        "hello_name": "👋 Привет, *{name}*!\n\nСколько подтягиваний ты можешь сделать *за один подход* максимум?\n_Введи честное число — программа подстроится под тебя._",
        "welcome_user": "🎉 *Добро пожаловать, {name}!*\n\nМакс. за подход: *{max_pullups}* → дневная норма: *{base}* подтягиваний\nУровень: {level} — начинаем! 💪",
        "welcome_back": "👋 С возвращением, *{name}*!\n\nУровень: {level} ⭐ XP: {xp}\n🔥 Стрик: {streak} дней",
        "enter_number": "❌ Введи число, например: {example}",
        # Training
        "train_goal": "🎯 Цель: *{planned}* {ex}",
        "train_done_today": "✅ Сделано за сегодня: *{done}*",
        "train_done_now": "🏋️ Сделано сейчас: *{done}*",
        "train_in_progress": "🏋️ *Тренировка идёт...*\n_Нажми на число или введи вручную:_",
        "train_no_sets": "❌ Нечего отменять — подходов ещё нет.",
        "train_enter_reps": "Введи количество повторений в подходе:",
        "train_rate_rpe": "Оцени по шкале от 1 до 10, насколько тяжёлой была тренировка:\n1 = очень легко · 10 = полный отказ",
        "train_rpe_invalid": "❌ Введи число 1-10 или нажми ⏭️ Пропустить.",
        "train_cancelled": "🚫 Тренировка отменена.",
        "train_confirm_cancel": "⚠️ Уверены что хотите отменить?\n\nВы потеряете *{done}* повторений за {sets} подходов.",
        "train_yes_cancel": "❌ Да, отменить тренировку",
        "train_continue": "↩️ Нет, продолжить тренировку",
        "train_lets_go": "💪 Продолжаем!",
        "train_complete": (
            "{em} *Тренировка завершена — {ex}!*\n\n"
            "📊 Сделано: *{done}* / {planned} ({pct})\n"
            "📦 Подходов: {sets}\n"
            "💪 RPE: {rpe}/10{rpe_comment}\n\n"
            "⭐ XP: +{xp_gained} (всего {xp_total})\n"
            "🏅 Уровень: {level} [{bar}] {to_next} до след.\n"
            "🔥 Стрик: {streak} дней"
        ),
        "train_rpe_trending_high": "\n⚠️ Средний RPE {avg:.1f} за 3 сессии — нагрузка слишком высокая. Норма ({ex}) снижена до {base} (−5%).",
        "train_rpe_trending_moderate": "\n📉 Средний RPE {avg:.1f} за 3 сессии — нагрузка высокая. Норма ({ex}) немного снижена до {base} (−2%).",
        "train_rpe_trending_low": "\n🚀 Средний RPE {avg:.1f} за 3 сессии — форма отличная! Норма ({ex}) повышена до {base} (+3%).",
        "train_progression": "\n🎯 Цикл завершён! Стабильный прогресс — норма ({ex}) повышена до {base} (+5%).",
        "density_hint": "💡 _День плотности: много коротких подходов, минимум отдыха между ними. Цель — набрать объём равномерно в течение дня._",
        "train_friend_notify": "📣 *{name}* завершил тренировку — {ex}!\n🎯 Цель: {planned} | Выполнено: {done} | Подходов: {sets}",
        "set_pr_congrats": "🏆 *Новый личный рекорд: {reps} за подход ({ex})!* Congrats! 🎉",
        "set_pr_friend_line": "\n🏆 Личный рекорд за подход ({ex}): *{reps}*",
        # Rest day override
        "rest_day_prompt": "😴 Сегодня день отдыха. Что хочешь сделать?",
        "rest_day_train": "💪 Тренироваться",
        "rest_day_rest": "😴 Отдыхать",
        # Friends
        "btn_friends_prev": "← Пред.",
        "btn_friends_next": "След. →",
        "friends_title": "👥 *Активные участники:*\n_Здесь видны те, кто тренировался хотя бы раз за последние 7 дней._",
        "friends_page": "Стр. {page} / {total}",
        "friends_empty": "👥 *Участники*\n\nПока никого нет — ты первый! 💪",
        "friends_poke_sent": "✅ Мотивация другу {name} отправлена! 💪",
        "friends_not_found": "❌ Участник не найден.",
        "friends_blocked": "❌ Пользователь заблокировал бота.",
        "friends_error": "❌ Не удалось отправить.",
        # AI
        "ai_thinking": "🤖 Анализирую твои данные...",
        "ai_thinking_chat": "💭 Думаю...",
        "ai_unavailable": "⚠️ ИИ временно недоступен — серверы перегружены. Попробуй ещё раз, обычно со второй-третьей попытки работает.",
        "ai_limit_daily": "🤖 Бот использовал дневной лимит запросов к ИИ. Попробуй снова завтра!",
        "ai_limit_minute": "🤖 Слишком много запросов к ИИ за раз. Подожди минуту и попробуй снова.",
        # Settings
        "settings_title": "⚙️ *Настройки*\n\nНормы:\n{bases}\nУведомления: {notify}\nЗаморозок: {freeze}",
        "set_time_prompt": "Текущее время уведомлений: *{current}*\n\nВведи новое время в формате *ЧЧ:ММ* (например: 09:00):",
        "set_time_ok": "✅ Напоминания в *{time}*",
        "set_time_bad": "❌ Неверный формат. Введи как: 09:00",
        "set_base_pick": "Норму какого упражнения изменить?",
        "set_base_prompt": "Текущая норма ({ex}): *{base}*/день\n\nВведи новое значение:",
        "set_base_ok": "✅ Норма ({ex}): *{base}*/день",
        "set_base_range": "❌ Введи число от 1 до 500:",
        "edit_date_prompt": "Введи дату в формате *ДД.ММ*:",
        "edit_date_bad": "❌ Неверный формат. Введи как: 14.03",
        "edit_pick_exercise": "Какое упражнение редактируем?",
        "edit_done_prompt": "Сколько повторений ({ex}) сделано *{date}*?\n_0 — удалить запись_",
        "edit_rpe_prompt": "Оцени RPE (1-10) для того дня:",
        "edit_ok": "✅ День *{date}* обновлён ({ex}): {done} повторений, RPE {rpe}",
        "edit_deleted": "🗑 Запись ({ex}) за *{date}* удалена.",
        "edit_no_date": "❌ Ошибка: дата не найдена.",
        "skip_date_prompt": "За какую дату добавить причину? Формат *ДД.ММ*:\n_(до 3 дней назад)_",
        "skip_date_range": "❌ Можно добавить причину только за последние 3 дня.",
        "skip_choose_reason": "Выбери причину:",
        "skip_ok": "✅ Причина добавлена за *{date}*: {reason}\n🔥 Стрик восстановлен!",
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
            "Вернуться можно в любой момент — нажми «Войти в Турникмен»."
        ),
        "delete_confirm_yes": "🗑 Да, удалить всё",
        "delete_confirm_no": "◀️ Отмена",
        "delete_account_done": "✅ Аккаунт удалён. Все данные стёрты.\n\nЕсли захочешь вернуться — нажми «Войти в Турникмен». 💪",
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
        "reminder_train": "🔔 Не забудь про тренировку!\n📋 {day_type} день:\n{plans}\n{status}",
        "reminder_not_started": "⏳ Ещё не начинал",
        "btn_reminder_start": "▶️ Начать тренировку",
        # Language
        "lang_prompt": "🌐 Выбери язык / Choose language:",
        "lang_ok": "✅ Язык: Русский 🇷🇺",
        # History browser
        "btn_history": "📋 История",
        "history_title": "📋 *История — {date_from}–{date_to}*",
        "history_week_total": "📊 Неделя: {totals}",
        "history_no_data": "📋 *История*\n\nНет записей.",
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
        "new_pr": "\n\n🏆 *Новый рекорд дня ({ex}): {done}!* 🎉",
        "train_saving": "⏳ Сохраняю...",
        # Upcoming schedule
        "stats_schedule_rest": "😴 Отдых",
        # Weekly summary
        "weekly_summary_title": "📊 *Итоги недели*",
        "weekly_summary_body": (
            "🏋️ Объём:\n{volume}\n"
            "⭐ XP за неделю: *{week_xp}*\n"
            "💪 Средний RPE: {avg_rpe}\n"
            "🔥 Стрик: *{streak}* дней\n"
            "🧊 Заморозок: {freeze}"
        ),
        "weekly_summary_no_workouts": "📊 На прошлой неделе тренировок не было. Не сдавайся! 💪",
        # Freeze token mechanic
        "token_earned_level": "\n\n🧊 *+1 заморозка* — за повышение уровня! _(всего: {tokens})_",
        "token_earned_streak": "\n\n🧊 *+1 заморозка* — за {streak} дней стрика подряд! _(всего: {tokens})_",
        "token_earned_pr": "\n\n🧊 *+1 заморозка* — за новый личный рекорд! _(всего: {tokens})_",
        # Leaderboard
        "btn_leaderboard": "🏆 Рейтинг",
        "leaderboard_title": "🏆 *Рейтинг — XP за неделю*",
        "leaderboard_empty": "🏆 *Рейтинг*\n\nПока никого нет — ты первый! 💪",
        "leaderboard_you_marker": " ← ты",
        # Program selection
        "btn_program": "🔧 Программа",
        "program_title": "🔧 *Программа тренировок*\n\nТекущая: *{current}*\n\nВыбери программу:",
        "program_standard": "📋 Стандарт (5х/нед)",
        "program_beginner": "🌱 Новичок (3х/нед)",
        "program_advanced": "🔥 Продвинутый (6х/нед)",
        "program_set_ok": "✅ Программа изменена на *{program}*",
        # Data export
        "btn_export": "📤 Экспорт",
        "export_caption": "📤 Твои тренировки (CSV)",
        "export_empty": "📋 Нет данных для экспорта.",
        # History monthly view
        "history_monthly_title": "📅 *История по месяцам*",
        "history_monthly_row": "`{month}  {totals}  {days}д`",
        "btn_history_monthly": "📅 По месяцам",
        "btn_history_weekly": "📅 По неделям",
        "heatmap_legend": "🟩 план · 🟨 частично · ⬜ нет данных · 😴 отдых",
        "month_names": ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"],
        # Advanced analytics
        "btn_analytics": "📈 Подробно",
        "analytics_title": "📈 *Аналитика*",
        "analytics_monthly_vol": "📊 *Объём по месяцам (XP, посл. 6):*",
        "analytics_day_type": "📋 *Выполнение по типу дня:*",
        "analytics_records": "🏆 *Рекорды (день / подход):*\n{records}\n🔥 Макс. стрик: {max_streak} дней",
        "analytics_weekday": "📅 *Самый активный день недели:* {day} ({count} тренировок)",
        "btn_back_stats": "◀️ К статистике",
    },
    "en": {
        # Buttons - main
        "btn_train": "🏋️ Training",
        "btn_stats": "📊 Statistics",
        "btn_friends": "👥 Friends",
        "btn_ai": "🤖 Turnikmen AI",
        "btn_ai_advice": "💡 Get Advice",
        "btn_settings": "⚙️ Settings",
        "btn_bug": "🐛 Report a Bug",
        "btn_back": "◀️ Back",
        # Buttons - landing
        "btn_login": "💪 Join Pullup Pro",
        "btn_about": "ℹ️ About",
        # Buttons - training
        "btn_undo": "↩️ Undo Set",
        "btn_manual": "✏️ Enter Manually",
        "btn_finish": "✅ Finish Training",
        "btn_cancel_train": "🚫 Cancel Training",
        "btn_skip": "⏭️ Skip",
        # Rest timer
        "btn_rest_fmt": "⏱ {sec}s",
        "rest_timer_toast": "⏱ Resting {sec}s — timer started",
        "rest_timer_running": "⏳ Rest: {sec}s left",
        "rest_timer_done": "✅ Rest over — next set! 💪",
        # Buttons - settings
        "btn_notify_time": "🔔 Notification Time",
        "btn_change_base": "📊 Change Base",
        "btn_edit_day": "📝 Edit Day",
        "btn_skip_reason": "📅 Skip Reason",
        "btn_logout": "🚪 Log Out",
        "btn_language": "🌐 Язык / Language",
        "btn_notify_workouts_on": "🔔 Friend Notifications: ON",
        "btn_notify_workouts_off": "🔕 Friend Notifications: OFF",
        "notify_workouts_enabled": "🔔 Friend workout notifications *enabled*. You'll be notified when someone finishes a workout.",
        "notify_workouts_disabled": "🔕 Friend workout notifications *disabled*.",
        # Exercises
        "ex_pullups": "Pull-ups",
        "ex_pushups": "Push-ups",
        "ex_dips": "Dips",
        "ex_squats": "Squats",
        "ex_pullups_weighted": "Weighted pull-ups",
        "ex_dips_weighted": "Weighted dips",
        "ex_gen_pullups": "pull-ups",
        "ex_gen_pushups": "push-ups",
        "ex_gen_dips": "dips",
        "ex_gen_squats": "squats",
        "ex_gen_pullups_weighted": "weighted pull-ups",
        "ex_gen_dips_weighted": "weighted dips",
        "train_pick_exercise": "🏋️ What are we training today?",
        "ex_setup_prompt": (
            "First time! 💪 How many {ex} can you do *in one set* at your max?\n"
            "_Be honest — the program will adjust to you._"
        ),
        "ex_setup_prompt_weighted": (
            "First time with added load! 🏋️ How many {ex} can you do *in one set* "
            "at your working weight?\n"
            "_Usually 3–8 reps. I'll ask how many kg you're hanging next._"
        ),
        "ex_setup_ok": "✅ Daily target — *{base}*. Let's go!",
        # Weighted training
        "kg": "kg",
        "weight_setup_prompt": (
            "⚖️ How many kilograms do you hang on the belt for {ex}?\n"
            "_Enter a number, e.g. 10 or 12.5. Enter 0 if you're not adding load yet._"
        ),
        "weight_setup_ok": "✅ Working weight — *+{weight} kg*. Let's go!",
        "weight_pick_prompt": (
            "⚖️ Today's load for {ex}\n\n"
            "Working weight: *+{weight} kg*\n"
            "_Tap a button or type your own. Whatever you pick becomes the new working weight._"
        ),
        "weight_enter_number": "Enter the load in kg as a number — 0 to {max}. For example: 10 or 12.5",
        "train_with_weight": "⚖️ Load: *+{weight} kg*",
        "new_weight_pr": (
            "\n\n🏋️ *NEW WEIGHT RECORD!* +{weight} kg on {ex} — "
            "you've never lifted that before!"
        ),
        "train_progression_weight_up": (
            "\n\n🏋️ *Load increased!* You've been closing the plan comfortably, so "
            "another 2.5 kg goes on: now *+{weight} kg* on {ex}, target {base} reps.\n"
            "_The rep target drops on purpose — fewer reps at a heavier load is expected._"
        ),
        "train_progression_weight_down": (
            "\n\n⚖️ *Load reduced.* You were finishing under 70% of the plan on {ex}, "
            "so 2.5 kg comes off: now *+{weight} kg*.\n"
            "_Better to complete the plan lighter than to leave it unfinished heavier._"
        ),
        # Start
        "welcome": (
            "💪 *Pullup Pro*\n\n"
            "Hey! I'm your personal coach for pull-ups, push-ups, dips and squats. "
            "I'll help you track progress, adapt your training plan, and stay motivated.\n"
            "The bot is completely free. Forever.\n\n"
            "🤖 Includes *Turnikmen AI* — a personal AI coach powered by Google Gemini 3 Flash. "
            "It knows your full training history and answers any question.\n\n"
            "Choose an action:\n\n"
            "📩 For questions about the bot: @zhanbota102"
        ),
        "about": (
            "ℹ️ *About — 1/3*\n\n"
            "💪 Hey! I'm Pullup Pro — your personal coach for pull-ups, push-ups, dips and squats. "
            "I'll help you track progress, adapt your training plan, and stay motivated.\n\n"
            "The bot is completely free. Forever.\n\n"
            "🤖 Includes *Turnikmen AI* — a personal AI coach powered by Google Gemini 3 Flash. "
            "It knows your full training history and answers any question.\n\n"
            "🔄 *7-day wave cycle:*\n"
            "Medium → Light → Heavy → Rest → Density → Light → Rest\n\n"
            "The day type is shared by all exercises: it sets how hard today is. "
            "Which exercise to do is up to you — one, two, or all four. "
            "The day counts as long as you do at least one.\n\n"
            "📈 *Automatic progression:*\n"
            "Each exercise has its own daily target. Complete cycles consistently — target +5%.\n"
            "High RPE → load decreases. Low RPE → load increases.\n\n"
            "_You can switch programs in Settings: Standard (5x/week), Beginner (3x/week), Advanced (6x/week)._\n\n"
            "📩 Questions about the bot: @zhanbota102"
        ),
        "about_page2": (
            "ℹ️ *About — 2/3*\n\n"
            "📊 *RPE — effort rating:*\n"
            "After each workout rate how hard it was from 1 to 10.\n"
            "The bot adjusts the exercise's target automatically using a rolling average.\n\n"
            "🧊 *Freeze tokens:*\n"
            "Miss a day? The bot spends a token automatically and your streak survives — nothing to press.\n"
            "Earn tokens: every 7-day streak milestone, on each rank-up, on a new personal record.\n"
            "Maximum 5 tokens.\n\n"
            "🤖 *Turnikmen AI:*\n"
            "The AI is personalised just for you. It analyses all your past workouts, completed sets, "
            "RPE scores, rest days, and missed sessions — and gives you advice based on your actual data. "
            "Or just chat: ask about technique, your plan, or how the bot works.\n\n"
            "🌱 *Important:*\n"
            "The bot is a tool. Real progress is built on sleep, nutrition, and recovery."
        ),
        "about_page3": (
            "ℹ️ *About — 3/4*\n\n"
            "⭐ *How XP works:*\n"
            "+1 XP per pull-up\n"
            "+0.75 XP per dip\n"
            "+0.5 XP per push-up\n"
            "+0.25 XP per squat\n"
            "+3% per kg of added load (counted up to 50 kg)\n"
            "+50 XP for every consecutive streak day\n\n"
            "🏅 *Ranks (CS:GO style):*\n"
            "`Silver I                 0 XP`\n"
            "`Silver II              500 XP`\n"
            "`Silver III           1,000 XP`\n"
            "`Silver IV            1,800 XP`\n"
            "`Silver Elite         2,800 XP`\n"
            "`Silver Elite Master  4,000 XP`\n"
            "`Gold Nova I          5,500 XP`\n"
            "`Gold Nova II         7,500 XP`\n"
            "`Gold Nova III       10,000 XP`\n"
            "`Gold Nova Master    13,500 XP`\n"
            "`Master Guardian I   18,000 XP`\n"
            "`Master Guardian II  23,000 XP`\n"
            "`MG Elite            29,000 XP`\n"
            "`DMG                 36,000 XP`\n"
            "`Legendary Eagle     44,000 XP`\n"
            "`LEM                 53,000 XP`\n"
            "`SMFC                63,000 XP`\n"
            "`The Global Elite    70,000 XP`\n\n"
            "🎯 *Road to Global Elite:* ~1.5 years at ~70 XP/day with an active streak\n"
            "_(e.g. 70 pull-ups, or 100 push-ups + 20 pull-ups)_\n\n"
            "🗑 *Deleting your account:*\n"
            "If you ever decide to leave — you can permanently delete your account via _Settings_. "
            "All data will be erased forever."
        ),
        "about_page4": (
            "ℹ️ *About — 4/4*\n\n"
            "🏋️ *Weighted training*\n\n"
            "The bot has six exercises. Four at bodyweight — pull-ups, push-ups, "
            "dips, squats — and two with added load: *weighted pull-ups* and "
            "*weighted dips*.\n\n"
            "The bodyweight exercises work exactly as before. Weighted work is "
            "separate, with its own target, its own load and its own records. "
            "Train bodyweight only, weighted only, or both.\n\n"
            "*How it works*\n\n"
            "• Pick a weighted exercise → the bot asks how many kg are on the belt\n"
            "• That load is stored as your working weight — next time you just confirm it\n"
            "• Each kilogram adds 3% XP per rep (counted up to 50 kg)\n"
            "• Your heaviest load ever is tracked as a record of its own\n\n"
            "*Double progression*\n\n"
            "Reps build first at the current load. Once you're closing the plan "
            "consistently, the bot adds 2.5 kg and drops the rep target, and the "
            "cycle repeats. That's how the weight keeps climbing for years.\n\n"
            "📖 The full guide — what to hang the weight from, how to fit a belt, "
            "technique and safety — is in _«📖 Getting Started» → «🏋️ Weighted»_."
        ),
        "btn_about_next": "Next →",
        "btn_guide": "📖 Getting Started",
        "btn_guide_step1": "Step 1 →",
        "btn_guide_step2": "Step 2 →",
        "btn_guide_step3": "Step 3 →",
        "btn_guide_step4": "Step 4 →",
        "btn_guide_extra": "More →",
        "btn_guide_weighted": "🏋️ Weighted →",
        "guide_weighted": (
            "🏋️ *Weighted pull-ups and dips*\n\n"
            "When bodyweight stops being enough, progress moves from reps to load. "
            "These are separate exercises in the bot — plain pull-ups and dips are "
            "untouched and work exactly as before.\n\n"
            "*When to start*\n\n"
            "Roughly 12–15 clean pull-ups or 20 dips in a set. Adding weight before "
            "that just wrecks your form.\n\n"
            "*What to hang the weight from*\n\n"
            "🔗 *Dip belt* — the main option. A wide belt with a chain; the chain "
            "threads through the plates and clips back with a carabiner. An 80–90 cm "
            "chain puts the plates between your legs just below the knees. Most "
            "comfortable choice: the load hangs free and stays out of the way.\n\n"
            "🎽 *Weight vest* — load spread across your torso, nothing swinging. "
            "Good for dips and higher rep counts, but usually capped at 20–30 kg and "
            "pricier than a belt.\n\n"
            "🎒 *Backpack with plates or water bottles* — where nearly everyone "
            "starts. Free, and works up to about 15 kg. Tighten the straps so it "
            "doesn't sway. Downside: it pulls your shoulders back and gets in the way "
            "at the top.\n\n"
            "🦵 *Dumbbell between the feet or knees* — fine for 5–10 kg if you have "
            "nothing else. Awkward to hold and easy to drop — don't do this heavy.\n\n"
            "*Fitting the belt*\n\n"
            "1. Buckle it around your hips, not your waist — it should sit on the pelvis\n"
            "2. Thread the chain through the plate\n"
            "3. Clip the carabiner back on and set the chain length\n"
            "4. Check the plates clear the bar and don't bang your knees\n"
            "5. Hang still for a couple of seconds before your first rep\n\n"
            "*Technique*\n\n"
            "• Load doesn't excuse range: arms straight at the bottom, chin over the bar at the top\n"
            "• No swinging or kipping — under load that's a direct route to a shoulder injury\n"
            "• Lower under control, 2–3 seconds. That's where the growth comes from\n"
            "• On dips don't go too deep: shoulder below elbow under load is risky\n"
            "• Breathe: in at the bottom, out on the way up\n\n"
            "*Safety*\n\n"
            "⚠️ Always warm up unloaded — 1–2 sets of ordinary pull-ups\n"
            "⚠️ Take the weight off before you drop from the bar\n"
            "⚠️ Shoulder or elbow hurts — strip the weight, don't push through it\n"
            "⚠️ Don't test a one-rep max more than once a month\n\n"
            "*How the bot progresses you*\n\n"
            "This runs on *double progression* — reps first, then load:\n"
            "• Closing ≥95% of the plan and it isn't harder than the day called for → *+2.5 kg*, "
            "and the rep target drops 10%\n"
            "• Closing 80–95% → rep target +5%, load unchanged\n"
            "• Closing <70% → *−2.5 kg*, target unchanged\n\n"
            "So you accumulate reps at the current load, then add a plate and start "
            "accumulating again. That's what keeps the weight climbing for years.\n\n"
            "*XP*\n\n"
            "Each kilogram adds 3% to the XP per rep (counted up to 50 kg). "
            "A pull-up with +20 kg is worth 1.6 XP instead of 1. "
            "Load is paid for honestly — but you can still climb the ranks at bodyweight."
        ),
        "guide_intro": (
            "📖 *Beginner's Guide*\n\n"
            "The bot helps you progress systematically in six exercises: "
            "pull-ups, push-ups, dips, squats, plus *weighted* pull-ups and dips. "
            "It builds your plan, tracks progress, and automatically adapts load to you.\n\n"
            "🤖 Includes built-in *Turnikmen AI* — ask anything about your training or the bot."
        ),
        "guide_step1": (
            "📋 *Step 1 — Registration*\n\n"
            "1. Tap «💪 Join Turnikmen»\n"
            "2. Enter your name\n"
            "3. Enter your max pullups in one set\n\n"
            "_The other exercises get set up later — the bot asks for your max "
            "the first time you pick them._"
        ),
        "guide_step2": (
            "📅 *Step 2 — Your Daily Plan*\n\n"
            "Every day has a type — shared by all exercises:\n"
            "• Medium — 100% of your target\n"
            "• Light — ~50–60% of your target\n"
            "• Heavy — ~115% of your target\n"
            "• Rest — recovery day\n"
            "• Density — many short sets\n\n"
            "Which exercise to do today is your choice. "
            "At least one — and the day counts."
        ),
        "guide_step3": (
            "🏋️ *Step 3 — Training*\n\n"
            "1. Tap «🏋️ Training»\n"
            "2. Pick an exercise — pull-ups, push-ups, dips, squats, or their weighted versions\n"
            "3. For weighted exercises the bot asks how many kg are on the belt today\n"
            "4. Do sets — tap the numbers or «✏️ Enter Manually»\n"
            "5. Tap «✅ Finish Training» when done\n\n"
            "Want more? Tap «Training» again and pick another exercise."
        ),
        "guide_step4": (
            "📊 *Step 4 — RPE (Effort Rating)*\n\n"
            "After each session the bot asks: how hard was it?\n"
            "1–3 = easy · 4–6 = moderate · 7–8 = hard · 9–10 = near maximum\n\n"
            "The bot uses these ratings to automatically adjust your plan."
        ),
        "guide_extra": (
            "🔥 *Streak & Freeze Tokens*\n\n"
            "Your streak counts consecutive days with a workout (any exercise) "
            "or a confirmed rest day. Keep it alive!\n"
            "Miss a day? The bot spends a freeze token automatically and your streak survives.\n\n"
            "How to earn tokens:\n"
            "• 🔥 every 7-day streak milestone\n"
            "• ⬆️ each time you level up\n"
            "• 🏆 when you set a new personal record\n"
            "_(maximum 5 tokens)_\n\n"
            "📈 *How your targets change*\n\n"
            "Each exercise has its own daily target. It adjusts automatically "
            "and independently of the other exercises.\n\n"
            "▲ *Increases when:*\n"
            "• +5% after completing a 7-day cycle if your last 5 training sessions averaged ≥80% completion\n"
            "• +3% if the last 3 sessions felt clearly easier than the day type called for and all targets were hit\n\n"
            "▼ *Decreases when:*\n"
            "• −2% if the last 3 sessions consistently land harder than expected\n"
            "• −5% if they land more than one and a half RPE points harder than expected\n"
            "• First session after a 3–6 day break — plan reduced by 25%\n"
            "• First session after a 7+ day break — plan reduced by 40%\n\n"
            "❓ *Do you need 7 consecutive days without missing?*\n\n"
            "No. The 7-day cycle is not 7 calendar days — it's 7 program steps. "
            "A step is counted each time you train or confirm a rest day in the bot. "
            "If you skip a day without opening the bot, that step isn't counted, "
            "but you don't restart from zero. Just continue from where you left off.\n\n"
            "📊 *How RPE affects your plan*\n\n"
            "The bot compares your rating not against one fixed number, but against "
            "*how hard that day was supposed to be*:\n"
            "• Light day — expect RPE ~5\n"
            "• Medium — ~6.5\n"
            "• Density — ~7\n"
            "• Hard — ~8\n\n"
            "It then takes a rolling average of the gap over that exercise's last 3 sessions:\n"
            "• A point easier than expected and all targets hit → target increases (+3%)\n"
            "• About as expected → no change\n"
            "• Half a point harder → target eases slightly (−2%)\n"
            "• One and a half points harder → target decreases (−5%)\n"
            "_A hard day at RPE 8 means the plan is working, not a reason to back off. "
            "One hard session won't change anything — the trend over 3 in a row matters. "
            "The target moves at most once a day._\n\n"
            "⭐ *XP per exercise*\n\n"
            "• Pull-up — 1 XP\n"
            "• Dip — 0.75 XP\n"
            "• Push-up — 0.5 XP\n"
            "• Squat — 0.25 XP\n"
            "• Weighted — +3% per kg (up to 50 kg). A pull-up with +20 kg = 1.6 XP\n"
            "• Each streak day — +50 XP\n"
            "The weekly leaderboard and Beast of the Week are ranked by weekly XP.\n\n"
            "📈 *Stats & History*\n\n"
            "• «📊 Statistics» — progress, XP, level, streak\n"
            "• «📋 History» — all past workouts by week\n\n"
            "🤖 *Turnikmen AI*\n\n"
            "Tap «🤖 Turnikmen AI» to chat — ask anything about your training or how the bot works. It knows your full history.\n\n"
            "💡 *Tip*\n\n"
            "Start with a conservative target. The bot will raise it automatically when you're ready.\n\n"
            "🔑 *The key principle*\n\n"
            "Can't finish the full workout today? That's fine — log even 10 reps. "
            "A few reps squeezed into a spare moment add up to a huge impact over the long run. "
            "We're here for long-term results, not short-term perfection. "
            "Consistency beats perfection every time."
        ),
        "bye": "👋 You've logged out.\n\n⏸ Notifications and streak are paused.\nYour data is saved — tap «Join Turnikmen» to come back 💪",
        "main_menu": "👋 Main menu:",
        "register_first": "Register first — /start",
        "nothing_to_cancel": "Nothing to cancel.",
        "cancelled": "❌ Action cancelled.",
        # Login / Registration
        "poke_already_today": "⏳ You already sent motivation to {name} today. Try again tomorrow.",
        "code_accepted": "What's your name?\n_(Enter at least 3 characters)_",
        "hello_name": "👋 Hi, *{name}*!\n\nHow many pullups can you do in *one set* at your max?\n_Be honest — the program will adjust to you._",
        "welcome_user": "🎉 *Welcome, {name}!*\n\nMax per set: *{max_pullups}* → daily target: *{base}* pullups\nLevel: {level} — let's go! 💪",
        "welcome_back": "👋 Welcome back, *{name}*!\n\nLevel: {level} ⭐ XP: {xp}\n🔥 Streak: {streak} days",
        "enter_number": "❌ Enter a number, e.g.: {example}",
        # Training
        "train_goal": "🎯 Goal: *{planned}* {ex}",
        "train_done_today": "✅ Done today: *{done}*",
        "train_done_now": "🏋️ Done now: *{done}*",
        "train_in_progress": "🏋️ *Training in progress...*\n_Tap a number or enter manually:_",
        "train_no_sets": "❌ Nothing to undo — no sets yet.",
        "train_enter_reps": "Enter the number of reps:",
        "train_rate_rpe": "Rate from 1 to 10 how hard the workout was:\n1 = very easy · 10 = total failure",
        "train_rpe_invalid": "❌ Enter a number 1-10 or tap ⏭️ Skip.",
        "train_cancelled": "🚫 Training cancelled.",
        "train_confirm_cancel": "⚠️ Are you sure you want to cancel?\n\nYou'll lose *{done}* reps from {sets} sets.",
        "train_yes_cancel": "❌ Yes, cancel training",
        "train_continue": "↩️ No, continue training",
        "train_lets_go": "💪 Let's go!",
        "train_complete": (
            "{em} *Training complete — {ex}!*\n\n"
            "📊 Done: *{done}* / {planned} ({pct})\n"
            "📦 Sets: {sets}\n"
            "💪 RPE: {rpe}/10{rpe_comment}\n\n"
            "⭐ XP: +{xp_gained} (total {xp_total})\n"
            "🏅 Level: {level} [{bar}] {to_next} to next\n"
            "🔥 Streak: {streak} days"
        ),
        "train_rpe_trending_high": "\n⚠️ Avg RPE {avg:.1f} over 3 sessions — load too high. Target ({ex}) reduced to {base} (−5%).",
        "train_rpe_trending_moderate": "\n📉 Avg RPE {avg:.1f} over 3 sessions — load is high. Target ({ex}) eased slightly to {base} (−2%).",
        "train_rpe_trending_low": "\n🚀 Avg RPE {avg:.1f} over 3 sessions — great form! Target ({ex}) raised to {base} (+3%).",
        "train_progression": "\n🎯 Cycle complete! Consistent progress — target ({ex}) raised to {base} (+5%).",
        "density_hint": "💡 _Density day: many short sets, minimal rest between them. Goal — accumulate volume spread throughout the day._",
        "train_friend_notify": "📣 *{name}* finished training — {ex}!\n🎯 Goal: {planned} | Done: {done} | Sets: {sets}",
        "set_pr_congrats": "🏆 *New personal record: {reps} in one set ({ex})!* Congrats! 🎉",
        "set_pr_friend_line": "\n🏆 All-time set PR ({ex}): *{reps}*",
        # Rest day override
        "rest_day_prompt": "😴 Today is a rest day. What do you want to do?",
        "rest_day_train": "💪 Train anyway",
        "rest_day_rest": "😴 Rest",
        # Friends
        "btn_friends_prev": "← Prev",
        "btn_friends_next": "Next →",
        "friends_title": "👥 *Active participants:*\n_Only those who trained at least once in the last 7 days are shown here._",
        "friends_page": "Page {page} / {total}",
        "friends_empty": "👥 *Participants*\n\nNo one yet — you're the first! 💪",
        "friends_poke_sent": "✅ Motivation sent to {name}! 💪",
        "friends_not_found": "❌ Participant not found.",
        "friends_blocked": "❌ User blocked the bot.",
        "friends_error": "❌ Failed to send.",
        # AI
        "ai_thinking": "🤖 Analyzing your data...",
        "ai_thinking_chat": "💭 Thinking...",
        "ai_unavailable": "⚠️ AI is temporarily unavailable — servers are overloaded. Try again, it usually works on the second or third attempt.",
        "ai_limit_daily": "🤖 The bot has used up its daily AI request limit. Please try again tomorrow!",
        "ai_limit_minute": "🤖 Too many AI requests at once. Wait a minute and try again.",
        # Settings
        "settings_title": "⚙️ *Settings*\n\nTargets:\n{bases}\nNotifications: {notify}\nFreezes: {freeze}",
        "set_time_prompt": "Current notification time: *{current}*\n\nEnter new time as *HH:MM* (e.g.: 09:00):",
        "set_time_ok": "✅ Reminders at *{time}*",
        "set_time_bad": "❌ Invalid format. Enter as: 09:00",
        "set_base_pick": "Which exercise's target do you want to change?",
        "set_base_prompt": "Current target ({ex}): *{base}*/day\n\nEnter new value:",
        "set_base_ok": "✅ Target ({ex}): *{base}*/day",
        "set_base_range": "❌ Enter a number from 1 to 500:",
        "edit_date_prompt": "Enter date as *DD.MM*:",
        "edit_date_bad": "❌ Invalid format. Enter as: 14.03",
        "edit_pick_exercise": "Which exercise are we editing?",
        "edit_done_prompt": "How many reps ({ex}) done on *{date}*?\n_0 — delete the record_",
        "edit_rpe_prompt": "Rate RPE (1-10) for that day:",
        "edit_ok": "✅ Day *{date}* updated ({ex}): {done} reps, RPE {rpe}",
        "edit_deleted": "🗑 Record ({ex}) for *{date}* deleted.",
        "edit_no_date": "❌ Error: date not found.",
        "skip_date_prompt": "For which date? Format *DD.MM*:\n_(up to 3 days ago)_",
        "skip_date_range": "❌ Can only add reason for the last 3 days.",
        "skip_choose_reason": "Choose a reason:",
        "skip_ok": "✅ Reason added for *{date}*: {reason}\n🔥 Streak restored!",
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
            "You can come back anytime — just tap «Join Turnikmen»."
        ),
        "delete_confirm_yes": "🗑 Yes, delete everything",
        "delete_confirm_no": "◀️ Cancel",
        "delete_account_done": "✅ Account deleted. All data erased.\n\nIf you want to come back — tap «Join Turnikmen». 💪",
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
        "reminder_train": "🔔 Don't forget your workout!\n📋 {day_type} day:\n{plans}\n{status}",
        "reminder_not_started": "⏳ Haven't started yet",
        "btn_reminder_start": "▶️ Start training",
        # Language
        "lang_prompt": "🌐 Выбери язык / Choose language:",
        "lang_ok": "✅ Language: English 🇬🇧",
        # History browser
        "btn_history": "📋 History",
        "history_title": "📋 *History — {date_from}–{date_to}*",
        "history_week_total": "📊 Week: {totals}",
        "history_no_data": "📋 *History*\n\nNo records yet.",
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
        "new_pr": "\n\n🏆 *New day record ({ex}): {done}!* 🎉",
        "train_saving": "⏳ Saving...",
        # Upcoming schedule
        "stats_schedule_rest": "😴 Rest",
        # Weekly summary
        "weekly_summary_title": "📊 *Weekly Summary*",
        "weekly_summary_body": (
            "🏋️ Volume:\n{volume}\n"
            "⭐ Weekly XP: *{week_xp}*\n"
            "💪 Avg RPE: {avg_rpe}\n"
            "🔥 Streak: *{streak}* days\n"
            "🧊 Freezes: {freeze}"
        ),
        "weekly_summary_no_workouts": "📊 No workouts last week. Don't give up! 💪",
        # Freeze token mechanic
        "token_earned_level": "\n\n🧊 *+1 freeze token* — for reaching a new level! _(total: {tokens})_",
        "token_earned_streak": "\n\n🧊 *+1 freeze token* — for a {streak}-day streak! _(total: {tokens})_",
        "token_earned_pr": "\n\n🧊 *+1 freeze token* — for a new personal record! _(total: {tokens})_",
        # Leaderboard
        "btn_leaderboard": "🏆 Leaderboard",
        "leaderboard_title": "🏆 *Leaderboard — weekly XP*",
        "leaderboard_empty": "🏆 *Leaderboard*\n\nNo one yet — you're first! 💪",
        "leaderboard_you_marker": " ← you",
        # Program selection
        "btn_program": "🔧 Program",
        "program_title": "🔧 *Training Program*\n\nCurrent: *{current}*\n\nChoose a program:",
        "program_standard": "📋 Standard (5x/week)",
        "program_beginner": "🌱 Beginner (3x/week)",
        "program_advanced": "🔥 Advanced (6x/week)",
        "program_set_ok": "✅ Program changed to *{program}*",
        # Data export
        "btn_export": "📤 Export",
        "export_caption": "📤 Your workouts (CSV)",
        "export_empty": "📋 No data to export.",
        # History monthly view
        "history_monthly_title": "📅 *History by Month*",
        "history_monthly_row": "`{month}  {totals}  {days}d`",
        "btn_history_monthly": "📅 By Month",
        "btn_history_weekly": "📅 By Week",
        "heatmap_legend": "🟩 hit · 🟨 partial · ⬜ no data · 😴 rest",
        "month_names": ["January", "February", "March", "April", "May", "June",
                        "July", "August", "September", "October", "November", "December"],
        # Advanced analytics
        "btn_analytics": "📈 Analytics",
        "analytics_title": "📈 *Analytics*",
        "analytics_monthly_vol": "📊 *Volume by Month (XP, last 6):*",
        "analytics_day_type": "📋 *Completion by Day Type:*",
        "analytics_records": "🏆 *Records (day / set):*\n{records}\n🔥 Max streak: {max_streak} days",
        "analytics_weekday": "📅 *Most trained day:* {day} ({count} sessions)",
        "btn_back_stats": "◀️ Back to Stats",
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
    """Look up a localized string by key and lang, formatting it with any provided kwargs."""
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
    """Return the localized display name for a Russian day-type string."""
    return DAY_NAMES.get(lang, DAY_NAMES["ru"]).get(name_ru, name_ru)


def text_filter(key: str):
    """Match button text in any registered language."""
    texts = []
    for lang_dict in STRINGS.values():
        val = lang_dict.get(key)
        if val and isinstance(val, str):
            texts.append(val)
    return F.text.in_(texts)
