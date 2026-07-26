# ACTOR-1 — Авторизованный пользователь

## Идентичность

Пользователь, успешно прошедший вход — `AuthRepository.isAuthorized()` возвращает `true` тогда и только тогда, когда сохранён главный токен (`getMainTokenData() != null`). Отдельного флага сессии в приложении нет.

Это сквозной актор: он будет использоваться и другими модулями по мере их специфицирования (FARM/ANIMAL/BOARD/PROFILE), не только AUTH. Суффикс `-IN-AUTH` закреплён с самого начала, а не перенесён позже — AUTH — модуль, чья собственная бизнес-логика (`isAuthorized()`) определяет, что значит быть этим актором, вне зависимости от того, в каком модуле его действие используется первым (`../actors/AGENTS.md`, «Refinement for actors used broadly»).

## Цели

**В AUTH**: выйти из аккаунта или удалить аккаунт по собственному решению.

## Действия

**AUTH**: инициирует [EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md) (выход из аккаунта) и [EVT-9](../events/EVT-9-USER-ACCOUNT-DELETION-REQUESTED-IN-AUTH.md) (запрос удаления аккаунта) через `AuthBloc` (`lib/pages/profile/bloc/auth_bloc.dart`, обработчики `AuthEventLogout`/`AuthEventDeleteAccount`).

**FARM** (пропуск исправлен ретроактивно — этот абзац следовало дополнить ещё при специфицировании FARM, актор уже цитировался событиями `EVT-10`…`EVT-17`/`EVT-102`/`EVT-103`, но не был здесь описан): инициирует [EVT-10](../events/EVT-10-FARM-CREATED-IN-FARM.md) (создание фермы), [EVT-11](../events/EVT-11-FARM-EDITED-IN-FARM.md) (редактирование фермы), [EVT-15](../events/EVT-15-PLACE-CREATED-IN-FARM.md) (создание места), [EVT-16](../events/EVT-16-PLACE-EDITED-IN-FARM.md) (редактирование места), [EVT-17](../events/EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md) (удаление места, при условии отсутствия закреплённых животных), [EVT-102](../events/EVT-102-FARM-CARD-VIEWED-IN-FARM.md) (просмотр карточки фермы со статистикой и переключение между фермами), [EVT-103](../events/EVT-103-PLACE-CARD-VIEWED-IN-FARM.md) (просмотр карточки места и переключение между местами) через `FarmsAndPlacesBloc`/`MainNavigatorCubit`/`PlaceCubit`.

**BOARD** (первый модуль, где этот актор явно переиспользован, как и было анонсировано в «Идентичность»): инициирует [EVT-68](../events/EVT-68-AD-PUBLISHED-IN-BOARD.md) (публикация объявления), [EVT-69](../events/EVT-69-AD-EDITED-IN-BOARD.md) (правка собственного объявления), [EVT-70](../events/EVT-70-AD-DELETED-IN-BOARD.md) (удаление собственного объявления), [EVT-71](../events/EVT-71-AD-FAVOURITE-TOGGLED-IN-BOARD.md) (добавление/снятие с избранного) через `BoardCubit`/`AdDetailCubit`/`BoardAdCreateBloc`; [EVT-74](../events/EVT-74-MY-ADS-VIEWED-IN-BOARD.md) (список «Мои объявления»), [EVT-75](../events/EVT-75-FAVOURITE-ADS-VIEWED-IN-BOARD.md) (список «Избранное») — read-экраны, специфицированы наравне с мутациями; [EVT-76](../events/EVT-76-MESSAGE-SENT-IN-BOARD.md) (отправка сообщения в чате, включая неявное автосоздание чата первым сообщением), [EVT-77](../events/EVT-77-CHATS-VIEWED-IN-BOARD.md) (список чатов), [EVT-78](../events/EVT-78-MESSAGES-VIEWED-IN-BOARD.md) (переписка) через `MessagesCubit`/`ChatsCubit`.

**SYSTEM (последний модуль в очереди):** инициирует [EVT-94](../events/EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md)
(ручной запуск полного sync-прохода — кнопка «Синхронизировать данные» на
экране «В работе» либо «Повторить» на экране ошибки синка),
[EVT-95](../events/EVT-95-LOCAL-DATA-CLEARED-IN-SYSTEM.md) (очистка
локальных данных при выходе из аккаунта — довершает [EVT-7](../events/EVT-7-USER-LOGGED-OUT-IN-AUTH.md)),
[EVT-98](../events/EVT-98-IN-WORK-SUMMARY-VIEWED-IN-SYSTEM.md) (просмотр
сводного экрана «В работе»), [EVT-99](../events/EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md)
(просмотр календаря событий фермы/места), [EVT-101](../events/EVT-101-DAY-EVENTS-LIST-VIEWED-IN-SYSTEM.md)
(просмотр посуточного списка событий — контейнер между календарём и
отчётом по типу) через `DataUpdateBloc`/`InWorkBloc`/`ReportsCalendarCubit`/
`ReportsDayListCubit`/`FarmDayListCubit`.

Взаимодействует с сущностями [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User), [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) (TokenData), [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm), [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place), [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad), [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) (Chat), [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) (ChatMessage), [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal, ANIMAL), [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) (DataUpdate).

## Ограничения

Удаление аккаунта ([EVT-8](../events/EVT-8-SESSION-INVALIDATED-AUTOMATICALLY-IN-AUTH.md)) не имеет обработки ошибок в вызывающем коде: `AuthRepository.deleteUser` проглатывает любую серверную ошибку, кроме `passwords.token`-типа, без исключения, поэтому `AuthBloc` считает операцию успешной и делает локальный логаут, даже если аккаунт на сервере не был удалён.

## Исходный код

| Файл | Класс/метод | Роль |
|---|---|---|
| `lib/pages/profile/bloc/auth_bloc.dart` | `AuthBloc.on<AuthEventLogout>`, `on<AuthEventDeleteAccount>` | принимает logout/удаление аккаунта |
| `lib/repositories/auth/auth_repository.dart` | `AuthRepository.isAuthorized`, `logout`, `deleteUser` | источник признака авторизованности; выполняет logout/удаление |
