# UC-164 — Технический отказ сохранения профиля тонет в `catch`: пользователь не получает ни успеха, ни ошибки

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-82](../events/EVT-82-USER-PROFILE-EDITED-IN-PROFILE.md) |
| Сущность | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) |
| Результат | `UPDATE_ERROR` |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |

## Назначение

Тот же сценарий, что описан в [EVT-82](../events/EVT-82-USER-PROFILE-EDITED-IN-PROFILE.md) —
авторизованный пользователь правит имя/email/телефон/страну на экране
`ProfileSettingsPage` и нажимает «Сохранить» (`ProfileEditCubit.saveChanges()`)
— но здесь сетевой вызов `AuthRepository.updateUser()` не завершается успехом.
Найдено и проверено чтением кода **два независимых пути**, оба ведущие в один
и тот же единственный `catch`-блок `saveChanges()`:

- (а) `rpcClientSHTP.call(message)` бросает исключение — сеть недоступна,
  таймаут, либо любой не-2xx HTTP-ответ (`CustomDioClient.call` логирует его
  через `Talker.error` и безусловно перебрасывает, `rethrow`);
- (б) сетевой вызов формально успешен (HTTP 200), но сервер вернул тело без
  ключа `data` — единственная форма ответа `CustomDioClient.call` возвращает
  «как есть», без исключения, это explicit `{'status': 'error', ...}`; тогда
  строка `final userJson = response['data'] as Map<String, dynamic>;` внутри
  `updateUser()` бросает `TypeError` (приведение `null` к `Map<String, dynamic>`
  проваливается) — этот путь не проходит через `CustomDioClient`'s `try/catch`
  (он уже успешно вернул управление), исключение рождается на уровень выше, в
  самом `AuthRepository.updateUser()`.

Оба пути **не имеют собственного `try/catch` внутри `AuthRepository.updateUser()`**
— исключение любого из них всплывает наружу необработанным и перехватывается
только в `ProfileEditCubit.saveChanges()`, единственным catch-блоком во всей
цепочке. Там оно только логируется в `Talker` (`getIt<Talker>().handle(e)`) —
без разбора типа/содержимого исключения — и метод возвращает `false`. Вызывающий
виджет (`ProfileSettingsView`) показывает snackbar успеха **только если**
`isSaved == true`; при `false` не показывается вообще ничего — ни ошибки, ни
любого другого сигнала. Отдельная, самостоятельно подтверждённая находка: тот
же самый `false` возвращается и в структурно другом, не-ошибочном случае —
когда `saveChanges()` завершается штатно, но среди изменённых полей была
`locale` (см. [EVT-83](../events/EVT-83-LANGUAGE-CHANGED-IN-PROFILE.md)) — вызывающий
код не может отличить «сеть отказала» от «сохранение прошло успешно, но нужно
сначала применить смену языка»: оба случая дают один и тот же `false` без
какого-либо сопутствующего состояния, различающего причину.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — пользователь приложения,
авторизованный (для гостя `saveChanges()` вообще не доходит до сетевого
вызова — `!_authRepository.isAuthorized()` перехватывает раньше, см.
«Альтернативные потоки»). Действие происходит на экране `ProfileSettingsPage`,
компонент `ProfileSettingsView` (`lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart`),
нажатием кнопки «Сохранить» (`BlackCircleButton`, видна только когда
`state.isDataChanged == true`).

## CURRENT

### Основной поток

1. Пользователь редактирует одно или несколько полей (имя, email, телефон,
   страна) через `editName`/`editFirstName`/`editEmail`/`editPhone`/`selectCountryCode`/`selectCountry`
   — каждый метод пишет в `state.newUserData` поверх `state.currentUserData`,
   `state.isDataChanged` становится `true`, кнопка «Сохранить» появляется
   (`Positioned` в `ProfileSettingsView.build`).
2. Пользователь нажимает «Сохранить»: `onTap` вызывает `await
   context.read<ProfileEditCubit>().saveChanges()`.
3. `saveChanges()`: `emit(state.copyWith(loading: true))` — кнопка переходит
   в `isLoading: true` (`state.loading ?? false` передаётся в `BlackCircleButton`).
   `newUserData = state.newUserData` — непусто (иначе см. «Альтернативные
   потоки»). `_authRepository.isAuthorized()` — истинно (авторизованный
   пользователь), ветка гостя (см. «Альтернативные потоки») не выполняется.
