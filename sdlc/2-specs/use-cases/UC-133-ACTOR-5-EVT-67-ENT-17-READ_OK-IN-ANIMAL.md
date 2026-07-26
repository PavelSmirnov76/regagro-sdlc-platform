# UC-133 — Пользователь экспортирует итоговый отчёт инвентаризации в Excel/PDF из `_ExportBottomSheet` — статус животного в файле жёстко закодирован по-русски, минуя l10n

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-67](../events/EVT-67-ANIMAL-INVENTORY-REPORT-EXPORTED-IN-ANIMAL.md) |
| Сущность | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| Результат | `READ_OK` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

С уже открытого итогового отчёта инвентаризации
([EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md),
`InventoryReportDetailsView`/`InventoryReportDetailsCubit`) пользователь жмёт
`share` в `AppBar`, выбирает формат в модальном `_ExportBottomSheet` и получает
файл (Excel через пакет `excel`, либо PDF через `pdf`/`printing`), переданный в
системный диалог «поделиться» (`SharePlus`). Экспорт — чистое чтение уже
загруженного `InventoryReportDetailsState`: он не делает ни одного нового
запроса к `UnsentReportAnimalsRepository`/`ReportAnimalsRepository` и не
пишет ни одной строки `InventoryScanReport` — весь набор данных (`myAnimalsByKind`,
`otherAnimals`, `farm`, `place`, `date`) к этому моменту уже посчитан
`InventoryReportDetailsCubit.load()` (см. EVT-66). Экспортный файл — не
зеркало экрана: он перестраивает те же данные в другую структуру (см.
«Основной поток», «Бизнес-правила»), с одним самостоятельным дефектом —
`_getStatusText` возвращает статус животного жёстко закодированной русской
строкой, минуя `AppLocalizations`, единственное такое место в этом файле.

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково: ни
`InventoryReportDetailsView`, ни `_ExportBottomSheet`, ни
`_generateAndShareExcel`/`_generateAndSharePdf` не обращаются к
`AuthRepository`/не проверяют статус авторизации нигде (весь файл
`lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart`
прочитан целиком — ни одного упоминания `isAuthorized`/`AuthRepository`).
Экспорт не делает ни одного сетевого вызова к бэкенду приложения; PDF-ветка,
впрочем, обращается к стороннему сервису шрифтов (см. «Открытые вопросы»).

## CURRENT

### Основной поток

1. На экране `InventoryReportDetailsView` (`AppBar` с заголовком
   `AppLocalizations.of(context)!.inventory` и подзаголовком —
   отформатированной `args.date`) кнопка `IconButton(icon: Icons.share)`
   в `actions` рендерится только при `!state.isLoading &&
   state.myAnimalsByKind.isNotEmpty`. `isLoading` в этом кубите никогда не
   становится `true` — все три `emit` в `InventoryReportDetailsCubit.load()`
   создают `InventoryReportDetailsState(...)` без аргумента `isLoading`, а
   поле объявлено `@Default(false)` в `InventoryReportDetailsState`, — так
   что фактическое условие видимости кнопки сводится к одному
   `myAnimalsByKind.isNotEmpty` (см. `UC-132` — эта конкретизация относится к
   экрану EVT-66 в целом, здесь фиксируется только как предпосылка
   доступности кнопки `share`).
2. Тап по кнопке → `_showExportBottomSheet(context, state)` →
   `showModalBottomSheet(context: context, isScrollControlled: true,
   useRootNavigator: true, builder: (bottomSheetContext) =>
   _ExportBottomSheet(state: state))`. `state` передаётся простым полем
   виджета — `_ExportBottomSheet` не подписан на `InventoryReportDetailsCubit`
   через `BlocProvider`/`context.watch`, это статический снимок состояния на
   момент нажатия кнопки, а не живой поток.
3. `_ExportBottomSheet.build` рисует контейнер с белым фоном и скруглением
   верхних углов (`BorderRadius.vertical(top: Radius.circular(20))`),
   заголовок `AppLocalizations.of(context)!.export_data` + `IconButton(Icons.close)`
   (`Navigator.of(context).pop()`), затем два варианта:
   - `l10n.export_to_excel` (иконка `Icons.table_chart`, зелёная);
   - `l10n.export_to_pdf` (иконка `Icons.picture_as_pdf`, красная).

   Оба — `InkWell` в контейнере с белым фоном и серой рамкой в 1px.
