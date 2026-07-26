- **derived from**: [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md), [EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md), [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md)

# UC-174 — Сохранение видимости видов отклоняется бизнес-правилом «ни один вид не выбран»: снэкбар показывает буквальный текст «key» вместо перевода

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md) |
| Сущность | [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) |
| Результат | `UPDATE_REJECTED` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же триггер, что описан в [EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md) —
пользователь на экране `KindsVisibilitySettingsPage` снимает видимость со
всех видов животных разом (по одному переключателем `Switcher` или через
«Снять все») и нажимает «Сохранить» (`KindsVisibilitySettingsCubit.save()`).
Здесь описана ветка, где после всех переключений не остаётся ни одного
видимого вида: `save()` осознанно отклоняет операцию бизнес-правилом,
`_kindsRepository.updateAll` не вызывается вовсе — `Kind.visible` в БД не
меняется. Это `REJECTED`, а не `ERROR`: отказ принят самим кодом кубита по
явному условию, ни один сетевой вызов и ни одно исключение здесь не
участвуют. Задокументирован также независимо проверенный дефект того же
пути: сообщение об отказе, которое видит пользователь, — буквальное слово
«key», а не текст на выбранном языке интерфейса.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения
(гость и авторизованный проходят один и тот же код; экран открывается без
route-guard по авторизации — маршрут `Routes.kindsVisibilitySettings`,
вложен в `Routes.workSettings` под `Routes.profile`, `lib/pages/routes.dart`;
единственная точка входа в UI — `WorkSettingsPage`,
`lib/pages/profile_settings/presentation/work_settings_page.dart`, пункт
«Видимость видов»).

## CURRENT

### Основной поток

1. `KindsVisibilitySettingsPage` открывает `BlocProvider(create: (context) =>
   KindsVisibilitySettingsCubit()..load())`. `load()` вызывает
   `_kindsRepository.getAll()` (весь справочник `Kind`, без фильтра по
   `visible`), сортирует по имени и эмитит `KindsVisibilitySettingsState.loaded(kinds:
   kinds)` дважды подряд (первый `emit` в текущем коде избыточен — оба
   вызова передают один и тот же список, наблюдаемого эффекта у первого нет).
2. Пользователь снимает видимость со всех видов — либо переключая каждый
   `Switcher` по одному (`onChanged` → `toggleKindVisibility(kind)`), либо
   нажимая `BlackCircleButton.secondary` «Снять все» (`onDeselectAll` →
   `toggleAllKindsVisibility(false)`). Оба метода только эмитят новый
   `KindsVisibilitySettingsState.loaded(kinds: updatedKinds)` — чисто
   in-memory изменение, `_kindsRepository` не вызывается ни разу до нажатия
   «Сохранить».
3. Пользователь нажимает `RElevatedButton` «Сохранить»
   (`floatingActionButton` страницы) → `context.read<KindsVisibilitySettingsCubit>().save()`.
4. `save()` проверяет `if (!state.kinds.any((e) => e.visible))` — во всём
   `state.kinds` нет ни одного вида с `visible == true`. Условие истинно.
5. Кубит **не вызывает** `_kindsRepository.updateAll` — эта строка
   находится в ветке `else`, недостижимой при истинном условии шага 4;
   выполняется вместо неё единственная строка ветки:
   `emit(KindsVisibilitySettingsState.failure(kinds: state.kinds, error:
   'key'))`. Метод `return`-ится сразу после `emit`.
6. `KindsVisibilitySettingsPage`, `BlocConsumer.listener`, обрабатывает
   `state.whenOrNull(... failure: (kinds, error) =>
   ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:
   Text(AppLocalizations.of(context)!.tr(error)))) ...)` — вызывает
   `AppLocalizationsExtension.tr(error)` с буквальной строкой `error ==
   'key'`.
7. `AppLocalizationsExtension.tr()` (`lib/l10n/app_localization.dart`) —
   `switch (key) { ... }` с несколькими десятками явных `case`; строки
   `'key'` среди них нет ни одной. Управление попадает в `default: return
   key;` — метод возвращает переданную строку как есть, без перевода и без
   исключения.
8. Пользователь видит `SnackBar` с текстом **«key»** — буквальное английское
   слово, не зависящее от языка интерфейса приложения (русский/английский/
   любой другой) и не сообщающее, что именно пошло не так. Экран не
   закрывается (`context.pop()` вызывается только в ветке `saved`, не в
   `failure`) — переключатели видов остаются в том же (все выключенные)
   состоянии, что и до нажатия «Сохранить»; пользователь может попытаться
   снова, но без включения хотя бы одного вида результат будет тем же.
