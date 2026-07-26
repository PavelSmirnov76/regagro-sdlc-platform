# UC-1 — Гость саморегистрируется, регистрация принята сервером

## Назначение

Гость без сохранённого главного токена заполняет форму регистрации и
отправляет её; сервер принимает данные, и клиент показывает состояние
успеха. Это happy-path сценарий события [EVT-1](../events/EVT-1-USER-SELF-REGISTERED-IN-AUTH.md) (`user.self_registered`).

## Пользователь

[ACTOR-2](../actors/ACTOR-2-GUEST-IN-AUTH.md) — Гость (`AuthRepository.isAuthorized() == false`); гостевой доступ
не требует отдельного выбора — им является любой пользователь без сохранённого
токена.

## CURRENT

### Основной поток

1. Гость открывает экран регистрации (маршрут `Routes.registration` →
   `RegistrationPage` → `RegistrationView`). `RegistrationCubit.loadHandbooks`
   подгружает справочники (страны, типы животных, юридические формы, типы
   организаций, типы маркеров) и предзаполняет страну/тип животных значением
   по умолчанию (сохранённый код страны гостя либо локаль устройства, первый
   элемент списка — как крайний фолбэк).
2. Гость заполняет обязательные поля формы: страна, тип животных, email,
   пароль, подтверждение пароля, имя (`requiredField: true` в
   `RegistrationView`) — остальные поля (юридическая форма, тип организации,
   телефон, данные организации/руководителя, тип маркера) необязательны.
3. Гость нажимает кнопку отправки. `formKey.currentState.validate()`
   (Flutter `Form`) прогоняет валидаторы полей — включая совпадение пароля и
   подтверждения — прежде чем вызвать `RegistrationCubit.submit()`; при
   провале валидации `submit()` не вызывается вовсе.
4. `RegistrationCubit.submit` эмитит `isSubmitting: true, isSuccess: false,
   errorMessage: null`, затем собирает `RegistrationRequest` из текущего
   `state.data`.
5. `AuthRepository.registerSelf` отправляет `POST
   {Constants.authSerivceApi}/registration/self` через `ApiClient`
   (`farm_rpc`-инстанс), тело — `RegistrationRequest.toJson()`. Ни на одном
   шаге данные формы не сохраняются локально — только передаются в теле
   запроса.
6. Сервер отвечает успехом (2xx) → `RegistrationCubit.submit` эмитит
   `isSubmitting: false, isSuccess: true`. Тело ответа (`Map<String,
   dynamic>`) `registerSelf` возвращает вызывающему коду, но
   `RegistrationCubit.submit` его не читает и никак не использует — только
   дожидается завершения вызова.
7. Дальнейший автовход тем же email/паролем — отдельное событие ([EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md)),
   не часть этого сценария.

### Альтернативные потоки

- Юридическая форма не выбрана в форме (`data.legalForm == null`) →
  `RegistrationRequest.legalFormId` подставляется равным `2` по умолчанию
  (`data.legalForm?.id ?? 2` в `RegistrationCubit.submit`) — единственное
  автоматическое дополнение данных перед отправкой.
- Необязательные поля не заполнены (телефон, тип организации, название/номер
  организации, имя/фамилия руководителя, тип маркера) → соответствующие ключи
  вовсе не попадают в JSON тела запроса (`RegistrationRequest.toJson`
  использует условное включение `if (... != null)`), а не отправляются как
  `null`.

### Связанные сущности

- [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User) — регистрируемая учётная запись; сценарий её создаёт на
  сервере, но ответ сервера локально не парсится в `User`/`UserDTO` и нигде
  не сохраняется — этот сценарий только отправляет данные.
- [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) (Session/TokenData) — этим сценарием **не** устанавливается: успех
  регистрации не создаёт и не сохраняет токен — сессия появляется только
  после отдельного автовхода ([EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md)), не описанного здесь.
- Справочники, из которых собирается тело запроса (страна, тип животных,
  юридическая форма, тип организации, тип маркера) — домен `HANDBOOKS`, ещё
  не специфицированы отдельными `ENT`-id на момент написания.

### Бизнес-правила

