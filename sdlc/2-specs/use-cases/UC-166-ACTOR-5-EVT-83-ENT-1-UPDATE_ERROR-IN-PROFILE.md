# UC-166 — Применение уже подтверждённой смены языка технически отказывает: `LanguageBloc` не перехватывает исключение, флаг «язык изменён» уже сброшен до того, как отказ вообще стал известен

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-83](../events/EVT-83-LANGUAGE-CHANGED-IN-PROFILE.md) |
| Сущность | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Строгое разграничение от соседних сценариев той же формы `ProfileSettingsPage`:

- Если `AuthRepository.updateUser(newUserData)` (для авторизованного) бросает
  исключение **до** того, как `saveChanges()` вообще успевает сравнить
  `newUserData.locale` с `state.currentUserData?.locale` — это
  [EVT-82](../events/EVT-82-USER-PROFILE-EDITED-IN-PROFILE.md)'s `UPDATE_ERROR`,
  уже задокументирован как
  [UC-164](UC-164-ACTOR-5-EVT-82-ENT-1-UPDATE_ERROR-IN-PROFILE.md). Этот файл
  его не переописывает.
- Этот use-case начинается **строго после** того, как форма профиля уже
  сохранена без исключения — для авторизованного `AuthRepository.updateUser()`
  уже успешно отправил `PUT {authSerivceApi}/user` и уже записал ответ сервера
  в Hive (`_saveMainAuthData`); для гостя `AppCacheService.saveGuestCountryCode()`
  (если применимо) уже выполнен без исключения — и `saveChanges()` обнаружил
  расхождение `newUserData.locale != state.currentUserData?.locale`, эмитировал
  `isLanguageChanged: true` и вернул `false` — сама эта точка входа (успешная,
  не техническая) описывается [EVT-83](../events/EVT-83-LANGUAGE-CHANGED-IN-PROFILE.md).
- Предметом именно этого файла является следующий, отдельный шаг —
  **применение** выбранного языка через `LanguageBloc.on<LanguageEventChange>`
  → `LanguageService.setLocale()` — и то, что происходит, когда именно этот
  шаг заканчивается технической ошибкой. Прочитанный код подтверждает: в этой
  цепочке нет ни одного `try/catch` уровня приложения — единственный перехват
  происходит на уровне фреймворка `bloc` и не долетает до пользователя ни в
  каком виде.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения,
независимо от статуса авторизации: сценарий этого файла целиком лежит
**после** ветвления гость/авторизованный внутри `saveChanges()` (см.
[UC-163](UC-163-ACTOR-5-EVT-82-ENT-1-UPDATE_OK-IN-PROFILE.md)) — оба случая
приводят к одному и тому же коду `ProfileSettingsView`, описанному ниже,
одинаково.

## CURRENT

### Основной поток

1. Пользователь (гость или авторизованный) уже выбрал новый язык
   (`ProfileEditCubit.selectLanguage`, пишет в `state.newUserData.locale`) и
   нажал «Сохранить»; `saveChanges()` уже дошёл до строки `if
   (newUserData.locale != state.currentUserData?.locale) { emit(...
   isLanguageChanged: true); return false; }` — для обеих веток (гостя и
   авторизованного) это происходит **после** того, как соответствующий этой
   ветке сетевой/локальный вызов уже завершился без исключения (иначе
   сценарий — [UC-164](UC-164-ACTOR-5-EVT-82-ENT-1-UPDATE_ERROR-IN-PROFILE.md),
   не этот файл). Для авторизованного к этому моменту Hive `AUTH_BOX/userKey`
   уже переписан ответом сервера — **новое значение `locale` уже физически
   персистировано** и на сервере, и локально.
2. `ProfileSettingsView`'s внешний `BlocConsumer<ProfileEditCubit, ProfileEditState>`
   (`listenWhen: (previous, current) => !previous.isLanguageChanged &&
   current.isLanguageChanged`) срабатывает: `listener` читает `newLocale =
   state.newUserData?.locale ?? LanguageService.locale`, вызывает
   `context.read<LanguageBloc>().add(LanguageEventChange(newLocale))` —
   **не `await`-ится**, `add()` в пакете `bloc` синхронно кладёт событие в
   очередь и возвращает управление немедленно, не дожидаясь обработки — и
   сразу же, в этом же вызове `listener`, синхронно вызывает
   `context.read<ProfileEditCubit>().consumeLanguageChangeFlag()`.