4. **Ветка Excel.** `onTap` (синхронный, не `async`) сначала вызывает
   `Navigator.of(context).pop()` (закрывает bottom sheet), затем, **не
   дожидаясь (`await`) результата**, вызывает `_generateAndShareExcel(context,
   state)` — это обычный вызов асинхронной функции без `await` в
   синхронном обработчике, весь дальнейший код выполняется как
   fire-and-forget по отношению к самому `onTap`.
5. Внутри `_generateAndShareExcel` (целиком в одном `try`):
   - `l10n = AppLocalizations.of(context)!` — `context` здесь тот же, что был
     передан в `_ExportBottomSheet.build`, т.е. контекст уже закрытого на шаге 4
     bottom sheet (см. «Открытые вопросы»);
   - `ex.Excel.createExcel()`, дефолтный лист `Sheet1` переименовывается в
     `l10n.inventory_report`;
   - заводятся три стиля ячеек: `boldLabelStyle` (только `bold`),
     `headerCellStyle` (`bold` + тонкая рамка со всех сторон),
     `dataCellStyle` (только рамка);
   - три строки «метка/значение» с общей тонкой рамкой только у ячейки
     метки (не у значения): `report_date` / `DateFormat('yyyy-MM-dd
     HH:mm').format(state.date)`, `farm` / `state.farm?.name ?? '-'`, `place`
     / `state.place?.name ?? '-'`;
   - пустая строка;
   - заголовок `'${l10n.extra_animals_list} (${state.otherAnimals.length})'`
     (жирный, без рамки), затем строка-заголовок столбца `l10n.number`
     (жирная, с рамкой), затем по одной строке (с рамкой) на каждый элемент
     `state.otherAnimals` — те же необработанные строки `transponderId`, что
     на экране показаны в секции «чужие метки» как номера без известного
     животного (`unknownNumbers`, см.
     [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md));
   - две пустые строки;
   - заголовок `l10n.scanned_animals_list` (жирный, без рамки), затем одна
     строка-заголовок из 8 колонок (`serial_number`, `type`, `number`,
     `breed`, `date_of_birth`, `farm`, `place`, `status`, все с рамкой и
     жирным начертанием), ширины колонок выставлены явно
     (8/20/20/20/15/20/20/20);
   - затем — **не переиспользуя** `_computeSections`/секции, уже
     показанные на экране — цикл `for (kindEntry in
     state.myAnimalsByKind.entries) for (animal in kindEntry.value)`
     строит **одну плоскую таблицу** по всем животным из
     `state.myAnimalsByKind` разом (без деления по возрастной группе/виду,
     без отдельного выделения «отсутствует»/«с другого места», как на
     экране): порядковый номер, `animal.kindNameText`,
     `animal.firstMainNumber`, `animal.breed?.name ?? '-'`, дата рождения
     (`yyyy-MM-dd` либо `'-'`), `animal.farm?.name ?? '-'`,
     `animal.place?.name ?? '-'`, и `_getStatusText(animal,
     scannedAnimalNumbers, state.farm, state.place)` — единственная
     колонка, не идущая через `l10n` (см. «Бизнес-правила»);
   - `excel.encode()` → временный файл (`getTemporaryDirectory()`, имя
     `'${l10n.inventory_report}_yyyy-MM-dd_HH-mm.xlsx'`) →
     `SharePlus.instance.share(ShareParams(files: [XFile(filePath)], text:
     '${l10n.inventory_report} $fileName'))` — на этом моменте `RESULT =
     READ_OK` этого файла считается достигнутым: файл собран и передан в
     системный диалог «поделиться» (не факт, что пользователь довёл шаринг
     до конца — это уже вне контроля приложения).
6. **Ветка PDF** (`_generateAndSharePdf`) — симметрична по структуре:
   - `PdfGoogleFonts.robotoRegular()`/`robotoBold()` — см. «Открытые
     вопросы» о сетевой зависимости этого вызова;
   - один `pw.MultiPage` (A4 landscape): заголовок `l10n.inventory_report`,
     три параграфа (`report_date`/`farm`/`place`), затем **только если**
     `state.otherAnymals.isNotEmpty` — однoколоночная таблица (`l10n.number`)
     по `state.otherAnimals`, затем **только если** собранный `rows`
     непуст — та же плоская 8-колоночная таблица, что и в Excel-ветке,
     заново независимо пересобранная тем же циклом по
     `state.myAnimalsByKind` с тем же вызовом `_getStatusText`;
   - файл сохраняется (`'${reportTitle}_yyyy-MM-dd_HH-mm.pdf'`) и
     передаётся в тот же `SharePlus.instance.share`.