- Обязательные поля формы: страна, тип животных, email, пароль, подтверждение
  пароля, имя. Совпадение пароля/подтверждения проверяется валидатором формы
  до вызова `submit()`, не внутри кубита/репозитория.
- Отсутствующая юридическая форма → `legal_form_id = 2` по умолчанию,
  подставляется на уровне `RegistrationCubit.submit`, а не на сервере и не в
  `RegistrationRequest`.
- `locale` в теле запроса — всегда текущий язык приложения
  (`LanguageService.locale`), а не отдельно выбираемое в форме значение; в
  форме регистрации нет поля выбора локали.
- Ни на одном шаге данные формы не пишутся в локальное хранилище (ни Hive, ни
  Drift) — весь сценарий это один прямой сетевой вызов.

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Нет — сценарий полностью реализован в коде и покрыт тестом, ничего не
отложено и не заблокировано.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/routes.dart` | `Routes.registration` | CURRENT | маршрут экрана регистрации |
| `lib/pages/registration/presentation/registration_page.dart` | `RegistrationPage` | CURRENT | точка входа страницы, читает опциональный prefill из extra |
| `lib/pages/registration/presentation/widgets/registration_view.dart` | `RegistrationView` | CURRENT | форма регистрации, валидация обязательных полей и совпадения паролей до вызова submit |
| `lib/pages/registration/cubit/registration_cubit.dart` | `RegistrationCubit.submit` | CURRENT | сборка `RegistrationRequest` из состояния и вызов репозитория, управление `isSubmitting`/`isSuccess` |
| `lib/pages/registration/cubit/registration_cubit.dart` | `RegistrationCubit.loadHandbooks` | CURRENT | подгрузка справочников и предзаполнение страны/типа животных перед формой |
| `lib/pages/registration/cubit/registration_data.dart` | `RegistrationData` | CURRENT | модель данных формы регистрации |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.registerSelf` | CURRENT | POST `{authSerivceApi}/registration/self`, данные не сохраняются локально |
| `lib/repositories/auth/models/registration_request.dart` | `RegistrationRequest.toJson` | CURRENT | тело запроса; условное включение опциональных полей, `country` сериализуется строкой |
| `lib/l10n/language_service.dart` | `LanguageService.locale` | CURRENT | источник значения `locale` в теле запроса — текущий язык приложения |
| `lib/constants.dart` | `Constants.authSerivceApi` | CURRENT | базовый URL, к которому строится путь `/registration/self` |

## Критерии приёмки

- Гость без сохранённого главного токена (`AuthRepository.isAuthorized() ==
  false`) может открыть форму регистрации, заполнить обязательные поля
  (страна, тип животных, email, пароль, подтверждение пароля, имя) и
  отправить форму.
- При успешном ответе сервера на `POST {authSerivceApi}/registration/self`
  `RegistrationCubit.state.isSuccess == true` и `state.isSubmitting == false`.
- Если юридическая форма не выбрана, тело запроса содержит `legal_form_id:
  2`.
- Поле `locale` в теле запроса равно текущему языку приложения
  (`LanguageService.locale`), независимо от того, что выбрано в остальных
  полях формы.
- Ни до, ни после отправки запроса данные формы не появляются ни в одной
  локальной таблице/Hive-боксе.

## Связанные тесты

`test/pages/registration_cubit_test.dart`, group `'UC-1/UC-2 — RegistrationCubit.submit'`, конкретно `test('UC-29: успех -> isSuccess:true')`.

## Открытые вопросы и ограничения

- `AuthRepository.registerSelf` не проверяет сетевое соединение перед вызовом
  (в отличие от `AuthRepository.login`, который явно вызывает
  `NetworkConnectivityService.hasConnection()`) — при отсутствии сети
  сценарий полагается на то, что сам Dio-вызов упадёт исключением; это ветвь
  другого (ERROR) use-case, не этого.
- Тело успешного ответа сервера (`Map<String, dynamic>`, возвращаемое
  `registerSelf`) нигде не используется вызывающим кодом — ни для заполнения
  `User`, ни для получения токена; следующий шаг (автовход, [EVT-3](../events/EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md)) выполняет
  отдельный `login`-запрос с тем же email/паролем, а не переиспользует данные
  ответа регистрации.