3. `consumeLanguageChangeFlag()`: `if (!state.isLanguageChanged) return; emit(state.copyWith(isLanguageChanged: false));` —
   флаг сбрасывается **немедленно**, до того как обработчик события в
   `LanguageBloc` вообще успел начать выполняться (шаг 2 не ждёт шаг 4) — это
   не зависит от того, удастся ли шаг 4 или нет.
4. Асинхронно (после того как событие дойдёт до своего обработчика —
   `Bloc.transformer = sequential()` из `bloc_concurrency`, установлен
   глобально в `lib/main.dart`, `main()`): `LanguageBloc.on<LanguageEventChange>`
   выполняется: `await LanguageService.setLocale(event.newLanguage);`.
5. Внутри `LanguageService.setLocale(newLocale)`: `await pref.setString(_languageKey,
   newLocale);` — бросает исключение (сбой на уровне плагина/платформенного
   канала `shared_preferences`, например ошибка записи на диск; не
   воспроизведено эмпирически этим проходом, см. «Открытые вопросы»). Строка
   `_locale = newLocale;`, следующая за `await`, **не выполняется** —
   статический `LanguageService._locale` (и, соответственно,
   `LanguageService.locale`) остаётся равен прежнему значению.
6. Исключение покидает тело обработчика `on<LanguageEventChange>` — строка
   `emit(LanguageStateChanged(event.newLanguage))` **не достигается**, новое
   состояние `LanguageBloc` не эмитится. Само исключение перехватывается не
   кодом приложения, а внутренним `handleEvent()` пакета `bloc`
   (`package:bloc/src/bloc.dart`, `Bloc.on<E>`): `catch (error, stackTrace) {
   onError(error, stackTrace); rethrow; } finally { ... }`.
7. `onError` вызывает зарегистрированный `Bloc.observer`
   (`Bloc.observer = TalkerBlocObserver(...)`, `lib/injection_container.dart`) →
   `TalkerBlocObserver.onError` (`package:talker_bloc_logger`) →
   `_talker.error('LanguageBloc', error, stackTrace)` — попадает в тот же
   дев-only канал `Talker`, что и остальные технические отказы этого модуля
   (см. [UC-164](UC-164-ACTOR-5-EVT-82-ENT-1-UPDATE_ERROR-IN-PROFILE.md)),
   невидимый обычному пользователю.
8. `rethrow` внутри `handleEvent()` не имеет эффекта, наблюдаемого кем-либо:
   `handleEvent()` — асинхронная функция, вызванная как `handleEvent();` без
   `await`/`unawaited`/`.catchError` внутри самого `on<E>`; её `Future`
   никем не ожидается и не обрабатывается. Приложение не обёрнуто в
   `runZonedGuarded`/`runTalkerZonedGuarded` — в `lib/main.dart`, `main()`,
   вызывается непосредственно `runApp(const MyApp());`, а альтернатива с
   `runTalkerZonedGuarded(...)` закомментирована. Наблюдаемый эффект —
   ничего: ни падения приложения, ни какого-либо дополнительного лога сверх
   уже случившегося на шаге 7.
9. Итог: `LanguageBloc.state` остаётся тем, чем было до шага 2 (`LanguageStateInitial(oldLocale)`
   при первом запуске, либо предыдущий успешный `LanguageStateChanged(oldLocale)`)
   — `LanguageStateChanged(newLocale)` никогда не эмитится.
   `ProfileSettingsView`'s внешний `BlocListener<LanguageBloc, LanguageStateInitial>`
   (`listener: (context, languageState) async { if (languageState is
   LanguageStateChanged) { ... } }`) не срабатывает вовсе — ни
   `ProfileEditCubit.load()` (перезагрузка формы из свежих данных), ни
   `DataUpdateBloc.add(DataUpdateStartAll(resetNavigationOnSuccess: true))`
   (полный ресинк) из этого пути не вызываются.