### Альтернативные потоки

- **Кнопка `share` скрыта, если отсканированы только неизвестные номера.**
  Условие видимости — `state.myAnimalsByKind.isNotEmpty`, оно не учитывает
  `state.otherAnimals`. Если в сессии/дне встретились только метки, не
  сопоставленные ни с одним локально известным животным этого места
  (`otherAnimals` непуст, `myAnimalsByKind` пуст — вполне достижимо: место
  без единого зарегистрированного животного, все сканы — чужие/неизвестные
  метки), экспорт целиком недоступен — ни Excel, ни PDF нельзя выгрузить,
  хотя данные (список неизвестных номеров) есть.
- **`state.otherAnimals` пуст.** Excel всё равно печатает заголовок
  `'... (0)'` и строку-заголовок `l10n.number` без единой строки данных;
  PDF, наоборот, полностью пропускает под-таблицу (`if
  (state.otherAnimals.isNotEmpty)`) — заголовочный текст остаётся, самой
  таблицы нет. Два формата ведут себя по-разному для одного и того же
  пустого случая.
- **`rows` (плоская таблица животных) пуст в PDF-ветке.** Технически
  реализовано (`if (rows.isNotEmpty)`), но недостижимо на практике, пока
  кнопка `share` скрыта именно по условию `myAnimalsByKind.isNotEmpty`: раз
  кнопка видна, хотя бы один список внутри `myAnimalsByKind` непуст
  (`putIfAbsent(...).add(e)` никогда не создаёт пустых списков), то есть
  `rows` после разворачивания всегда содержит хотя бы одну строку.
- **`fileBytes == null` после `excel.encode()`** (Excel-ветка) —
  `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:
  Text(l10n.error_saving_file)))`, если `context.mounted`. Отдельный,
  специфичный для Excel случай, не имеющий аналога в PDF-ветке (`pdf.save()`
  не возвращает `null`). Не `READ_OK`, для этого файла не покрывается —
  отдельного use-case для этой ветки на момент написания не заведено.
- **Исключение внутри `try` любой из двух веток** (сбой построения
  файла/записи на диск/вызова `SharePlus`) — единый `catch (e)`:
  `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:
  Text('${l10n.error_creating_file}: $e')))`, тоже под `if
  (context.mounted)`. `RESULT` этой ветки — не `READ_OK`; отдельный
  `READ_ERROR` use-case для [EVT-67](../events/EVT-67-ANIMAL-INVENTORY-REPORT-EXPORTED-IN-ANIMAL.md)
  на момент написания не заведён (см. «Открытые вопросы» про то, насколько
  вообще наблюдаема эта ветка пользователем).
- **Пользователь закрывает `_ExportBottomSheet` крестиком, не выбрав
  формат.** `Navigator.of(context).pop()` без параметров — ни одна из
  генерирующих функций не вызывается, экран EVT-66 остаётся как был. Не
  этот файл.

### Связанные сущности

- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport) — сущность сегмента `ENT` в id: экспорт только
  читает то, что `InventoryReportDetailsCubit.load()` уже загрузил в
  `state.allAnimals`/`state.otherAnimals` (см. EVT-66); сам этот файл не
  делает ни одного нового обращения к
  `UnsentReportAnimalsRepository`/`ReportAnimalsRepository` и не пишет ни
  одной строки `UnsentReportAnimals`/`ReportAnimals`.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — только чтение:
  весь набор `state.myAnimalsByKind` (уже отфильтрованный `load()` по
  ферме/месту либо по совпадению идентификации, см. EVT-66) разворачивается
  в одну плоскую таблицу; ни одно поле `Animal` этим сценарием не
  изменяется.
- [ENT-12](../entities/ENT-12-ANIMAL-IDENTIFICATION-IN-ANIMAL.md)
  (AnimalIdentification) — только косвенно: `animal.animalIdentificationNumbers`
  (готовое поле `AnimalWithDetails`, вычисленное при `load()`) используется
  в `_getStatusText` для определения `isScanned`; экспортный код не
  обращается к `AnimalIdentificationsRepository` напрямую.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm, FARM) — только чтение:
  `state.farm?.name` в шапке файла, `animal.farm?.name` в каждой строке,
  `farm?.remoteId` в сравнении внутри `_getStatusText`.