4. `await _authRepository.updateUser(newUserData);` — вызов **не обёрнут**
   в собственный `try/catch` ни на уровне `AuthRepository`, ни между этой
   строкой и внешним `try` в `saveChanges()`.
5. Внутри `updateUser()`: `_userDataForUpdate(user)` собирает тело запроса
   (`user.copyWith(phone: formattedPhone).toUserDTO().toJson()`, с зачисткой
   пустого телефона в `null`); `rpcClientSHTP = getIt.get<ApiClient>(instanceName:
   'farm_rpc')`; `message = ApiMessage(link: '${Constants.authSerivceApi}/user',
   method: ApiMethod.put, data: userData)`. Здесь сценарий расходится на две
   независимо проверенные ветки.

**Ветка (а) — сетевое исключение.**

6а. `final response = await rpcClientSHTP.call(message);` — внутри
    `CustomDioClient.call` (`lib/network/api_client/custom_dio_client.dart`):
    `dio.request(...)` бросает исключение (сеть недоступна, таймаут, либо
    любой не-2xx ответ — `DioClient` не переопределяет `validateStatus`,
    поэтому Dio по умолчанию бросает `DioException` вне 200–299). `catch (e) {
    getIt.get<Talker>().error('CustomDioClient: call: $e'); rethrow; }` —
    исключение логируется и безусловно перебрасывается.
7а. Исключение всплывает из `await rpcClientSHTP.call(message)` (шаг 5),
    покидает `updateUser()` необработанным (в этом методе нет `try/catch`),
    покидает `await _authRepository.updateUser(newUserData);` (шаг 4 этого же
    потока) и попадает в `catch (e)` `saveChanges()` (шаг 8 общего потока).

**Ветка (б) — логически некорректный ответ без исключения на уровне
`CustomDioClient`.**

6б. `dio.request(...)` завершается штатно, HTTP 200, но `response.data` —
    `Map<String, dynamic>` без ключей `data`/`animal_exits` и с
    `response.data['status'] == 'error'` — единственное условие в
    `CustomDioClient.call`, при котором ответ возвращается «как есть», без
    исключения, без ключа `data` (например `{'status': 'error', 'message':
    '...'}`).
7б. `updateUser()` получает этот `response` без исключения. `final userJson =
    response['data'] as Map<String, dynamic>;` — `response['data']` равно
    `null` (ключа нет), приведение `null as Map<String, dynamic>` бросает
    `TypeError`. Этот `TypeError` рождается непосредственно в `updateUser()`,
    вне какого-либо `try` — покидает метод необработанным и попадает в
    `catch (e)` `saveChanges()` тем же путём, что и ветка (а).

### Продолжение общего потока (после любой из веток а/б)

8. `catch (e) { emit(state.copyWith(loading: false)); getIt<Talker>().handle(e);
   return false; }` — единственное, что происходит: `loading` сбрасывается в
   `false` (кнопка перестаёт крутиться), исключение уходит в `Talker`
   (видно только в дев-логах/консоли, не пользователю), метод возвращает
   `false`. Ни тип исключения, ни его сообщение не анализируются и не
   передаются наружу ни в каком виде.
9. Вызывающий код — `onTap` в `ProfileSettingsView`: `final isSaved = await
   context.read<ProfileEditCubit>().saveChanges(); if (context.mounted &&
   isSaved) { showAppSnackBarSuccess(...); }` — условие `isSaved` ложно,
   `if`-блок не выполняется. **Никакого `else`, никакого вызова
   `showAppSnackBarError`, никакого другого визуального сигнала не
   существует в этом файле для случая `isSaved == false`.**
10. Наблюдаемый пользователем итог: кнопка «Сохранить» ненадолго показывает
    индикатор загрузки, затем возвращается в обычное состояние — **не
    отличимое от простого отсутствия действия**. `state.newUserData` не
    сброшен и не откачен к `state.currentUserData` (шаг 8 не трогает ни одно
    из этих двух полей) — введённые пользователем правки остаются видны в
    полях формы, кнопка «Сохранить» остаётся видна дальше (`isDataChanged`
    всё ещё `true`, т.к. `currentUserData` не обновился), и повторное
    нажатие «Сохранить» — единственный доступный пользователю следующий шаг,
    без какой-либо подсказки о том, что предыдущая попытка не удалась.

