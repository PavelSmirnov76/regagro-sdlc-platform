# EVT-83 — language.changed

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |
| Сущность(и) | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) (User, AUTH — поле `locale`) |

**Триггер.** Пользователь выбирает новый язык (`ProfileEditCubit.selectLanguage`,
пишет в черновик `newUserData.locale`) и нажимает «Сохранить» вместе с
остальными полями формы — [EVT-82](EVT-82-USER-PROFILE-EDITED-IN-PROFILE.md).
`saveChanges()` детектирует расхождение `newUserData.locale` с
`currentUserData.locale` (уже после того, как для авторизованного
`AuthRepository.updateUser` успешно отправлен) и вместо обычного успеха
эмитит `isLanguageChanged: true`.

**Эффект.** `ProfileSettingsView`'s `BlocConsumer<ProfileEditCubit>` реагирует
на этот флаг: диспатчит `LanguageBloc.on<LanguageEventChange>(newLocale)` →
`LanguageService.setLocale()` (персист в SharedPreferences, ключ `'language'`) →
`emit(LanguageStateChanged)`. `MaterialApp.router` (обёрнут в
`BlocBuilder<LanguageBloc>`, `lib/main.dart`) пересобирает `locale`
приложения; множество отдельных экранов (`board_page.dart`,
`favourite_ads_page.dart`, `in_work_page.dart`, `main_page.dart`,
`profile_page.dart` и др.) держат собственный `BlocListener<LanguageBloc>`,
который на `LanguageStateChanged` вызывает `setState(() {})` — локальный
форс-ребилд отдельно от глобального. Ещё один слушатель в
`ProfileSettingsView` реагирует на `LanguageStateChanged`: перезагружает
`ProfileEditCubit.load()` и диспатчит **полный ресинк**
(`DataUpdateBloc.add(DataUpdateStartAll(resetNavigationOnSuccess: true))`),
без `isUpdateData: true` — см. [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md),
инвариант про потерю несинхронизированных локальных настроек при таком
ресинке.

**Исходный код.** `lib/pages/profile/cubit/profile_edit_cubit.dart` →
`selectLanguage`, `saveChanges`, `consumeLanguageChangeFlag`;
`lib/pages/profile/presentation/widgets/profile_settings/profile_settings_view.dart` →
оба `BlocListener` (`ProfileEditCubit`/`LanguageBloc`); `lib/pages/language/language_bloc.dart` →
`LanguageBloc.on<LanguageEventChange>`; `lib/l10n/language_service.dart` →
`LanguageService.setLocale`, `init`.