- [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) (Place, FARM) — тот же
  паттерн, что и Farm, для `place`.

### Бизнес-правила

- **Центральный дефект: `_getStatusText` возвращает жёстко закодированные
  русские строки, минуя `AppLocalizations`.** Сигнатура — `String
  _getStatusText(dynamic animal, Set<String> scannedAnimalNumbers, Farm?
  farm, Place? place)`; три достижимых исхода — литералы `'Учтено'`,
  `'Потеряно'`, `'С другого объекта'` (плюс необозначенный четвёртый, см.
  ниже) — не читаются ни из `l10n`, ни из какого-либо другого источника
  локализации. Это единственное место во всём файле, где так: заголовок
  `AppBar`, все подписи `_ExportBottomSheet`, все текстовые метки внутри
  обеих генерирующих функций (`report_date`, `farm`, `place`,
  `extra_animals_list`, `number`, `scanned_animals_list`,
  `serial_number`/`type`/`breed`/`date_of_birth`/`status` и т.д.) — все
  идут через `AppLocalizations.of(context)!.*`, и все ключи присутствуют и в
  `lib/l10n/app_en.arb`, и в `lib/l10n/app_ru.arb` (проверено:
  `export_data`, `export_to_excel`, `export_to_pdf`, `inventory_report`,
  `report_date`, `farm`, `place`, `extra_animals_list`, `number`,
  `scanned_animals_list`, `serial_number`, `type`, `breed`,
  `date_of_birth`, `status`, `error_saving_file`, `error_creating_file` —
  все найдены в обоих `.arb`). Следствие: пользователь с любым
  неанглийским-нерусским (и даже английским) языком приложения получит
  полностью локализованный экран и полностью локализованный экспортный
  файл — кроме одной колонки `status`/«статус», которая всегда на русском,
  независимо от `AppLocalizations.of(context)!.localeName`.
- **Четвёртая, необозначенная ветка `_getStatusText` тоже возвращает
  `'Учтено'`.** Функция — это три явных `if`, каждый со своим `return`, без
  `else if`; после всех трёх — безусловный `return 'Учтено';`. Комбинация
  «не отсканировано» + «другая ферма/место» ни в одном из трёх `if` не
  описана явно и падает в этот безусловный `return`. В штатных условиях
  (когда `InventoryReportDetailsCubit.load()` успешно резолвит и `farm`, и
  `place`) эта комбинация в `state.myAnimalsByKind` не встречается — сам
  `load()` уже убирает из выборки животных, у которых одновременно (другая
  ферма ИЛИ другое место) И нет совпадения идентификации со сканом
  (`animals.removeWhere(...)`, см. EVT-66) — так что на практике этот
  безусловный `return` недостижим полезным образом, это чистое покрытие
  «по умолчанию». Но если `farm` не резолвится (`_farmsRepository.getById(null)`
  возвращает `null` без исключения, если ни `_farmId` из аргументов
  страницы, ни `reports.first.farmId` не заданы) — весь блок
  `if (farm != null) { animals.removeWhere(...); }` в `load()` целиком
  пропускается, и `myAnimalsByKind` остаётся **неотфильтрованным**: в него
  попадают вообще все локально известные, неудалённые животные из
  `getAllAnimalsWithDetailsByFilters()` без аргументов, каких угодно ферм и
  мест. В этом (узком, но не невозможном) сценарии описанная выше
  четвёртая ветка становится реально достижимой и массово неверно
  подписывает статусом `'Учтено'` животных, которые к этой инвентаризации
  не имеют отношения вовсе.
- Excel и PDF полностью независимо пересобирают одну и ту же плоскую
  таблицу из `state.myAnimalsByKind` (два отдельных цикла с идентичной
  логикой и отдельным вызовом `_getStatusText` на каждую строку) — не
  переиспользуют друг друга и не переиспользуют `_computeSections`,
  которым построены секции самого экрана.
