# EVT-98 — in_work_summary.viewed

| | |
|---|---|
| Инициатор | [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) |
| Модуль | [MOD-7](../modules/MOD-7-SYSTEM.md) |
| Сущность(и) | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal, ANIMAL) |

**Триггер.** Пользователь открывает вкладку «В работе» (`Routes.inWork`) —
`InWorkBloc`, реактивно подписан на 8 потоков.

**Эффект.** Показывает 6 плиток со счётчиками ещё не отправленных на
сервер записей: взвешивание, перемещение (дедуплицируется по
`fromId_placeId_HHmm` — несколько строк `Movement` с одинаковым ключом
считаются одним «событием»), вакцинация (сумма трёх счётчиков — новые +
редактируемые + помеченные на удаление), выбытие, регистрация (локальные
животные), инвентаризация — каждая плитка ведёт на свой уже
специфицированный хаб неотправленных ([EVT-48](EVT-48-ANIMAL-WEIGHINGS-VIEWED-UNSENT-IN-ANIMAL.md),
[EVT-40](EVT-40-VACCINATIONS-VIEWED-UNSENT-IN-ANIMAL.md), и т.д.).
**BOARD (избранное/сообщения/мои объявления) в этом экране не участвует
вообще** — весь экран посвящён исключительно ANIMAL-домену. Внизу — кнопка
«Синхронизировать данные» ([EVT-94](EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md)).

**Исходный код.** `lib/pages/in_work/in_work_page.dart`;
`lib/pages/in_work/in_work_bloc.dart` → `InWorkBloc` (8 подписок,
дедупликация перемещений).