### Альтернативные потоки

- **Гость не достигает сетевого вызова вовсе.** `if (!_authRepository.isAuthorized())`
  перехватывает раньше строки 4 общего потока — гостевая ветка ограничивается
  `AppCacheService.saveGuestCountryCode()` (тоже без `try/catch`, но эта
  функция — локальная запись в `SharedPreferences`, не сетевой вызов, здесь
  не описывается) и не вызывает `AuthRepository.updateUser()` в принципе:
  этот use-case не применим к гостю.
- **`newUserData == null`.** Если `state.newUserData` пуст (например,
  `saveChanges()` вызван до единственного `load()`), `saveChanges()`
  возвращает `false` до входа в try-ветку сетевого вызова — `if (newUserData
  == null) return false;` находится **внутри** общего `try`, но эта ранняя
  ошибка не связана с сетью и не задействует `catch (e)` вовсе; это отдельный,
  структурно иной путь того же `false`, не описываемый этой спекой (см. also
  «Открытые вопросы»).
- **Смена языка — тот же `false`, другая причина.** Если среди изменённых
  полей — `locale`, `saveChanges()` (после **успешного** `updateUser()`)
  эмитит `isLanguageChanged: true` и тоже возвращает `false` —
  [EVT-83](../events/EVT-83-LANGUAGE-CHANGED-IN-PROFILE.md). С точки зрения
  `onTap` в `ProfileSettingsView` (шаг 9 этого use-case) это **неотличимо** от
  технического отказа, описанного здесь: оба пути дают `isSaved == false`,
  оба не показывают snackbar. Единственное наблюдаемое различие — состояние
  `state.isLanguageChanged`, которое сам виджет кнопки не читает вовсе
  (только отдельный `BlocConsumer.listenWhen` выше по дереву — см.
  «Открытые вопросы»).
- **`UserDTO.fromJson(userJson)`/`_normalizeUserPhoneFields(userJson)` —
  не проверено отдельно.** Если бы `userJson` (уже успешно приведённый к
  `Map<String, dynamic>` в ветке успеха) содержал поля неожиданной формы,
  `UserDTO.fromJson` мог бы бросить собственное исключение — не проверено
  чтением этого конкретного метода как отдельная под-ветка, но по структуре
  кода (тоже вне `try` внутри `updateUser()`) вело бы к тому же самому
  единственному `catch (e)` в `saveChanges()`, тому же исходу, что и ветки
  (а)/(б) — не описывается отдельно, так как не добавляет нового
  наблюдаемого поведения.

### Связанные сущности

- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH) — сущность, чьё
  сохранение отказывает этим сценарием. Локальный Hive-снимок пользователя
  (`AuthRepository._saveMainAuthData`) **не изменяется** ни в одной из веток
  (а)/(б) — код, который бы его записал, находится строго после точки отказа
  внутри `updateUser()`, не достигается. `state.currentUserData` в кубите
  тоже не обновляется (шаг 8 не трогает это поле) — форма продолжает
  показывать введённые, но не сохранённые правки.
- [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) (Country, HANDBOOKS) —
  читается (`_countriesRepository.getAll()`, вызывается заново только внутри
  `load()`, не внутри `saveChanges()`) для отображения выбора страны; не
  изменяется этим сценарием ни в одной ветке.

### Бизнес-правила

- Единственный источник истины о том, «сохранилось или нет» для вызывающего
  кода — булев результат `saveChanges()`; никакого отдельного канала (поле
  состояния, exception-объект, код ошибки) для причины отказа не существует.
- `catch (e)` в `saveChanges()` перехватывает **любое** исключение без
  разбора типа — сетевое (`DioException`/любое из `CustomDioClient`), либо
  локальное приведение типа (`TypeError` из ветки (б)), либо гипотетическое
  из `UserDTO.fromJson` — все они неразличимы для пользователя и для
  вызывающего виджета.
- Нет ретрая, нет backoff — единственный способ повторить попытку —
  повторное нажатие «Сохранить» тем же пользователем, вручную.