- **Структура экспортного файла отличается от структуры экрана.**
  На экране (`InventoryAccordionListWidget`, см. EVT-66) — 4 отдельные
  секции: «учтено» по возрастной группе, «отсутствует», «чужие метки»
  (объединяет известных животных с другого места/фермы **и** неизвестные
  номера в одной секции), и внутри неё неизвестные номера показываются как
  строки с меткой «подразделение не указано». В экспортном файле — только
  2 блока: список «прочие животные» (`extra_animals_list` = ровно те же
  неизвестные номера, что на экране) отдельно от единой плоской таблицы, в
  которую попадают учтённые, отсутствующие и известные-с-другого-места
  животные вместе, различаемые только колонкой `status` — известные
  животные с другого места **не** выделены в собственный список, как на
  экране, а размазаны по общей таблице.
- Экспорт не изменяет ни одну строку `InventoryScanReport`/`Animal` —
  чисто читающее, файлообразующее действие (согласуется с текстом
  [EVT-67](../events/EVT-67-ANIMAL-INVENTORY-REPORT-EXPORTED-IN-ANIMAL.md)).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — весь основной поток (обе ветки, Excel и
PDF) воспроизводится статическим чтением
`lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart`
целиком. Найденные дефекты (жёстко закодированный русский статус,
недостижимая-кроме-узкого-случая четвёртая ветка `_getStatusText`, сетевая
зависимость PDF-шрифтов) в рамках этого документирующего прохода не
исправляются — это фиксация уже существующего кода, тем же принципом, что и
в [UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md).

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `InventoryReportDetailsView.build` (`actions`) | CURRENT | условие видимости кнопки `share` — `!state.isLoading && state.myAnimalsByKind.isNotEmpty` |
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `InventoryReportDetailsView._showExportBottomSheet` | CURRENT | `showModalBottomSheet(isScrollControlled: true, useRootNavigator: true, ...)` |
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `_ExportBottomSheet` (`build`) | CURRENT | модальный выбор формата; хардкодит `Colors.white`/`Colors.grey`/`Colors.green`/`Colors.red` и инлайн `TextStyle` вместо `AppColors`/`app_typography.dart` (см. «Открытые вопросы») |
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `_ExportBottomSheet._generateAndShareExcel` | CURRENT | сборка книги `excel`, запись во временный файл, `SharePlus.instance.share` |
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `_ExportBottomSheet._generateAndSharePdf` | CURRENT | сборка `pw.MultiPage`, `PdfGoogleFonts`, запись во временный файл, `SharePlus.instance.share` |
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `_ExportBottomSheet._getStatusText` | CURRENT | предмет центрального дефекта — жёстко закодированные русские строки статуса, не через `l10n`; безусловный `return 'Учтено'` в конце как покрытие незаявленной четвёртой комбинации |
| `lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart` | `InventoryReportDetailsCubit.load` | CURRENT | источник `state.myAnimalsByKind`/`otherAnimals`/`farm`/`place`, который экспорт только читает; фильтрует `animals` по ферме/месту, только если `farm != null` |
| `lib/pages/animals_inventory/cubit/inventory_report_details_state.dart` | `InventoryReportDetailsState.isLoading` | CURRENT | `@Default(false)`, ни разу не переопределяется явным `true` внутри `load()` |
| `lib/pages/scanning/widgets/inventory_accordion_list_widget.dart` | `InventoryAccordionListWidget`, `InventoryAgeGroupSection`, `InventoryAbsentEntry`, `InventoryForeignKnownEntry` | CURRENT | 4-секционная структура самого экрана — контраст с 2-блочной структурой экспортного файла; сам этот виджет полностью локализован (`l10n.inventory_absent_section`/`inventory_foreign_tags`/`inventory_animals_label`) |
| `lib/repositories/farm_repository/farm_repository.dart` | `FarmRepository.getById` | CURRENT | `if (farmId == null) return null;` — без исключения; от результата зависит, выполнится ли фильтрация `animals` в `load()` (см. «Бизнес-правила», четвёртая ветка `_getStatusText`) |
| `lib/widgets/app_snackbar.dart` | `showAppSnackBarError`/`showAppSnackBarInfo` | CURRENT (не используется здесь) | проектный хелпер снекбаров — обе ошибочные ветки экспорта используют вместо него ad-hoc `ScaffoldMessenger.of(context).showSnackBar` |
| `pubspec.lock` | `excel: 4.0.6` | внешний пакет | генерация `.xlsx` |
| `pubspec.lock` | `pdf: 3.11.3` | внешний пакет | `pw.Document`/`pw.MultiPage`; base-14 `Font.helvetica()` как fallback без кириллицы |
| `pubspec.lock` | `printing: 5.14.2` | внешний пакет | `PdfGoogleFonts.robotoRegular/robotoBold` — сетевая загрузка с `fonts.gstatic.com` |
| `~/.pub-cache/.../printing-5.14.2/lib/src/fonts/font.dart` | `DownloadableFont.getFont` | внешний пакет | `catch (e) { ... return Font.helvetica(); }` — сетевой сбой гасится молча, без исключения наружу |
| `~/.pub-cache/.../printing-5.14.2/lib/src/cache.dart` | `PdfBaseCache.defaultCache = PdfMemoryCache()` | внешний пакет | кэш шрифтов только в памяти процесса, TTL 20 минут (`Timer(const Duration(minutes: 20), clear)`), не персистится на диск |
| `pubspec.lock` | `share_plus: 12.0.1` | внешний пакет | `SharePlus.instance.share(ShareParams(...))` — передача файла в системный диалог |

