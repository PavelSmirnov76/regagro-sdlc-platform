# EVT-86 — kind_visibility.viewed

| | |
|---|---|
| Инициатор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Модуль | [MOD-6](../modules/MOD-6-PROFILE.md) |
| Сущность(и) | [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (Taxonomy/Kind, HANDBOOKS) |

**Триггер.** Пользователь открывает «Видимость видов животных»
(`/profile/work_settings/kinds_visibility_settings`) —
`KindsVisibilitySettingsCubit.load()`.

**Эффект.** Читает все `Kind` (`_kindsRepository.getAll()`, без фильтра по
`visible`), сортирует по имени. Состояние `loaded` эмитится дважды подряд с
одинаковыми данными (безобидный копипаст-артефакт, не влияет на
наблюдаемое поведение).

**Исходный код.** `lib/pages/profile_settings/presentation/kinds_visibility_settings_page.dart`;
`lib/pages/profile_settings/cubit/kinds_visibility_settings_cubit/kinds_visibility_settings_cubit.dart` →
`KindsVisibilitySettingsCubit.load`; `lib/repositories/kind/kinds_repository.dart` →
`KindsRepository.getAll`.