- `Talker.handle(e)` — единственный канал, куда вообще попадает факт отказа;
  он не пользовательский (консоль/дев-инструменты), поэтому с точки зрения
  обычного пользователя приложения этот сценарий неотличим от того, что
  ничего не произошло вовсе.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — обе ветки (сетевое исключение в
`CustomDioClient.call` и `TypeError` приведения `response['data']` внутри
`AuthRepository.updateUser()`) воспроизводятся статическим чтением кода
целиком: `ProfileEditCubit.saveChanges` → `AuthRepository.updateUser` →
`CustomDioClient.call`/`DioClient`. Исправление (например, отдельное
пользовательское сообщение об ошибке через `showAppSnackBarError`, различение
причины `false` между веткой (а)/(б) и веткой «нужно применить смену языка»)
в рамках этого документирующего прохода не выполняется — это фиксация уже
существующего кода, а не работа над дефектом.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/profile/cubit/profile_edit_cubit.dart` | `ProfileEditCubit.saveChanges` | CURRENT | единственный `try/catch` во всей цепочке; `catch (e)` не разбирает тип исключения, только логирует и возвращает `false` |
| `lib/pages/profile/cubit/profile_edit_state.dart` | `ProfileEditState`, `ProfileEditStateExtension.isDataChanged` | CURRENT | `loading`/`newUserData`/`currentUserData` — ни одно не сигнализирует причину отказа |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.updateUser`, `._userDataForUpdate`, `._normalizeUserPhoneFields`, `._saveMainAuthData` | CURRENT | сетевой PUT-вызов и разбор ответа — без собственного `try/catch`; строка `response['data'] as Map<String, dynamic>` — источник ветки (б) |
| `lib/network/api_client/custom_dio_client.dart` | `CustomDioClient.call` | CURRENT | источник ветки (а) — логирует через `Talker.error` и `rethrow` любое исключение `dio.request`; источник формы ответа ветки (б) — единственная ветвь, возвращающая `response.data` без ключа `data` при явном `status: 'error'` |
| `lib/network/dio_client.dart` | `DioClient` | CURRENT | не переопределяет `validateStatus` — Dio по умолчанию бросает исключение на любом не-2xx ответе, база для ветки (а) |
| `lib/constants.dart` | `Constants.authSerivceApi` | CURRENT | эндпоинт `PUT {authSerivceApi}/user` |
| `lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` | `ProfileSettingsView.build` (кнопка «Сохранить», `onTap`) | CURRENT | единственный вызывающий код; показывает snackbar успеха только при `isSaved == true`, никакой ветки на `false` |
| `lib/widgets/app_snackbar.dart` | `showAppSnackBarSuccess`, `showAppSnackBarError` | CURRENT | `showAppSnackBarError` существует в проекте, но не вызывается ни в одном месте этого сценария |
| `sheep_farm_database` / `packages/sheep_farm_database/lib/entities/user/user.dart` | `User`, `UserDTO` | CURRENT | доменная модель/DTO, участвующие в `_userDataForUpdate`/`UserDTO.fromJson` |

## Критерии приёмки

- Если `rpcClientSHTP.call(message)` внутри `AuthRepository.updateUser()`
  бросает исключение любого типа, оно всплывает необработанным до
  `catch (e)` в `ProfileEditCubit.saveChanges()`; `state.loading` становится
  `false`, `state.currentUserData`/`state.newUserData` не изменяются,
  `getIt<Talker>().handle(e)` вызывается ровно один раз, метод возвращает
  `false`.
- Если тот же вызов возвращает ответ без ключа `data` (в частности —
  explicit `{'status': 'error', ...}` без исключения на уровне
  `CustomDioClient`), строка `response['data'] as Map<String, dynamic>`
  бросает `TypeError`, который проходит тем же путём до того же `catch (e)`,
  с тем же итоговым состоянием и тем же возвратом `false`.
- В обоих случаях `ProfileSettingsView`'s `onTap` не показывает никакого
  snackbar (ни успеха, ни ошибки) — `showAppSnackBarSuccess` вызывается
  только при `isSaved == true`.
- Введённые пользователем правки остаются в `state.newUserData` и видны в
  полях формы после отказа; кнопка «Сохранить» остаётся видимой
  (`state.isDataChanged` не меняется отказом).
- Возврат `false` в этом сценарии структурно неотличим для вызывающего кода
  от возврата `false` в ветке «сохранение успешно, но требуется применить
  смену языка» ([EVT-83](../events/EVT-83-LANGUAGE-CHANGED-IN-PROFILE.md)) — ни одна
  из двух причин не передаётся наружу отдельным сигналом, доступным `onTap`.

