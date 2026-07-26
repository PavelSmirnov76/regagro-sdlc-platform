# ACTOR-5 — Пользователь приложения (регистрация/ведение животного)

## Идентичность

Текущий пользователь приложения, независимо от статуса авторизации — регистрация и ведение животного одинаково доступны и гостю, и авторизованному пользователю. Отличается от [ACTOR-1](ACTOR-1-USER-IN-AUTH.md) (строго авторизованный) и [ACTOR-2](ACTOR-2-GUEST-IN-AUTH.md) (строго до входа, специфичен для сценариев самого входа/регистрации аккаунта) — это третья, самостоятельная идентичность: «кто угодно, кто сейчас пользуется приложением».

Сквозной внутри `ANIMAL`: все семь под-областей модуля (REG/MOVE/VAC/WEIGH/DISP/REPRO/INV) будут его переиспользовать по мере специфицирования, не заводить копию.

## Цели

Завести новое животное со всеми нужными атрибутами и идентификационными метками; отредактировать данные уже заведённого животного.

## Действия

**REG (на сегодня — единственная специфицированная под-область):** инициирует [EVT-22](../events/EVT-22-ANIMAL-REGISTERED-LOCALLY-IN-ANIMAL.md) (регистрация), [EVT-23](../events/EVT-23-ANIMAL-LOCAL-EDITED-IN-ANIMAL.md) (правка ещё не синхронизированного животного), [EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md) (правка уже синхронизированного животного, отправка отложена до sync) через `AnimalRegistrationBloc`/`AnimalEditBloc`.

**MOVE:** инициирует [EVT-27](../events/EVT-27-MOVEMENT-RECORDED-IN-ANIMAL.md) (перемещение), [EVT-28](../events/EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md) (отмена из хаба неотправленных), [EVT-29](../events/EVT-29-MOVEMENT-DELETED-VIA-REPORT-IN-ANIMAL.md) (отмена с экрана дневного отчёта) через `AnimalMovementBloc`/`UnsentMovementsCubit`/`MovementReportCubit`; также [EVT-104](../events/EVT-104-MOVEMENTS-VIEWED-UNSENT-IN-ANIMAL.md) (хаб неотправленных) и [EVT-105](../events/EVT-105-MOVEMENTS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) (посуточный отчёт) — два read-экрана, добавлены отдельным проходом, закрывая ранее отложенный пробел (как и было сделано для аналогичных read-экранов VAC/WEIGH/DISP/INV).

**VAC:** инициирует [EVT-32](../events/EVT-32-VACCINATION-RECORDED-IN-ANIMAL.md) (запись вакцинации, для одного или нескольких животных), [EVT-33](../events/EVT-33-VACCINATION-EDITED-UNSENT-IN-ANIMAL.md) (правка ещё не отправленной записи), [EVT-34](../events/EVT-34-VACCINATION-DELETED-UNSENT-IN-ANIMAL.md) (удаление ещё не отправленной записи, одной или нескольких разом) через `VaccinationBloc`/`UnsentVaccinationEditBloc`/`UnsentVaccinationCubit`; также [EVT-39](../events/EVT-39-VACCINATIONS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md) (список вакцинаций животного), [EVT-40](../events/EVT-40-VACCINATIONS-VIEWED-UNSENT-IN-ANIMAL.md) (хаб неотправленных), [EVT-41](../events/EVT-41-VACCINATIONS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) (посуточный отчёт) — три read-экрана, специфицируются наравне с мутациями. Правка и «мягкое» удаление уже синхронизированной записи технически реализованы, но недостижимы ни из одного экрана — см. [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md).

**WEIGH:** инициирует [EVT-42](../events/EVT-42-ANIMAL-WEIGHING-RECORDED-IN-ANIMAL.md) (взвешивание одного или нескольких животных подряд), [EVT-43](../events/EVT-43-ANIMAL-WEIGHING-EDITED-IN-ANIMAL.md) (правка одного взвешивания — явно из хаба или автоматически, если у животного уже есть взвешивание за сегодня), [EVT-44](../events/EVT-44-ANIMAL-WEIGHING-DELETED-UNSENT-IN-ANIMAL.md) (удаление ещё не отправленного взвешивания) через `WeighAnimalCubit`/`AnimalWeighingsCubit`; также [EVT-47](../events/EVT-47-ANIMAL-WEIGHINGS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md) (история взвешиваний животного, со среднесуточным привесом), [EVT-48](../events/EVT-48-ANIMAL-WEIGHINGS-VIEWED-UNSENT-IN-ANIMAL.md) (хаб неотправленных), [EVT-49](../events/EVT-49-ANIMAL-WEIGHINGS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) (посуточный отчёт). Удаление/повторная отправка уже синхронизированного взвешивания технически реализованы, но недостижимы ни с одного экрана — см. [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md).

**DISP:** инициирует [EVT-50](../events/EVT-50-DISPOSAL-RECORDED-IN-ANIMAL.md) (выбытие одного или нескольких животных, включая сценарий «между фермами одного владельца»), [EVT-51](../events/EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md) (отмена группы из хаба неотправленных), [EVT-52](../events/EVT-52-DISPOSAL-DELETED-VIA-REPORT-IN-ANIMAL.md) (отмена с экрана дневного отчёта) через `AnimalDisposalBloc`/`UnsentDisposalsCubit`/`DisposalReportCubit`; также [EVT-55](../events/EVT-55-DISPOSALS-VIEWED-UNSENT-IN-ANIMAL.md) (хаб неотправленных), [EVT-56](../events/EVT-56-DISPOSALS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) (посуточный отчёт). Также инициирует кросс-областной [EVT-57](../events/EVT-57-ANIMAL-HISTORY-VIEWED-IN-ANIMAL.md) («История животного», объединяет MOVE/VAC/WEIGH/DISP/REG в одну ленту — обнаружен и специфицирован при прохождении DISP, но принадлежит модулю ANIMAL в целом, не отдельной под-области) через `AnimalHistoryCubit`.