9. `Kind.visible` в Drift-таблице `Kinds` не изменяется ни для одного вида —
   `updateAll`/`dao.updAll`/`dao.upd` не вызваны ни разу за весь этот поток.

### Альтернативные потоки

- **Существующий, но неиспользуемый правильный ключ.** В `tr()` уже есть
  `case 'profile_settings__kinds_visibility_settings__error_no_value_selected':
  return profile_settings__kinds_visibility_settings__error_no_value_selected;`
  (`lib/l10n/app_localization.dart`) — переведённая строка существует на
  всех локалях приложения (например `app_ru.arb`:
  `"profile_settings__kinds_visibility_settings__error_no_value_selected":
  "Не выбран ни один вид"`; `app_en.arb`: `"No species selected"`). Это
  именно тот ключ, который должен был бы использовать `save()` вместо
  буквального `'key'` — он существует и переведён на все языки приложения,
  но нигде не передаётся в `KindsVisibilitySettingsState.failure`; ни один
  вызов `error:` в кубите не ссылается на него.
- **Хотя бы один вид остаётся видимым.** Условие шага 4 ложно —
  `_kindsRepository.updateAll(state.kinds)` вызывается (батч `updAll` →
  `upd` по каждому `Kind` в одной транзакции), затем `emit(saved(kinds:
  state.kinds))`; это отдельный, успешный сценарий (`UPDATE_OK`), не
  описываемый этим use-case.
- **Техническая ошибка внутри `updateAll`.** `save()` не оборачивает вызов
  `_kindsRepository.updateAll` в `try/catch` — если бы `updAll`/`upd` бросили
  исключение, оно всплыло бы необработанным из `save()` (это отдельный,
  здесь не наступающий гипотетический `ERROR`-сценарий, недостижимый в
  ветке этого use-case, поскольку `updateAll` в ней вообще не вызывается).
- **`error` в `KindsVisibilitySettingsState.failure` — обязательный
  (`required String error`), не nullable.** Единственное место в коде,
  присваивающее ему значение, — буквальный литерал `'key'` на шаге 5;
  других вызовов `KindsVisibilitySettingsState.failure(...)` во всей
  кодовой базе нет.

### Связанные сущности

- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy/Kind,
  HANDBOOKS, узкая грань `Kind.visible`) — сущность, чьё обновление здесь
  отклоняется: `Kind.visible` не изменяется ни для одного вида, весь `state.kinds`
  (включая уже снятые пользователем в памяти изменения) отбрасывается при
  выходе со страницы без успешного сохранения.
- [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)
  (ProfileSettings) — не участвует напрямую в этом сценарии сохранения;
  синхронизируется с сервера тем же сетевым эндпоинтом, что и
  `visibleKinds` (`SettingsRepository.setSettingToSHTP`/`getSettingFromSHTP`),
  но `KindsVisibilitySettingsCubit.save()` — чисто локальная операция, сеть
  здесь не участвует вовсе.
- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — не участвует;
  `save()` не читает и не пишет пользователя.

### Бизнес-правила

- **«Хотя бы один вид должен остаться видимым» — единственное условие,
  проверяемое перед сохранением.** `state.kinds.any((e) => e.visible)` —
  если ложно, сохранение отклоняется целиком; частичного сохранения или
  предупреждения до нажатия «Сохранить» (например, дизейбл кнопки) не
  существует — пользователь узнаёт об отказе только постфактум, из
  `SnackBar`.
- **Отказ — осознанное решение бизнес-правила кубита, а не техническая
  ошибка.** Ни сеть, ни исключение здесь не участвуют; `save()` сам решает
  не вызывать `updateAll` по чистому in-memory условию — это `REJECTED`, не
  `ERROR`.
- **Известный дефект: буквальный, не существующий как ключ локализации
  текст.** Литерал `'key'`, передаваемый в `KindsVisibilitySettingsState.failure(error:
  'key')`, не совпадает ни с одним `case` в
  `AppLocalizationsExtension.tr()` — `default: return key;` возвращает его
  без изменений. Правильный, уже существующий и переведённый на все языки
  ключ — `profile_settings__kinds_visibility_settings__error_no_value_selected`
  (`"Не выбран ни один вид"` на русском, `"No species selected"` на
  английском) — существует в `tr()`, но не используется вызывающим кодом
  `KindsVisibilitySettingsCubit.save()`. Пользователь на любом языке
  интерфейса видит одно и то же нелокализованное слово «key» вместо
  осмысленного сообщения о причине отказа.