## Связанные тесты

`test/pages/profile_edit_cubit_test.dart` существует и содержит группу
`'ProfileEditCubit.saveChanges — edge cases'` с единственным тестом
`'newUserData:null (load() ни разу не вызывался) -> возвращает false, ничего
не эмитит кроме loading'` — это соседний по возврату `false`, но структурно
другой путь (ранний выход `if (newUserData == null) return false;`, до
входа в сетевой вызов, не задействующий `catch (e)` вовсе), не сценарий этого
файла. Группы `'UC-163 — ProfileEditCubit.saveChanges (гость, без смены
языка)'` и `'UC-165 — ProfileEditCubit.saveChanges (гость, смена языка)'`
покрывают только гостевую ветку (без сетевого вызова) — тоже не этот
сценарий. Ни один тест в файле не регистрирует `AuthRepository` как мок
(`grep -rln "MockAuthRepository" test/` не находит этот файл) — `setUp`
регистрирует реальный `AuthRepository()` поверх Hive-тестового бокса; ни
один тест не переводит пользователя в авторизованное состояние (сохраняя
`TokenDataHive`/`UserHive` в бокс, как делает группа `'UC-161 —
ProfileEditCubit.load (авторизован)'`) и одновременно не вызывает
`saveChanges()` — авторизованная ветка `saveChanges()` в этом файле не
вызывается вообще ни разу, ни в успешном, ни в отказном варианте. Также
`Talker` не зарегистрирован в `getIt` ни в одном `setUp` этого файла — тест,
который довёл бы `saveChanges()` до `catch (e)` в авторизованной ветке
сегодня, дополнительно упал бы на `getIt<Talker>().handle(e)` (не
зарегистрирован), пока не будет добавлена регистрация `MockTalker`
(`test/helpers/mocks.dart`) в `setUp`.

**TBD — теста нет** ни на ветку (а) (сетевое исключение из
`AuthRepository.updateUser` в авторизованной ветке `saveChanges()`), ни на
ветку (б) (`TypeError` из `response['data'] as Map<String, dynamic>` при
ответе без ключа `data`), ни на итоговое поведение `ProfileSettingsView`
(отсутствие snackbar при `isSaved == false`) — последнее вообще не
покрывается юнит-тестом кубита, потребовало бы widget-теста.

## Открытые вопросы и ограничения

- **Официальный дефект, не предмет этого прохода.** `catch (e)` в
  `saveChanges()` не различает тип исключения и не выставляет никакого
  состояния ошибки — единственный сигнал вызывающему коду — `false`,
  неотличимый от штатного «нужно сначала подтвердить смену языка». Экран не
  показывает пользователю никакого сообщения об отказе — ни через
  `showAppSnackBarError` (существует в проекте, не используется здесь), ни
  любым другим способом. Является ли это осознанным решением (например,
  ожидание, что `updateUser()` почти никогда не отказывает) или недосмотром —
  ничем в коде/комментариях не зафиксировано.
- **Ветка (б) зависит от того, что сервер вообще способен вернуть
  `{'status': 'error', ...}` на `PUT {authSerivceApi}/user` с кодом 200** —
  не подтверждено эмпирически против реального бэкенда; вывод сделан
  статическим чтением `CustomDioClient.call` (единственное условие, при
  котором оно возвращает ответ без ключа `data`, без исключения) и
  `AuthRepository.updateUser` (единственное место, приводящее `response['data']`
  к `Map<String, dynamic>` без проверки на `null`).
- **`state.isLanguageChanged` — единственное существующее в состоянии поле,
  которое различает исходы `false`, но только для ветки языка, не для
  ветки этого use-case.** `ProfileSettingsView`'s `onTap` (кнопка
  «Сохранить») его не читает вовсе — читает его отдельный
  `BlocConsumer.listenWhen` выше по дереву виджетов, реагирующий сменой
  языка, а не показом сообщения пользователю о причине `false`.
- Не проверено эмпирически на реальном запуске против настоящего бэкенда —
  вывод по обеим веткам сделан статическим чтением кода
  (`ProfileEditCubit.saveChanges` → `AuthRepository.updateUser` →
  `CustomDioClient.call`/`DioClient`), без запущенного теста, подтверждающего
  любую из двух веток (см. «Связанные тесты» — TBD).