**REPRO:** инициирует [EVT-58](../events/EVT-58-ANIMAL-PARENT-LINKED-IN-ANIMAL.md) (привязка родителя — из списка кандидатов или вручную, «не зарегистрировано»), [EVT-59](../events/EVT-59-ANIMAL-CHILD-LINKED-IN-ANIMAL.md) (привязка потомка — изменяет запись ВЫБРАННОГО животного, не просматриваемого), [EVT-60](../events/EVT-60-ANIMAL-REPRODUCTION-VIEWED-IN-ANIMAL.md) (просмотр экрана «Разведение») через `ReproductionCubit`. Не заводит новой сущности — родители/потомки хранятся полями прямо на [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md); push/pull переиспользует [EVT-24](../events/EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md)/[EVT-26](../events/EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md) (REG). Шаг «Родословная» визарда регистрации технически существует, но недостижим — см. [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md).

**INV:** инициирует [EVT-61](../events/EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md) (завершение сессии сканирования), [EVT-62](../events/EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md) (правка уже сохранённой сессии, из хаба «В работе»), [EVT-67](../events/EVT-67-ANIMAL-INVENTORY-REPORT-EXPORTED-IN-ANIMAL.md) (экспорт итогового отчёта в Excel/PDF) через `ScanningBloc`; также [EVT-65](../events/EVT-65-ANIMAL-INVENTORY-VIEWED-UNSENT-IN-ANIMAL.md) (хаб неотправленных сессий), [EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) (итоговый отчёт по сессии/дню) через `UnsentInventoriesCubit`/`InventoryReportDetailsCubit`. Не заводит новой сущности связи с [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) на уровне БД — сопоставление метки с животным целиком вычисляется на клиенте, см. [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md).

Взаимодействует с сущностями [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md), [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md), [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md), [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md), [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md), [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md), [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md).

Все семь под-областей `ANIMAL` теперь специфицированы через этого актора.

**BOARD (первый модуль за пределами ANIMAL, где этот актор переиспользован —
в пределах допустимого без переноса суффикса, `../../2-specs/actors/AGENTS.md`,
«for an actor used by one or two modules beyond its home»):** инициирует
[EVT-72](../events/EVT-72-ADS-FEED-VIEWED-IN-BOARD.md) (лента объявлений —
поиск/фильтры/пагинация, доступна и гостю), [EVT-73](../events/EVT-73-AD-DETAIL-VIEWED-IN-BOARD.md)
(детальная карточка объявления, включая автоматический инкремент просмотров),
[EVT-80](../events/EVT-80-AD-CONTACT-CALLED-IN-BOARD.md) (звонок по телефону
из карточки объявления или переписки) через `BoardCubit`/`AdDetailCubit`.
Мутации над объявлением (публикация/правка/удаление/избранное) и чат — не
через этого актора, см. [ACTOR-1](ACTOR-1-USER-IN-AUTH.md) (BOARD требует
реальной авторизации для этих действий, гость=авторизован работает только
для чтения).

Взаимодействует также с сущностью [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) (Ad, BOARD).

**PROFILE (третий модуль за пределами ANIMAL — весь раздел без route-guard
по авторизации, гость и авторизованный проходят один и тот же код):**
инициирует [EVT-81](../events/EVT-81-USER-PROFILE-VIEWED-IN-PROFILE.md)
(просмотр профиля), [EVT-82](../events/EVT-82-USER-PROFILE-EDITED-IN-PROFILE.md)
(редактирование имени/email/телефона/страны — для гостя ограничивается
локальным сохранением страны, без сетевого вызова),
[EVT-83](../events/EVT-83-LANGUAGE-CHANGED-IN-PROFILE.md) (смена языка
интерфейса), [EVT-84](../events/EVT-84-VACCINATION-NOTIFICATION-SETTINGS-VIEWED-IN-PROFILE.md)/[EVT-85](../events/EVT-85-VACCINATION-NOTIFICATION-SETTINGS-SAVED-IN-PROFILE.md)
(уведомления о вакцинации), [EVT-86](../events/EVT-86-KIND-VISIBILITY-VIEWED-IN-PROFILE.md)/[EVT-87](../events/EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md)
(видимость видов животных), [EVT-88](../events/EVT-88-DEVICE-SETTINGS-VIEWED-IN-PROFILE.md)/[EVT-89](../events/EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md)
(настройки сканирующих устройств) через `ProfileEditCubit`/`LanguageBloc`/
`NotificationsSettingsCubit`/`KindsVisibilitySettingsCubit`/`ScannerSettingsPage`.

Взаимодействует также с сущностями [ENT-1](../entities/ENT-1-USER-IN-AUTH.md)
(User, AUTH — переиспользован, не редактируется этим актором нигде, кроме
самого PROFILE), [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md)
(Taxonomy/Kind, HANDBOOKS — узкая грань `visible`), [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md)
(ProfileSettings), [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) (Device).

## Ограничения

Не инициирует ни один sync-шаг напрямую — отправка на сервер выполняется асинхронно, отдельным проходом (см. [ACTOR-4](ACTOR-4-SYSTEM-IN-SYSTEM.md)), не как часть локального сохранения.

## Исходный код

| Файл | Класс/метод | Роль |
|---|---|---|
| `lib/pages/animal_registration/animal_registration_bloc.dart` | `AnimalRegistrationBloc` | визард регистрации |
| `lib/pages/animal_edit/animal_edit_bloc.dart` | `AnimalEditBloc` | редактирование уже синхронизированного животного |