## TARGET

TARGET не отличается от CURRENT — правильное поведение (бизнес-правило
«хотя бы один вид видим» и отказ сохранения при его нарушении) уже
реализовано и не меняется этим документирующим проходом; изменения
потребовал бы только сам литерал `error:` в
`KindsVisibilitySettingsCubit.save()`, что является исправлением дефекта,
а не документируемым здесь целевым поведением.

## TBD / BLOCKED

Блокеров для документирования нет — весь сценарий, включая дефект с
буквальным текстом «key», прослеживается статическим чтением кода
(`kinds_visibility_settings_cubit.dart` → `kinds_visibility_settings_state.dart`
→ `kinds_visibility_settings_page.dart` → `app_localization.dart`) и
подтверждён запущенным тестом на уровне кубита (только для факта самого
отказа — `failure`/`updateAll` не вызван; содержимое `error == 'key'` этим
тестом не проверяется, см. «Открытые вопросы и ограничения»).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_cubit.dart` | `KindsVisibilitySettingsCubit.save` | CURRENT | проверяет `state.kinds.any((e) => e.visible)`; если ложно — `emit(failure(kinds: state.kinds, error: 'key'))` и `return`, без вызова `updateAll` |
| `lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_cubit.dart` | `KindsVisibilitySettingsCubit.toggleKindVisibility`, `.toggleAllKindsVisibility` | CURRENT | in-memory переключение `visible` у одного/всех `Kind` в `state.kinds`, без обращения к репозиторию |
| `lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_state.dart` | `KindsVisibilitySettingsState.failure` | CURRENT | freezed-состояние отказа; `error` — `required String`, не nullable; единственный вызов конструктора во всей кодовой базе передаёт литерал `'key'` |
| `lib/pages/profile_settings/presentation/kinds_visibility_settings_page.dart` | `_KindsVisibilitySettingsPageState` (`BlocConsumer.listener`, ветка `failure`) | CURRENT | `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppLocalizations.of(context)!.tr(error))))` — передаёт `error` напрямую в `tr()` без проверки |
| `lib/l10n/app_localization.dart` | `AppLocalizationsExtension.tr` | CURRENT | `switch (key) { ...; default: return key; }` — нет `case 'key'`; возвращает непереведённый вход как есть |
| `lib/l10n/app_localization.dart` | `case 'profile_settings__kinds_visibility_settings__error_no_value_selected'` | CURRENT | существующий, переведённый на все локали ключ, который должен был бы использоваться `save()` вместо литерала `'key'`, но не используется |
| `lib/l10n/app_ru.arb`, `lib/l10n/app_en.arb` (и другие `app_*.arb`) | `profile_settings__kinds_visibility_settings__error_no_value_selected` | CURRENT | переведённая строка на каждом языке приложения («Не выбран ни один вид» / «No species selected» и т.д.) |
| `lib/repositories/kind/kinds_repository.dart` | `KindsRepository.updateAll` (унаследован из `BaseRepository.updateAll`), `.getAll` | CURRENT | `updateAll` — не вызывается в этом сценарии вовсе; `getAll` — источник `state.kinds` при `load()` |
| `lib/repositories/base_repository.dart` | `BaseRepository.updateAll` | CURRENT | делегирует `dao.updAll(list)` — недостижим в этом сценарии |
| `packages/sheep_farm_database/lib/entities/base_dao.dart` | `BaseDao.updAll` | CURRENT | батч-обновление построчным `upd` в одной транзакции — недостижим в этом сценарии |

## Критерии приёмки

- Если после любой комбинации `toggleKindVisibility`/`toggleAllKindsVisibility`
  в `state.kinds` нет ни одного элемента с `visible == true`, вызов
  `save()` эмитит ровно одно состояние —
  `KindsVisibilitySettingsState.failure(kinds: <тот же список>, error:
  'key')` — и не вызывает `_kindsRepository.updateAll` ни разу.
- `Kind.visible` ни для одного вида не меняется в БД в результате такого
  вызова `save()`.
- `KindsVisibilitySettingsPage` при состоянии `failure` показывает
  `SnackBar` с текстом, равным буквальной строке «key» (не переводом,
  не пустой строкой), и не закрывает экран (`context.pop()` не вызывается).
- Ключ `profile_settings__kinds_visibility_settings__error_no_value_selected`
  существует в `AppLocalizationsExtension.tr()` и в `.arb`-файлах всех
  поддерживаемых языков, но ни разу не передаётся аргументом `error:` ни в
  одном вызове `KindsVisibilitySettingsState.failure(...)` в кодовой базе.

## Связанные тесты

- `test/pages/kinds_visibility_settings_cubit_test.dart`, group `'UC-174 —
  KindsVisibilitySettingsCubit.save REJECTED'`, test `'нет ни одного
  видимого вида -> failure, updateAll не вызывается'` — покрывает только
  сам факт отказа: `_isFailure(cubit.state) == true` и
  `verifyNever(() => repository.updateAll(any()))`. Тест **не читает и не
  проверяет** значение `state.error` (не проверяется ни `== 'key'`, ни
  что-либо ещё про содержимое сообщения) — дефект с буквальным
  нелокализованным текстом «key», описанный в этом use-case, этим тестом не
  обнаруживается и не может быть обнаружен в его нынешнем виде: тест
  проверяет тип состояния (`failure`) и факт отказа от `updateAll`, но не
  проверяет полезную нагрузку `error`. Это разрыв между «код по
  этой ветке протестирован» и «дефект обнаружен тестом» — фиксируется
  здесь явно.
  Группа названа по прежней нумерации id (`UC-174`) и не переименована на
  момент написания этой спеки — переименование под `UC-174` выполняется
  отдельным контролируемым проходом, не этой задачей; якорь `grep -r
  "UC-174" test/` заработает только после него.