10. `MyApp.build` (`lib/main.dart`) держит `MaterialApp.router(locale:
    Locale(lang), ...)` внутри `BlocBuilder<LanguageBloc, LanguageStateInitial>`,
    где `lang` вычисляется из `languageState.language` — поскольку
    `LanguageBloc` не эмитировал новое состояние, `lang` не меняется:
    **фактически отображаемый язык приложения остаётся прежним**, несмотря на
    то что пользователь только что подтвердил смену и (для авторизованного)
    новое значение уже лежит на сервере и в Hive.
11. `state.newUserData?.locale` в `ProfileEditCubit` по-прежнему хранит
    запрошенный новый язык (ни один из шагов 2–9 его не трогает) —
    `_ProfileSettingsRegionAndLanguage.build` вычисляет
    `currentLanguageCode = state.newUserData?.locale ?? LanguageService.locale`
    и передаёт его в `LanguagePickerField` как `selectedLanguage` — **пока
    этот же экземпляр `ProfileEditCubit` жив** (пользователь не покидал
    экран), выпадающий список продолжает показывать язык, который
    пользователь выбрал, хотя реально применённый язык интерфейса (весь
    остальной текст на экране, шаг 10) остался прежним — расхождение видно
    прямо на этом же экране.
12. `ProfileEditStateExtension.isDataChanged` сравнивает в том числе
    `currentUserData?.locale != newUserData?.locale` — поскольку ни одно из
    двух полей не изменилось шагами 2–9, это условие остаётся истинным
    (вместе с тем фактом, что `saveChanges()` вообще не тронул `currentUserData`/`newUserData`
    в ветке `isLanguageChanged`, см. [UC-163](UC-163-ACTOR-5-EVT-82-ENT-1-UPDATE_OK-IN-PROFILE.md)) —
    кнопка «Сохранить» остаётся видимой; повторное нажатие — единственный
    доступный пользователю следующий шаг, полностью повторяющий шаги 1–11 (для
    авторизованного это означает повторный, избыточный, но безвредный `PUT
    {authSerivceApi}/user` с уже отправленными данными, и новую попытку
    `LanguageEventChange`, которая может на этот раз пройти успешно, если
    причина сбоя `pref.setString` была временной).

### Альтернативные потоки

- **Пересоздание `ProfileEditCubit` (уход с экрана и возврат) не проявляет и
  не чинит расхождение, а стирает сам факт попытки.** `ProfileSettingsView`
  создаёт кубит заново через `BlocProvider(create: (context) =>
  ProfileEditCubit(loadGuestSettings: true)..load())` при каждом новом
  построении дерева виджетов. `load()` — что для авторизованного (`selectedLanguage
  = LanguageService.locale`, передаётся в `UserModel.fromUser(user,
  selectedCountry, selectedLanguage)`), что для гостя (`locale:
  LanguageService.locale` напрямую в конструкторе `UserModel`) — **всегда**
  берёт значение `locale` для и `currentUserData`, и `newUserData` из
  `LanguageService.locale`, а не из `user.locale` (поле `User`/`UserHive`,
  уже содержащее — для авторизованного — новое, успешно отправленное на шаге
  1 значение). `UserModel.fromUser` (`lib/pages/profile/data/user_model.dart`)
  принимает `user.locale` неявно через параметр `user`, но реально не читает
  это поле нигде в своём теле — параметр `selectedLanguage`, а не `user.locale`,
  становится итоговым `locale` результата. Итог: после пересоздания кубита
  оба поля (`currentUserData.locale`, `newUserData.locale`) снова равны
  друг другу и равны старому `LanguageService.locale` — `isDataChanged` по
  локали снова ложно, кнопка «Сохранить» может исчезнуть (если остальные
  поля тоже не изменены), и сам факт того, что пользователь недавно пытался
  сменить язык, нигде не виден. Для авторизованного при этом **на сервере и
  в Hive уже лежит новое значение `User.locale`** (записанное шагом 1) —
  оно никогда не читается этим путём построения `UserModel`, поэтому
  расхождение между тем, что хранит [ENT-1](../entities/ENT-1-USER-IN-AUTH.md),
  и тем, что реально показывает и применяет приложение, переживает
  пересоздание экрана бессрочно, до следующей **успешной** попытки сменить
  язык тем же путём.