## Критерии приёмки

- Кнопка `share` в `AppBar` экрана `InventoryReportDetailsView` видна тогда
  и только тогда, когда `state.myAnimalsByKind.isNotEmpty` (условие
  `!state.isLoading` фактически всегда истинно, поскольку `isLoading` не
  становится `true` ни в одном `emit` `InventoryReportDetailsCubit.load()`).
- Тап по кнопке открывает `_ExportBottomSheet` с двумя вариантами
  (`export_to_excel`/`export_to_pdf`), оба локализованы через
  `AppLocalizations`.
- Выбор «Экспорт в Excel» закрывает bottom sheet и порождает `.xlsx`-файл с
  тремя строками метаданных (дата/ферма/место), списком «прочие животные»
  (`state.otherAnimals`, каждая строка — сырой `transponderId`) и единой
  8-колоночной таблицей по всем животным `state.myAnimalsByKind`, где
  последняя колонка — результат `_getStatusText`; файл передаётся в
  `SharePlus.instance.share`.
- Выбор «Экспорт в PDF» порождает симметричный `.pdf` (A4 landscape) с той
  же структурой данных, независимо пересобранной тем же алгоритмом; при
  пустых `otherAnimals`/`rows` соответствующая таблица не рендерится вовсе
  (в отличие от Excel, где заголовок таблицы печатается всегда).
- `_getStatusText` возвращает один из литералов `'Учтено'`/`'Потеряно'`/`'С
  другого объекта'` (либо `'Учтено'` по умолчанию для необозначенной
  четвёртой комбинации) — ни один из них не проходит через
  `AppLocalizations`, независимо от текущего языка приложения.
- Ни одна из двух генерирующих функций не изменяет ни одну запись
  `InventoryScanReport`/`Animal`/`Farm`/`Place` — обе только читают уже
  загруженный `state`.

## Связанные тесты

- `test/pages/inventory_report_details_cubit_test.dart`, группы `'UC-131 —
  InventoryReportDetailsCubit.load (по дате)'` и `'UC-131 —
  InventoryReportDetailsCubit.load (по sessionUuid)'` (старая нумерация, не
  трогать сейчас) — покрывают **только** `InventoryReportDetailsCubit.load()`,
  т.е. предпосылку данных для этого файла (EVT-66), но не саму сцену
  экспорта: ни один из этих тестов не строит `InventoryReportDetailsView`,
  не открывает `_ExportBottomSheet` и не вызывает
  `_generateAndShareExcel`/`_generateAndSharePdf`/`_getStatusText`.
- **TBD — теста нет** на `_ExportBottomSheet`, `_generateAndShareExcel`,
  `_generateAndSharePdf` и `_getStatusText` — `grep -rln
  "InventoryReportDetailsView\|_ExportBottomSheet\|generateAndShareExcel\|generateAndSharePdf"
  test/` не находит ни одного файла.
- **TBD — теста нет** на `InventoryAccordionListWidget` (виджет самого
  экрана EVT-66, с которым сравнивается структура экспортного файла в этом
  документе) — тот же `grep` не находит ни одного файла и для него.

## Открытые вопросы и ограничения

- **Не залокализованный статус — центральный дефект этого файла** (см.
  «Бизнес-правила»). Не зафиксировано, осознанное ли это упущение (например,
  функция писалась до появления мультиязычности в этой под-области) или
  просто недосмотр при копировании логики из `_computeSections` в отдельную
  функцию для экспорта.