- Нет теста, проверяющего `AppLocalizationsExtension.tr('key')` напрямую,
  и нет теста, рендерящего `KindsVisibilitySettingsPage` в состоянии
  `failure` и проверяющего фактический текст `SnackBar` — этот последний
  шаг (то, что реально видит пользователь) на сегодня не покрыт ни одним
  тестом, только статическим чтением кода `kinds_visibility_settings_page.dart`
  + `app_localization.dart`, выполненным при написании этой спеки.

## Открытые вопросы и ограничения

- **Приоритетный, независимо подтверждённый дефект: буквальный текст
  «key» в снэкбаре вместо перевода.** `KindsVisibilitySettingsCubit.save()`
  передаёт нелокализованный литерал `'key'`, для которого в
  `AppLocalizationsExtension.tr()` нет `case` — `default: return key;`
  возвращает его без изменений. Правильный ключ
  (`profile_settings__kinds_visibility_settings__error_no_value_selected`,
  переведён на все языки приложения) уже существует в том же файле, но не
  используется вызывающим кодом. Это чисто однострочное исправление
  (замена литерала `'key'` на существующую константу/строку ключа в вызове
  `emit(failure(..., error: ...))`), не затрагивающее ни бизнес-правило
  «хотя бы один вид видим», ни остальной поток — но фактическое поведение
  на сегодня именно такое, каким описано в CURRENT.
- **Тест существует, но не ловит именно этот дефект.** `test/pages/kinds_visibility_settings_cubit_test.dart`
  (group `'UC-174 — KindsVisibilitySettingsCubit.save REJECTED'`) проверяет
  только тип состояния и то, что `updateAll` не вызван — оба этих факта
  верны и в дефектной, и в гипотетически исправленной версии кода. Ни один
  существующий тест не читает `state.error`, поэтому наличие теста на эту
  ветку не является гарантией отсутствия описанного дефекта — «код
  протестирован» и «дефект обнаружен» здесь не совпадают.
- Нет UI-индикации до нажатия «Сохранить» (например, дизейбл кнопки, пока
  не выбран хотя бы один вид) — пользователь может свободно снять все
  переключатели и нажать «Сохранить», прежде чем узнать об отказе; это не
  отдельный технический дефект, а отсутствующая UX-подсказка, не
  специфицируемая отдельно в рамках этого use-case.
- Тот же факт (`Kind.visible`) редактируется и вторым, независимо
  реализованным путём — шагом `FarmCreateStep.kindsVisibility` визарда
  создания фермы (`FarmCreateCubit`, модуль `FARM`) — с отдельной,
  не связанной с этим кубитом логикой toggle/save; не проверено, повторяет
  ли тот путь тот же литерал `'key'` или собственный текст ошибки — вне
  рамок этого use-case (тот код принадлежит уже закрытому модулю `FARM`),
  уже отмечено как находка в [EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md).
