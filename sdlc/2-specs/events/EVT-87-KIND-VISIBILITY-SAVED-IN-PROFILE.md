# EVT-87 — kind_visibility.saved

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |
| Сущность(и) | [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy/Kind, HANDBOOKS) |

**Триггер.** Пользователь переключает видимость отдельных видов
(`toggleKindVisibility`) и/или «Выбрать все»/«Снять все»
(`toggleAllKindsVisibility`, все изменения — чисто in-memory), нажимает
сохранить — `KindsVisibilitySettingsCubit.save()`.

**Эффект.** Если ни один вид не остаётся видимым — сохранение осознанно
отклоняется бизнес-правилом: `emit(failure(kinds: ..., error: 'key'))` без
вызова `updateAll` (**известный дефект**: `'key'` — буквальный, не
существующий как ключ локализации текст, `AppLocalizationsExtension.tr()`
возвращает его as-is при отсутствии кейса в `switch` — пользователь видит
слово «key» вместо сообщения «Не выбран ни один вид»; правильный ключ
существует в `tr()`, но не используется вызывающим кодом). Иначе —
`_kindsRepository.updateAll(state.kinds)` (батч-обновление колонки `visible`
у всех `Kind` разом).

Тот же факт (переключение `Kind.visible`) редактируется и вторым,
независимо написанным путём — шагом `FarmCreateStep.kindsVisibility` визарда
создания первой фермы (`FarmCreateCubit`, модуль `FARM`, уже
специфицирован) — с почти идентичной, но раздельно реализованной логикой
toggle/save. Не переспецифицируется здесь как отдельное событие — тот код
принадлежит уже закрытому модулю `FARM`.

**Исходный код.** `lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_cubit.dart` →
`KindsVisibilitySettingsCubit.save`, `toggleKindVisibility`,
`toggleAllKindsVisibility`; `lib/repositories/kind/kinds_repository.dart` →
`KindsRepository.updateAll`.