- **`state.loading` в авторизованной ветке не сбрасывается самим шагом
  `isLanguageChanged: true`.** `saveChanges()`: `if
  (newUserData.locale != state.currentUserData?.locale) { emit(state.copyWith(isLanguageChanged:
  true)); return false; }` — в отличие от гостевой ветки того же условия
  (`emit(state.copyWith(loading: false, isLanguageChanged: true));`), здесь
  `loading` не упомянут в `copyWith` и остаётся `true` (выставлено в самом
  начале `saveChanges()`). `BlackCircleButton` (`lib/widgets/button/button.dart`)
  игнорирует `onTap`, пока `isLoading == true`
  (`onTap: !isLoading ? onTap : () {}`) — если ничто другое не сбросит
  `loading`, кнопка «Сохранить» становится нетапабельной. Однако
  `ProfileEditCubit`'s конструктор независимо подписан на изменения того же
  Hive-ключа (`_valueListenable = _authRepository.getAuthBoxListenable(keys:
  [AuthRepository.userKey]); _listener = () { load(); };`), а `updateUser()`
  на шаге 1 уже записал в этот самый ключ — что асинхронно вызывает `load()`
  независимо от последовательности `saveChanges()` и может успеть сбросить
  `loading` до/во время/после шага 2 этого сценария. Порядок этой гонки не
  разрешён чтением кода и не проверялся эмпирически в рамках этого прохода —
  см. «Открытые вопросы»; для гостевой ветки этой гонки нет вовсе (`loading`
  сбрасывается явно, синхронно, тем же `emit`).
- **`newUserData?.locale` из шага 2 может быть `null`, если сам `newUserData`
  уже стал `null`** — структурно не наступает в рамках этого сценария,
  поскольку `state.newUserData` уже гарантированно не `null` к моменту, когда
  `isLanguageChanged` вообще способен стать `true` (тот же `saveChanges()`
  делает ранний `if (newUserData == null) return false;` до этой точки).

### Связанные сущности

- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — сама сущность
  этим use-case-ом не пишется: её поле `locale` для авторизованного уже было
  корректно обновлено на сервере и в Hive **раньше**, на шаге, предшествующем
  этому сценарию (см. «Назначение»/[UC-163](UC-163-ACTOR-5-EVT-82-ENT-1-UPDATE_OK-IN-PROFILE.md)).
  Предмет этого файла — то, что клиентское приложение (глобальный
  `LanguageService.locale`/`LanguageBloc.state`, а после пересоздания
  экрана — и сам `ProfileEditCubit.state.currentUserData`) никогда не узнаёт
  об этом успешно сохранённом значении и не синхронизируется с ним, потому
  что путь применения языка (`LanguageBloc`) технически отказал, а путь
  чтения профиля (`UserModel.fromUser`) в принципе не читает `user.locale`.
- `ProfileEditState`/`ProfileEditCubit` (не отдельная сущность спецификации,
  но состояние экрана) — `isLanguageChanged` сбрасывается независимо от
  исхода; `newUserData`/`currentUserData` не меняются этим сценарием ни в
  одном поле.
- `LanguageBloc`/`LanguageService` — не сущность модуля `PROFILE` в терминах
  БД, а глобальный клиентский механизм хранения `locale` приложения
  (`SharedPreferences`, ключ `'language'`), не персистентный per-account факт:
  этот же ключ используется вне зависимости от того, кто авторизован.

### Бизнес-правила

- Применение языка (`LanguageBloc`) — шаг, **отдельный и не транзакционно
  связанный** с сохранением профиля (`AuthRepository.updateUser`/
  `AppCacheService.saveGuestCountryCode`): один может успешно завершиться,
  пока другой технически отказывает, без какого-либо отката в любую
  сторону.
- Флаг `isLanguageChanged` — одноразовый сигнал «нужно попытаться применить
  язык», а не факт «язык применён» — он гасится в момент, когда его
  единственный читатель (внешний `BlocConsumer.listener` в
  `ProfileSettingsView`) один раз попытался его обработать, независимо от
  того, удалась ли сама попытка.