- **`_ExportBottomSheet` хардкодит цвета и текстовые стили** (`Colors.white`/
  `Colors.grey`/`Colors.green`/`Colors.red`, инлайн `TextStyle(fontSize:
  20, fontWeight: FontWeight.w600)` и т.п.) вместо `AppColors`/
  `app_typography.dart`, что прямо противоречит
  `.claude/rules/ui-architecture.md` — в отличие от
  `InventoryAccordionListWidget` в той же фиче, который корректно использует
  `AppColors`/`context.typography`.
- **Ad-hoc `ScaffoldMessenger.showSnackBar` вместо `lib/widgets/app_snackbar.dart`**
  в обеих ошибочных ветках (`error_saving_file`, `error_creating_file: $e`)
  — тоже расходится с проектной конвенцией; вторая ветка к тому же
  показывает пользователю сырой текст исключения (`$e`) без какой-либо
  локализации/санитизации.
- **Контекст bottom sheet попадает в `_generateAndShareExcel`/
  `_generateAndSharePdf` уже после `Navigator.pop()`.** `onTap` вызывает
  `pop()` синхронно, затем передаёт тот же `context` (замыканием) в
  асинхронную генерирующую функцию, не дожидаясь её завершения. Первый
  вызов `AppLocalizations.of(context)!` (до первого `await`) в момент
  вызова, скорее всего, ещё застаёт контекст смонтированным — сама
  выгрузка виджета bottom sheet происходит не мгновенно по вызову `pop()`,
  а по завершении обратной анимации. Однако к моменту, когда генерация
  дойдёт до `if (context.mounted)` перед показом `SnackBar` об ошибке
  (после записи файла на диск, при PDF — после потенциального сетевого
  запроса шрифта), контекст bottom sheet с высокой вероятностью уже
  размонтирован — то есть сама проверка `context.mounted` работает
  корректно (не бросает исключение на невалидном контексте), но её
  практический эффект — сообщение об ошибке почти никогда не показывается
  пользователю. Не воспроизведено эмпирически (не хватает интеграционного
  теста с управляемым таймингом), только выведено чтением кода.
- **PDF-ветка зависит от сети для кириллического шрифта.**
  `PdfGoogleFonts.robotoRegular()`/`robotoBold()` (пакет `printing 5.14.2`)
  при отсутствии закэшированных байтов делают `http.get` на
  `fonts.gstatic.com`; кэш — `PdfBaseCache.defaultCache = PdfMemoryCache()`,
  только в памяти процесса, с таймером самоочистки на 20 минут, не
  переживает перезапуск приложения. При сетевой ошибке `DownloadableFont.getFont`
  перехватывает исключение сама и возвращает `Font.helvetica()` — без
  исключения наружу, без какого-либо лога вне debug-assert. `pdf 3.11.3`
  реализует `Font.helvetica()` как один из стандартных 14 PDF-шрифтов
  (`Type1`, таблицы ширин в `type1_fonts.dart`) — по спецификации PDF такие
  шрифты не содержат кириллических глифов. Практическое следствие для этого
  offline-first приложения: если у устройства нет сети (и Roboto ранее не
  успел закэшироваться в текущем запуске процесса) в момент нажатия
  «Экспорт в PDF», файл всё равно успешно строится и передаётся в
  `SharePlus` без какой-либо ошибки пользователю, но кириллический текст
  внутри (включая как раз статус `_getStatusText`, если приложение на
  русском) рискует не отрендериться читаемо. Это единственное место во
  всём `lib/` — `grep -rn "PdfGoogleFonts" lib/` — не находит других
  использований. Не воспроизведено рендерингом реального PDF в оффлайне в
  рамках этого прохода, вывод — из чтения точных версий пакетов, закреплённых
  в `pubspec.lock`, и их исходного кода.
- **Кнопка `share` скрыта, если единственные данные сессии — неизвестные
  номера** (см. «Альтернативные потоки»). Осознанное ли это решение
  («нечего показывать, кроме списка чужих меток — не стоит предлагать
  экспорт») или недосмотр (`otherAnimals` не участвует в условии видимости
  вовсе) — не зафиксировано в коде.
- **Полное отсутствие тестового покрытия** для всей сцены экспорта и для
  `InventoryAccordionListWidget` (см. «Связанные тесты») — включая
  отсутствие теста на саму находку «четвёртая ветка `_getStatusText`
  недостижима в штатном случае, но реальна при нерезолвленной ферме».
