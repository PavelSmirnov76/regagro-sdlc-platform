# EVT-79 — board_availability.checked

| | |
|---|---|
| Инициатор | [ACTOR-3](../actors/ACTOR-3-APP-IN-AUTH.md) |
| Модуль | [MOD-5](../modules/MOD-5-BOARD.md) |
| Сущность(и) | [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) (HANDBOOKS, читается — не редактируется этим модулем) |

**Триггер.** Автоматически, без действия пользователя: смена авторизованного
пользователя (Hive `AuthRepository.getAuthBoxListenable`), смена гостевой
страны (`AppCacheService.guestCountryCodeNotifier`), либо завершение
синхронизации справочника стран (`AppCacheService.boardEnabledSyncNotifier`,
после `CountriesRepository.syncCountries()`) — `BoardChatAvailabilityCubit`,
глобально предоставлен над всем деревом виджетов.

**Эффект.** Пересчитывает `country?.boardEnabled == true` (для гостя — по
`AppCacheService.getGuestCountryCode()`, для авторизованного — по
`user.countryId`, с fallback на `user.phoneCountryIsoCode`). Результат
(`bool`) гейтит только UI: скрывает/показывает вкладки «Доска»/«Сообщения» в
нижней навигации и кнопки в профиле — **не** является route-guard'ом,
`lib/pages/routes.dart` не проверяет этот флаг ни для одного маршрута BOARD.
Источник самого флага (`GET {boardServiceApi}/countries`) при любой ошибке
молча возвращает пустой список (`CountriesRepository.getBoardEnabledCountryIds`) —
сетевой сбой на этом шаге тихо выключает BOARD для всех стран разом, без
лога и без ретрая.

**Исходный код.** `lib/blocs/board_chat_availability/board_chat_availability_cubit.dart` →
`BoardChatAvailabilityCubit`; `lib/repositories/country/countries_repository.dart` →
`CountriesRepository.getBoardEnabledCountryIds`, `syncCountries`; `lib/pages/main/main_page.dart` →
`BlocListener<BoardChatAvailabilityCubit,bool>`; `lib/widgets/bottom_app_bar/nav_bar.dart`.