- Никто в кодовой базе не вызывает `LanguageBloc.add(LanguageEventChange(...))`
  с ожиданием результата (`add()` не возвращает `Future`, и вызывающий код
  нигде не подписывается на следующий `LanguageBloc.state` синхронно с этим
  вызовом, кроме отдельного, независимого `BlocListener<LanguageBloc>`) —
  структурно невозможно, находясь в точке вызова `add()`, узнать, удалась ли
  сама смена языка.
- Единственный канал, в который вообще попадает факт технического отказа —
  `Talker` через `Bloc.observer` (`TalkerBlocObserver`); ни `DataUpdates`
  (эта таблица не имеет отношения к клиентским, не sync-shным блокам), ни
  какой-либо `SnackBar`/`error`-состояние этого не фиксируют.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — вся цепочка (`ProfileSettingsView`'s
`BlocConsumer<ProfileEditCubit>.listener` → `LanguageBloc.add` → `LanguageBloc.on<LanguageEventChange>`
→ `LanguageService.setLocale` → `pref.setString`, и параллельно —
`consumeLanguageChangeFlag()`, вызванный синхронно и независимо от исхода)
прослеживается статическим чтением кода и исходников пакета `bloc`
(`bloc-9.0.1`, версия зафиксирована в `pubspec.lock`) и `talker_bloc_logger`
(`5.0.1`). Единственная не разрешённая статическим чтением деталь — гонка
между `saveChanges()` и Hive `ValueListenable`-подпиской кубита, влияющая
только на `state.loading` в авторизованной ветке (см. «Альтернативные
потоки»/«Открытые вопросы»), не на итоговый исход применения языка.
Исправление (например, обёртка `try/catch` вокруг `LanguageService.setLocale()`
внутри `LanguageBloc`, отдельное состояние ошибки, различимое от успеха, или
чтение `user.locale` в `UserModel.fromUser` как минимум для обнаружения
расхождения) в рамках этого документирующего прохода не выполняется.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/language/language_bloc.dart` | `LanguageBloc.on<LanguageEventChange>` | CURRENT | единственное место, вызывающее `LanguageService.setLocale`; не обёрнуто в собственный `try/catch` |
| `lib/pages/language/language_bloc.dart` | `LanguageEventChange`, `LanguageStateChanged`, `LanguageStateInitial` | CURRENT | событие/состояния; `LanguageStateChanged` не эмитится, если `setLocale` бросает исключение |
| `lib/l10n/language_service.dart` | `LanguageService.setLocale`, `.locale` (static getter/поле `_locale`) | CURRENT | `pref.setString` — источник возможного исключения; `_locale = newLocale` не достигается при отказе |
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.consumeLanguageChangeFlag` | CURRENT | сбрасывает `isLanguageChanged` синхронно, независимо от исхода `LanguageEventChange` |
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.load` | CURRENT | вызывается либо через `BlocListener<LanguageBloc>` (только при успехе), либо через Hive `ValueListenable` (`_listener`), независимо от исхода применения языка |
| `lib/pages/profile/cubit/profile_edit_state.dart` | `ProfileEditStateExtension.isDataChanged` | CURRENT | остаётся `true` по локали, пока `currentUserData`/`newUserData` не сведены — держит кнопку «Сохранить» видимой |
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | `ProfileSettingsView.build` (внешний `BlocListener<LanguageBloc, LanguageStateInitial>`, внутренний `BlocConsumer<ProfileEditCubit, ProfileEditState>.listener`) | CURRENT | диспатчит `LanguageEventChange` и вызывает `consumeLanguageChangeFlag()` синхронно в одном колбэке; отдельный `BlocListener<LanguageBloc>` реагирует только на `LanguageStateChanged`, никогда не срабатывает в этом сценарии |
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | `_ProfileSettingsRegionAndLanguage.build` | CURRENT | вычисляет отображаемый язык из `state.newUserData?.locale ?? LanguageService.locale` — показывает запрошенный, но не применённый язык, пока кубит жив |
| `lib/pages/profile/data/user_model.dart` | `UserModel.fromUser` | CURRENT | итоговое поле `locale` берётся из параметра `selectedLanguage` (=`LanguageService.locale`), `user.locale` игнорируется — маскирует расхождение с сервером/Hive при пересоздании кубита |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.updateUser`, `._saveMainAuthData` | CURRENT | предшествующий шаг (вне рамок этого use-case) — уже успешно персистирует новое `User.locale` на сервере и в Hive `AUTH_BOX/userKey` до точки отказа этого сценария |
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit` (конструктор, поля `_valueListenable`/`_listener`) | CURRENT | подписка на Hive `AuthRepository.userKey`, независимо перевызывающая `load()` — источник гонки, влияющей на `state.loading` в авторизованной ветке |
| `lib/widgets/button/button.dart` | `BlackCircleButton` (`onTap: !isLoading ? onTap : () {}`) | CURRENT | игнорирует нажатие, пока `isLoading == true` — потенциально блокирует повторную попытку в авторизованной ветке |
| `lib/main.dart` | `MyApp.build` (`BlocBuilder<LanguageBloc, LanguageStateInitial>` → `MaterialApp.router(locale: ...)`) | CURRENT | фактически применяемый язык приложения читается из `LanguageBloc.state.language`, не из `ProfileEditCubit`/`User.locale` напрямую |
| `lib/main.dart` | `main` | CURRENT | `runApp(const MyApp())` без `runZonedGuarded`/`runTalkerZonedGuarded` (закомментировано) — необработанная асинхронная ошибка `handleEvent()` не долетает ни до какого дополнительного глобального обработчика |
| `lib/injection_container.dart` | `Bloc.observer = TalkerBlocObserver(...)` | CURRENT | единственный канал, получающий факт отказа — дев-only, невидим пользователю |
| `package:bloc` (`bloc-9.0.1`, см. `pubspec.lock`) | `Bloc.on<E>` (внутренний `handleEvent`) | CURRENT (внешняя зависимость) | перехватывает исключение обработчика, вызывает `onError`, затем `rethrow` внутри необслуживаемого `Future` — не влияет на вызывающий код `add()` |
| `package:talker_bloc_logger` (`5.0.1`, см. `pubspec.lock`) | `TalkerBlocObserver.onError` | CURRENT (внешняя зависимость) | `_talker.error('LanguageBloc', error, stackTrace)` — единственное действие с исключением |

## Критерии приёмки

- Если `pref.setString` внутри `LanguageService.setLocale` бросает исключение
  любого типа, `LanguageBloc.on<LanguageEventChange>` не эмитит
  `LanguageStateChanged`; `LanguageBloc.state` остаётся равным состоянию до
  диспатча; `LanguageService.locale` не меняется.
- Исключение долетает ровно до одного канала — `Bloc.observer.onError` →
  `TalkerBlocObserver.onError` → `Talker.error('LanguageBloc', ...)` — и ни до
  какого пользовательского UI-сигнала (snackbar, диалог, индикатор ошибки).
- `ProfileEditCubit.state.isLanguageChanged` становится `false` сразу после
  диспатча `LanguageEventChange`, независимо от того, успешно ли впоследствии
  завершится сам `LanguageEventChange` — нет пути, которым технический отказ
  этого сценария заново выставил бы флаг или иным образом сообщил кубиту о
  неудаче.
- `ProfileSettingsView`'s `BlocListener<LanguageBloc, LanguageStateInitial>`
  не вызывает ни `ProfileEditCubit.load()`, ни
  `DataUpdateBloc.add(DataUpdateStartAll(...))` в этом сценарии.
- `MaterialApp.router`'s фактический `locale` не меняется — приложение
  продолжает отображаться на прежнем языке.
- `state.newUserData?.locale` остаётся равным запрошенному, но не
  применённому языку, пока жив тот же экземпляр `ProfileEditCubit`;
  `ProfileEditStateExtension.isDataChanged` остаётся `true` по локали, кнопка
  «Сохранить» остаётся видимой.
- При пересоздании `ProfileEditCubit` (`load()` вызван заново) и
  `currentUserData.locale`, и `newUserData.locale` становятся равны
  `LanguageService.locale` (прежнему значению) — попытка смены языка не
  восстанавливается и не переносится дальше этим путём, независимо от того,
  что для авторизованного `User.locale` на сервере/в Hive уже содержит новое
  значение.

## Связанные тесты

- `test/pages/language_bloc_test.dart`, group `'UC-165/UC-165 — LanguageBloc.LanguageEventChange
  (общий код, оба актора)'`, test `'LanguageEventChange -> сохраняет в pref,
  эмитит Changed с новым языком'` — покрывает только **успешный** путь
  (`pref` — реальный `SharedPreferences` с `setMockInitialValues({})`, не
  умеет симулировать отказ `setString`); `setUp`/`setUpAll` этого файла не
  регистрируют `Bloc.observer`/`Talker` вовсе — технический отказ обработчика
  в этом файле сегодня физически не проверяем без дополнительного мока
  хранилища, бросающего исключение на `setString`.
- `test/pages/profile_edit_cubit_test.dart`, group `'ProfileEditCubit —
  редактирование'`, test `'consumeLanguageChangeFlag сбрасывает флаг, если он
  выставлен'` — покрывает только сам факт сброса флага изолированно, без
  какого-либо `LanguageBloc`/`LanguageEventChange` в тесте вовсе.
- `test/pages/profile_edit_cubit_test.dart`, group `'UC-165 — ProfileEditCubit.saveChanges
  (гость, смена языка)'`, test `'locale изменился -> isLanguageChanged:true,
  возвращает false, currentUserData не тронут'` — покрывает только
  предшествующий этому use-case шаг (эмиссию `isLanguageChanged: true`
  кубитом), только для гостя, без дальнейшей оркестрации
  `ProfileSettingsView`/`LanguageBloc`.
- Виджет-тестов `ProfileSettingsView` нет вовсе: `grep -rl "ProfileSettingsView\|profile_settings_view"
  test/` не находит ни одного файла — цепочка `BlocListener<LanguageBloc>` +
  `BlocConsumer<ProfileEditCubit>.listener` (диспатч `LanguageEventChange` и
  вызов `consumeLanguageChangeFlag()` в одном колбэке) не покрыта ни одним
  тестом ни в успешном, ни в отказном варианте.

**TBD — теста нет** ни на технический отказ `LanguageService.setLocale`/`pref.setString`,
ни на то, что `isLanguageChanged` гасится независимо от исхода
`LanguageEventChange`, ни на отсутствие реакции `BlocListener<LanguageBloc>`
при отсутствующем `LanguageStateChanged`, ни на гонку `state.loading` между
`saveChanges()` и Hive `ValueListenable`-подпиской в авторизованной ветке.

## Открытые вопросы и ограничения

- **Не проверено эмпирически, способен ли `pref.setString` (плагин
  `shared_preferences`, версия зафиксирована в `pubspec.lock`) реально
  бросить исключение на реальном устройстве** (например, при сбое записи на
  диск, превышении лимита платформенного канала, гонке с параллельной
  инициализацией) — вывод о последствиях сделан исключительно статическим
  чтением кода (`LanguageBloc`/`LanguageService`/пакет `bloc`), при условии,
  что такое исключение произошло; сам факт его правдоподобности не
  верифицирован против реального бэкенда/платформы.
- **Гонка `state.loading` в авторизованной ветке не разрешена.** Emit
  `state.copyWith(isLanguageChanged: true)` внутри `saveChanges()` не
  сбрасывает `loading` явно (в отличие от гостевой ветки того же условия);
  сбросится ли оно фактически, зависит от того, успеет ли независимая Hive
  `ValueListenable`-подписка кубита (реагирующая на тот же `AuthRepository.userKey`,
  уже записанный `updateUser()` раньше в этой же последовательности) вызвать
  `load()` раньше, чем пользователь заметит зависшую кнопку «Сохранить» —
  порядок этой гонки не установлен ни чтением кода, ни тестом.
- **`UserModel.fromUser` игнорирует `user.locale` — не задокументировано
  нигде как осознанное решение.** Может быть намеренным (чтобы поле «текущий
  язык» экрана профиля всегда отражало реально применённый
  `LanguageService.locale`, а не то, что записано в `User`), но побочный
  эффект — постоянное расхождение между [ENT-1](../entities/ENT-1-USER-IN-AUTH.md)
  (сервер+Hive) и приложением остаётся невидимым и не самовосстанавливается
  ни одним путём чтения профиля.
- Никакого способа для пользователя увидеть, что применение языка не
  удалось, не существует ни на этом экране, ни где-либо ещё в приложении —
  единственный след отказа (`Talker.error`) недоступен обычному
  пользователю.
