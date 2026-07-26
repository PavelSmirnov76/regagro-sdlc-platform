# UC-134 — Экспорт итогового отчёта инвентаризации в Excel/PDF технически отказывает: `_generateAndShareExcel`/`_generateAndSharePdf` ловят исключение (и, отдельно для Excel, несостоявшееся кодирование без исключения) и показывают пользователю читаемое сообщение об ошибке

| | |
|---|---|
| Актор | [ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) |
| Событие | [EVT-67](../events/EVT-67-ANIMAL-INVENTORY-REPORT-EXPORTED-IN-ANIMAL.md) |
| Сущность | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| Результат | `READ_ERROR` |
| Модуль | [MOD-4](../modules/MOD-4-ANIMAL.md) |

## Назначение

Документирует `ERROR`-исход [EVT-67](../events/EVT-67-ANIMAL-INVENTORY-REPORT-EXPORTED-IN-ANIMAL.md)
(`animal_inventory.report_exported`): пользователь на экране итогового отчёта
инвентаризации (`InventoryReportDetailsView`,
`lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart`)
выбирает «Экспорт в Excel» либо «Экспорт в PDF» из модального
`_ExportBottomSheet`, а формирование/шаринг файла заканчивается технической
неудачей. В отличие от подавляющего большинства read/export-сценариев
под-области `INV` (например [UC-132](UC-132-ACTOR-5-EVT-66-ENT-17-READ_ERROR-IN-ANIMAL.md),
где `InventoryReportDetailsCubit.load` вообще не имеет `try/catch` и состояние
физически не может нести ошибку), обе экспортные функции —
`_generateAndShareExcel` и `_generateAndSharePdf` — **целиком обёрнуты в
`try/catch`** и при любом исключении показывают пользователю читаемый,
локализованный `SnackBar`, а не оставляют его перед бесконечным ожиданием.
Это тот же положительный контраст, что уже задокументирован для
[UC-130](UC-130-ACTOR-5-EVT-65-ENT-17-READ_ERROR-IN-ANIMAL.md)
(`UnsentInventoriesCubit.load`) — эта спека фиксирует второй такой пример в
той же под-области, не находку о дефекте.

Перепроверено чтением файла целиком: у Excel-пути на самом деле **две**
независимо проверяемые технические причины отказа, ведущие к **разным**
сообщениям пользователю, а не одна:

- (а) любое исключение, брошенное где угодно внутри `try` (построение книги,
  `getTemporaryDirectory()`, запись файла, вызов системного диалога
  «поделиться») — перехватывается общим `catch (e)` в конце метода, и
  показывает `'${l10n.error_creating_file}: $e'` (с сырым текстом
  исключения);
- (б) `excel.encode()` возвращает `null` **без исключения** — узкий, отдельно
  проверенный `if (fileBytes != null) {...} else {...}` внутри самого `try`,
  ветка `else` показывает `l10n.error_saving_file` (без текста исключения,
  потому что исключения не было).

PDF-путь устроен проще — у него нет эквивалента ветки (б): `pdf.save()`
(единственный источник байт для PDF) не возвращает nullable-тип и не
проверяется на `null`, поэтому единственная техническая причина отказа —
исключение, перехватываемое тем же паттерном, что и ветка (а) Excel-пути
(в тексте ниже — ветка (в)). Это несимметричное распределение веток между
двумя форматами экспорта — не общий сценарий «экспорт не удался», а три
отдельно проверенных пути, как и в эталоне
[UC-90](UC-90-ACTOR-4-EVT-45-ENT-15-CREATE_ERROR-IN-ANIMAL.md).

## Пользователь

[ACTOR-5](../actors/ACTOR-5-USER-IN-ANIMAL.md) — текущий пользователь
приложения, гость и авторизованный одинаково. Проверено чтением
`InventoryReportDetailsView`/`_ExportBottomSheet` целиком: ни один из этих
классов не обращается к `AuthRepository`/`isAuthorized` — доступ к
итоговому отчёту и его экспорту не зависит от статуса авторизации, как и у
остальных read-экранов этой под-области.

## CURRENT

### Основной поток

1. Пользователь уже находится на экране итогового отчёта
   (`InventoryReportDetailsView`, маршрут `Routes.inventoryReport`) — попадает
   туда одним из двух путей [EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md):
   автоматически сразу после завершения сессии сканирования, либо вручную из
   календаря отчётов. `InventoryReportDetailsCubit.load()` к этому моменту уже
   успешно загрузил данные — `state.isLoading == false`.
2. `CustomAppBar.actions` показывает иконку `Icons.share` **только** при
   `!state.isLoading && state.myAnimalsByKind.isNotEmpty`
   (`InventoryReportDetailsView.build`) — если у места содержания нет ни
   одного известного животного (`myAnimalsByKind` пуст), иконки нет вовсе, и
   весь сценарий этого файла для такого места структурно недостижим.
3. Тап по иконке → `_showExportBottomSheet(context, state)` →
   `showModalBottomSheet(context: context, isScrollControlled: true,
   useRootNavigator: true, builder: (bottomSheetContext) =>
   _ExportBottomSheet(state: state))`. Параметр `bottomSheetContext` самого
   `builder` нигде не используется — `_ExportBottomSheet` строится без него;
   у `_ExportBottomSheet.build` собственный `BuildContext`, принадлежащий
   поддереву модального bottom sheet, а не родительскому экрану.
4. `_ExportBottomSheet` рендерит заголовок (`AppLocalizations.export_data`),
   кнопку закрытия и два пункта: «Экспортировать в Excel»
   (`AppLocalizations.export_to_excel`) и «Экспортировать в PDF»
   (`AppLocalizations.export_to_pdf`).
5. Пользователь тапает по одному из двух пунктов. Оба `onTap`-обработчика
   устроены одинаково: **сначала** `Navigator.of(context).pop()` (запрос на
   закрытие bottom sheet), **сразу же, без `await`**, вызывают
   `_generateAndShareExcel(context, state)` либо
   `_generateAndSharePdf(context, state)` — передавая тот же `context`,
   что и у самого `_ExportBottomSheet`, т.е. **контекст уже закрываемого
   bottom sheet**, не контекст `InventoryReportDetailsView` снизу (см.
   «Альтернативные потоки» о последствиях этого).
6. Обе функции первым делом синхронно фиксируют `final l10n =
   AppLocalizations.of(context)!;` — до входа в `try` — и дальше расходятся
   по формату.

**Ветка Excel (а/б).**

7. `_generateAndShareExcel` создаёт `ex.Excel.createExcel()`, переименовывает
   единственный лист (`'Sheet1'` → `l10n.inventory_report`), проставляет
   стили (`boldLabelStyle`/`headerCellStyle`/`dataCellStyle` с общей тонкой
   рамкой), затем построчно пишет: дату отчёта (`l10n.report_date`,
   `state.date`), ферму (`l10n.farm`, `state.farm?.name`), место (`l10n.place`,
   `state.place?.name`), пустую строку-разделитель, заголовок и содержимое
   секции «доп. номера» (`l10n.extra_animals_list` + счётчик,
   `state.otherAnimals` — те же неизвестные/несопоставленные номера, что и в
   секции «неизвестные номера» на самом экране, [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)),
   ещё две пустые строки, заголовок `l10n.scanned_animals_list` и полную
   табличную часть — заголовки колонок (№, вид, номер, порода, дата рождения,
   ферма, место, статус) и одну строку на каждое животное из
   `state.myAnimalsByKind` **независимо** от `_computeSections`, используемого
   для отображения на самом экране (свой собственный проход по тем же данным,
   свой собственный вызов `_getStatusText` на каждое животное — жёстко
   закодированные русские строки `'Учтено'`/`'Потеряно'`/`'С другого
   объекта'`, без `l10n`, как уже задокументировано в
   [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)).
8. `final directory = await getTemporaryDirectory();` (пакет
   `path_provider`), собирается имя файла
   (`'${l10n.inventory_report}_${DateFormat('yyyy-MM-dd_HH-mm').format(DateTime.now())}.xlsx'`),
   `final fileBytes = excel.encode();` — точка расхождения (а)/(б).
9. **(а) Любое исключение** на любом из шагов 7–8 или на шаге 10 ниже
   (построение книги, файловый I/O, вызов share) перехватывается общим
   `catch (e)` в конце метода: если `context.mounted` — показывает
   `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:
   Text('${l10n.error_creating_file}: $e')))`; если `context.mounted ==
   false` — не показывает ничего, ошибка нигде больше не логируется (ни
   `Talker`, ни любой другой механизм — весь файл `inventory_report_details_view.dart`
   не импортирует логгер).
10. **(б) `fileBytes == null` без исключения.** Если `excel.encode()`
    (`Save._save()` → `ZipEncoder().encode(...)` из пакета `archive`,
    транзитивной зависимости `excel`) вернул `null` — ветка `if (fileBytes !=
    null) {...}` не выполняется, выполняется её `else`: если `context.mounted`
    — показывает `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:
    Text(l10n.error_saving_file)))` — **без** текста исключения (его и не
    было); если `context.mounted == false` — так же ничего не показывает.
    Условие, при котором `ZipEncoder().encode(...)` реально возвращает `null`
    на практике, кодом `excel`/`archive` не гарантируется явно (защитная
    проверка на вырожденный случай) — воспроизведение этой ветки отдельным
    тестом в репозитории отсутствует (см. «Связанные тесты»).
11. Если `fileBytes != null` — `File(filePath).writeAsBytes(fileBytes)`,
    затем `SharePlus.instance.share(ShareParams(files: [XFile(filePath)],
    text: ...))` — это уже успешный путь (не документируется этим файлом,
    `READ_OK`).

**Ветка PDF (в).**

12. `_generateAndSharePdf` создаёt `pw.Document()`, резолвит шрифты
    `await PdfGoogleFonts.robotoRegular()`/`robotoBold()` (пакет `printing`).
    Важный смежный факт, перепроверенный чтением исходников пакета
    (`~/.pub-cache/hosted/pub.dev/printing-5.13.1/lib/src/fonts/font.dart`,
    `DownloadableFont.getFont`): загрузка шрифта обёрнута **собственным**
    `try/catch` внутри пакета — при сбое сети/загрузки шрифта исключение не
    пробрасывается наружу, метод молча возвращает `Font.helvetica()`. Значит,
    отсутствие сети во время резолва шрифтов **не** является источником
    ветки (в) этого сценария — деградация до Helvetica происходит тихо, ниже
    уровня `try/catch` `_generateAndSharePdf`.
13. Строит `pw.MultiPage` (альбомная A4) с теми же логическими секциями, что
    и Excel (дата/ферма/место, таблица доп. номеров, таблица отсканированных
    животных со статусом через тот же `_getStatusText`, вызванный отдельным,
    не переиспользуемым с Excel-веткой проходом по `state.myAnimalsByKind`).
14. `getTemporaryDirectory()`, `await pdf.save()` (тип `Uint8List`, не
    nullable — в отличие от `excel.encode()` эквивалентной проверки на
    `null` в коде нет и быть не может по контракту метода), запись файла,
    `SharePlus.instance.share(...)`.
15. **(в) Любое исключение** на шагах 12–14 перехватывается единственным
    `catch (e)` метода: если `context.mounted` — тот же паттерн, что и ветка
    (а): `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:
    Text('${l10n.error_creating_file}: $e')))`; иначе — ничего.
16. Во всех трёх случаях (а/б/в) сбой полностью локализован внутри метода
    экспорта: он не всплывает ни в `InventoryReportDetailsCubit`, ни в
    `InventoryReportDetailsState` (у которого, как задокументировано в
    [UC-132](UC-132-ACTOR-5-EVT-66-ENT-17-READ_ERROR-IN-ANIMAL.md), нет
    варианта `error`), сам экран отчёта под закрывшимся bottom sheet остаётся
    в точности таким же, каким был до попытки экспорта — ни одна строка
    `UnsentReportAnimals`/`ReportAnimals` не читается заново и не изменяется
    (экспорт целиком работает с уже загрученным `state`, ни разу не
    обращаясь к `UnsentReportAnimalsRepository`/`ReportAnimalsRepository`
    напрямую).

### Альтернативные потоки

- **Гонка между анимацией закрытия bottom sheet и асинхронной работой
  экспорта.** `context`, переданный в `_generateAndShareExcel`/
  `_generateAndSharePdf`, — это `BuildContext` самого `_ExportBottomSheet`,
  для которого `Navigator.of(context).pop()` уже вызван на предыдущей строке
  того же `onTap`. Пока проигрывается анимация закрытия
  `showModalBottomSheet` (её элемент не уничтожается синхронно самим
  `pop()`, а лишь запускает transition), `context.mounted` остаётся `true`;
  как только элемент действительно демонтирован по завершении этой
  анимации, `context.mounted` становится `false`. Обе функции — как в ветке
  каждого исключения (а/в), так и в ветке (б) — перед показом `SnackBar`
  проверяют именно этот `context.mounted`. Формирование Excel-книги/PDF-
  документа, запись файла и вызов системного диалога «поделиться» —
  небыстрая асинхронная последовательность; если она не укладывается в
  длительность transition-анимации закрытия bottom sheet, `context.mounted`
  успевает стать `false` раньше, чем выполнение доходит до
  `if (context.mounted) { ScaffoldMessenger... }` — тогда `SnackBar` **не
  показывается вовсе**, ни при исключении, ни при `fileBytes == null`:
  единственный след ошибки просто не появляется нигде. Это не проверено
  эмпирически (потребовало бы виджет-теста с управляемым `pump`/таймингами
  реальной транзишен-анимации) — вывод сделан статическим чтением кода и
  общих семантик `Navigator.pop`/`ModalBottomSheetRoute`, не запуском.
- **Отмена пользователем системного диалога «поделиться» — не этот
  сценарий.** `SharePlus.instance.share(...)` (пакет `share_plus`) возвращает
  `Future<ShareResult>` и не бросает исключение, если пользователь просто
  закрыл системный share-sheet без выбора получателя — такое поведение не
  проходит ни через ветку (а)/(в), ни через какое-либо сообщение об ошибке;
  экспорт в этом случае молча завершается успешно с точки зрения кода
  (файл создан и передан системе, дальнейшая судьба — вне контроля
  приложения).
- **`context.mounted == false` уже на момент входа в `catch`/`else` —
  общий случай, не специфичный для гонки с bottom sheet.** Если пользователь
  успел закрыть весь экран `InventoryReportDetailsView` (например, кнопкой
  «назад») ещё до завершения асинхронной работы экспорта, тот же guard
  `if (context.mounted)` так же тихо подавляет `SnackBar` — задокументировано
  здесь как частный случай общего правила, не как отдельная причина отказа.
- **Похожий по форме export-путь в другой под-области того же
  модуля не документируется здесь.** `lib/pages/animals_registry/cubit/animals_registry_cubit.dart`
  (`exportToExcel`, ключи `export_error_saving_file`/`export_error_creating_file` —
  однокоренные, но отдельные от `error_saving_file`/`error_creating_file`
  этого сценария) реализует внешне похожий Excel-экспорт для другого
  экрана/сущности и покрыт тестом (`test/pages/animals_registry_cubit_test.dart`)
  — упоминается только для контраста «есть тестовое покрытие похожего
  паттерна в другом месте приложения», не относится к [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  и не разбирается дальше в рамках этого документа.

### Связанные сущности

- [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md)
  (InventoryScanReport) — данные, которые пытается экспортировать сценарий,
  уже загружены `InventoryReportDetailsCubit.load()` до открытия bottom
  sheet ([EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md));
  сам экспорт не делает ни одного нового обращения к
  `UnsentReportAnimalsRepository`/`ReportAnimalsRepository` и не изменяет ни
  одну строку `UnsentReportAnimals`/`ReportAnimals` независимо от исхода —
  чисто клиентское формирование файла из уже прочитанных данных.
- [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) (Animal) — читается
  косвенно через уже построенные `AnimalWithDetails`-объекты в
  `state.myAnimalsByKind`; не перечитывается заново и не изменяется этим
  сценарием ни при успехе, ни при отказе.
- [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) (Farm), [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md)
  (Place) — `state.farm`/`state.place`, уже разрешённые вышестоящим
  `InventoryReportDetailsCubit.load()`; используются только для строк
  «ферма»/«место» в экспортируемом файле, не перечитываются и не изменяются.
- [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) (таксономия HANDBOOKS)
  — название вида/породы (`animal.kindNameText`, `animal.breed?.name`)
  берётся из уже вложенных в `AnimalWithDetails` объектов; ANIMAL здесь, как
  и везде, только ссылается на HANDBOOKS по id, не мутирует его.

### Бизнес-правила

- Результат — `READ_ERROR` для всех трёх веток (а/б/в): ни одна из них не
  является осознанным бизнес-отказом (`REJECTED`) — все три чисто
  технические (исключение либо необъяснённый `null` от библиотеки
  кодирования), поэтому ни одна не может быть `REJECTED` по определению
  закрытого словаря результатов.
- Ветка (б) (`fileBytes == null` у Excel) — единственная во всей
  под-области `INV`, где технический отказ обнаруживается **без**
  исключения, через явную проверку возвращаемого значения, а не через
  `catch`. Это отличает её от подавляющего большинства других
  `READ_ERROR`/`CREATE_ERROR`-сценариев `ANIMAL`, где единственный механизм
  обнаружения отказа — пойманное исключение.
- PDF-путь не имеет ветки, симметричной (б): `pdf.save()` не возвращает
  nullable-тип, и в коде нет отдельной проверки на пустой результат — если
  библиотека `pdf` когда-либо начнёт возвращать данные, которые формально не
  `null`, но нечитаемы, это не будет обнаружено ни на уровне
  `_generateAndSharePdf`, ни где-либо ещё в этом файле.
- И `error_creating_file`, и `error_saving_file` — статические,
  локализованные ключи (`AppLocalizations.of(context)!.error_creating_file`/
  `.error_saving_file`), в соответствии с общим правилом проекта для
  статических ключей; `error_creating_file` дополнительно конкатенируется с
  сырым `e.toString()` через интерполяцию строки, не через
  `error_creating_file_details(Object details)` — параметризованный ключ с
  тем же смыслом существует в `AppLocalizations`
  (`lib/l10n/app_localizations.dart`, `error_creating_file_details`), но в
  этом файле не используется ни разу — вместо него сообщение и сырой текст
  склеены вручную (`'${l10n.error_creating_file}: $e'`).
- Оба вызова `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:
  Text(...)))` — самодельные, без переиспользования проектного хелпера
  `lib/widgets/app_snackbar.dart` (`showAppSnackBarError` и т.д.,
  `.claude/rules/ui-architecture.md`) — отклонение от общего для проекта
  правила о SnackBar'ах; фиксируется здесь как факт CURRENT-кода, не
  исправляется в рамках этого документирующего прохода.
- Никакая из трёх веток не логируется ни в `Talker`, ни в любой другой
  механизм — единственный возможный след сбоя, который увидит кто-либо, это
  сам `SnackBar` (а он, как задокументировано в «Альтернативные потоки»,
  может и не успеть показаться из-за гонки с закрытием bottom sheet).

## TARGET

TARGET не отличается от CURRENT.

## TBD / BLOCKED

Блокеров для документирования нет — все три ветки (а: исключение в
Excel-пути, б: `fileBytes == null` без исключения в Excel-пути, в:
исключение в PDF-пути) статически прослеживаются чтением кода целиком:
`InventoryReportDetailsView`/`_ExportBottomSheet` →
`_generateAndShareExcel`/`_generateAndSharePdf` → пакеты `excel`/`pdf`/
`printing`/`share_plus`/`path_provider`. Единственный не закрытый вопрос —
эмпирическая проверка гонки `context.mounted` против анимации закрытия
bottom sheet (см. «Альтернативные потоки», «Открытые вопросы») — это не
блокер для фиксации уже существующего поведения, а открытый вопрос о его
надёжности на практике.

## Технические зависимости

| Файл | Символ | Статус | Роль |
|---|---|---|---|
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `InventoryReportDetailsView.build` (иконка `Icons.share` в `actions`) | CURRENT | видимость точки входа — только при `!state.isLoading && state.myAnimalsByKind.isNotEmpty` |
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `InventoryReportDetailsView._showExportBottomSheet` | CURRENT | `showModalBottomSheet(..., useRootNavigator: true, builder: (bottomSheetContext) => _ExportBottomSheet(state: state))` — `bottomSheetContext` параметра `builder` не используется |
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `_ExportBottomSheet.build` | CURRENT | оба `onTap` сначала `Navigator.of(context).pop()`, затем без `await` вызывают экспортный метод с тем же (закрываемым) `context` |
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `_ExportBottomSheet._generateAndShareExcel` | CURRENT | предмет сценария — ветки (а)/(б) |
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `_ExportBottomSheet._generateAndSharePdf` | CURRENT | предмет сценария — ветка (в) |
| `lib/pages/animals_inventory/presentation/widgets/inventory_report_details_view.dart` | `_ExportBottomSheet._getStatusText` | CURRENT | статус построчно, жёстко закодированные русские строки (`'Учтено'`/`'Потеряно'`/`'С другого объекта'`); вызывается независимо и Excel-, и PDF-веткой — код дублирован, не переиспользован |
| `lib/pages/animals_inventory/cubit/inventory_report_details_cubit.dart` | `InventoryReportDetailsCubit.load` | CURRENT | загружает `state`, потребляемый экспортом; сам экспорт его повторно не вызывает |
| `lib/pages/animals_inventory/cubit/inventory_report_details_state.dart` | `InventoryReportDetailsState` | CURRENT | источник `myAnimalsByKind`/`otherAnimals`/`farm`/`place`/`date`, используемых при построении файла |
| `~/.pub-cache/hosted/pub.dev/excel-4.0.6/lib/src/excel.dart` | `Excel.encode` | EXTERNAL | делегирует в `Save._save()` |
| `~/.pub-cache/hosted/pub.dev/excel-4.0.6/lib/src/save/save_file.dart` | `Save._save` | EXTERNAL | `return ZipEncoder().encode(...)` — может вернуть `null` без исключения, источник ветки (б) |
| `~/.pub-cache/hosted/pub.dev/printing-5.13.1/lib/src/fonts/font.dart` | `DownloadableFont.getFont` | EXTERNAL | собственный `try/catch`; при сбое загрузки шрифта тихо возвращает `Font.helvetica()`, не пробрасывая исключение — почему сбой сети при резолве шрифтов не является источником ветки (в) |
| `share_plus` (`^12.0.0`, `pubspec.yaml`) | `SharePlus.instance.share` | EXTERNAL | возвращает `Future<ShareResult>`, не бросает исключение при отмене пользователем системного диалога |
| `path_provider` (`^2.1.4`, `pubspec.yaml`) | `getTemporaryDirectory` | EXTERNAL | потенциальный источник исключения в обеих ветках (а)/(в) |
| `lib/l10n/app_ru.arb`, `app_en.arb` (и остальные языки) | `error_creating_file`, `error_saving_file` | CURRENT | локализованные ключи сообщений об ошибке |
| `lib/l10n/app_localizations.dart` | `error_creating_file_details(Object details)` | CURRENT | параметризованный ключ с тем же смыслом, существует, но не используется этим файлом — вместо него ручная интерполяция строки |
| `lib/widgets/app_snackbar.dart` | `showAppSnackBarError` и др. | CURRENT | проектный хелпер для SnackBar'ов — не используется этим файлом (см. «Бизнес-правила») |

## Критерии приёмки

- Если исключение брошено в любой точке `_generateAndShareExcel` (построение
  книги, `getTemporaryDirectory()`, запись файла, вызов `SharePlus.instance.share`) —
  и `context.mounted == true` в момент `catch` — пользователь видит `SnackBar`
  с текстом `'${l10n.error_creating_file}: $e'`.
- Если `excel.encode()` вернул `null` без исключения — и `context.mounted ==
  true` в этот момент — пользователь видит `SnackBar` с текстом
  `l10n.error_saving_file`, без текста исключения (его не было).
- Если исключение брошено в любой точке `_generateAndSharePdf` — и
  `context.mounted == true` в момент `catch` — пользователь видит тот же
  формат сообщения, что и ветка Excel (а): `'${l10n.error_creating_file}: $e'`.
  Эквивалента ветки (б) у PDF-пути нет.
- Если к моменту `catch`/`else` `context.mounted == false` (в частности —
  если анимация закрытия bottom sheet уже завершилась быстрее, чем
  асинхронная работа экспорта) — ни один `SnackBar` не показывается ни при
  каком из трёх исходов, и нигде больше след ошибки не остаётся.
- Ни при одном из трёх исходов не изменяется ни одна строка
  `UnsentReportAnimals`/`ReportAnimals`, и не эмитится новое состояние
  `InventoryReportDetailsCubit`/`InventoryReportDetailsState` — экран отчёта
  под закрывшимся bottom sheet остаётся в точности таким, каким был до
  попытки экспорта.
- Ни один из трёх исходов не логируется в `Talker` или любой другой
  механизм — единственный возможный след, который видит кто-либо, это сам
  `SnackBar` (если он успел показаться).
- Иконка `share` в `AppBar` отсутствует, если `state.myAnimalsByKind` пуст —
  весь сценарий этого файла для такого состояния структурно недостижим.

## Связанные тесты

TBD — теста нет. Ни `_generateAndShareExcel`, ни `_generateAndSharePdf`, ни
`_ExportBottomSheet`, ни сам `InventoryReportDetailsView` не встречаются ни в
одном тестовом файле репозитория — прямой поиск
(`grep -rln "InventoryReportDetailsView\|_generateAndShareExcel\|_generateAndSharePdf\|_ExportBottomSheet" test/`)
не находит ни одного совпадения; аналогично поиск по используемым пакетам
(`grep -rl "excel\|share_plus\|pdf\b\|printing" test/`) находит только
`test/pages/animals_registry_cubit_test.dart` — тест другого, не относящегося
к [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) экспортного
пути (`AnimalsRegistryCubit.exportToExcel`).

Единственный тестовый файл, покрывающий соседний код той же под-области —
`test/pages/inventory_report_details_cubit_test.dart` (группы `'UC-131 —
InventoryReportDetailsCubit.load (по дате)'` и `'UC-131 —
InventoryReportDetailsCubit.load (по sessionUuid)'`, старая нумерация,
переименуется отдельным контролируемым проходом), но он тестирует только
`InventoryReportDetailsCubit.load` ([EVT-66](../events/EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md)),
т.е. загрузку данных, не сам экспорт ([EVT-67](../events/EVT-67-ANIMAL-INVENTORY-REPORT-EXPORTED-IN-ANIMAL.md));
ни один `test`/`group` этого файла не мокает и не проверяет `excel`, `pdf`,
`printing`, `share_plus` или `path_provider`.

## Открытые вопросы и ограничения

- **Гонка `context.mounted` против анимации закрытия bottom sheet — не
  проверена эмпирически.** Как задокументировано в «Альтернативные потоки»,
  `context`, используемый обеими экспортными функциями и для `mounted`-guard'а,
  и для самого `ScaffoldMessenger.of(context)`, — это контекст уже
  закрываемого (`Navigator.pop()` вызван строкой раньше) `_ExportBottomSheet`,
  а не стабильный контекст `InventoryReportDetailsView` снизу. Если
  асинхронная работа экспорта (особенно PDF-путь — резолв шрифтов, пусть и
  без сетевого исключения, всё равно асинхронный, плюс запись файла и вызов
  системного диалога) не укладывается в длительность transition-анимации
  закрытия bottom sheet, `SnackBar` об ошибке не покажется вовсе — ни при
  исключении, ни при `fileBytes == null`. Является ли этот риск осознанно
  принятым (например, ожидание, что экспорт почти всегда завершается быстрее
  анимации) или недосмотром — ничем в коде/комментариях не зафиксировано; для
  точного ответа нужен виджет-тест с управляемым `pump`/таймингами, которого
  сейчас нет.
- **Почему у Excel есть защитная ветка (б), а у PDF — нет.** Ничего в коде не
  объясняет эту асимметрию: `pdf.save()` могло бы в принципе тоже
  проверяться на пустой/невалидный результат, но такой проверки нет —
  является ли это осознанным решением (раз API `pdf` не предполагает `null`)
  или просто нанесённой один раз, но не перенесённой на второй формат,
  логикой — не зафиксировано.
- **Дублирование логики построения таблицы/статуса между Excel- и
  PDF-ветками.** Обе функции независимо и заново проходят по
  `state.myAnimalsByKind` и вызывают одну и ту же `_getStatusText` — общий
  код не вынесен в разделяемый метод; любое будущее изменение бизнес-логики
  статуса потребует правки в двух местах одновременно, и уже сейчас — это
  просто наблюдение по факту чтения кода, не проверенный на практике риск
  рассинхронизации.
- **`ScaffoldMessenger.of(context).showSnackBar(...)` вместо проектного
  хелпера `lib/widgets/app_snackbar.dart`.** Оба вызова в этом файле не
  используют `showAppSnackBarError`/аналоги, вопреки общему правилу проекта
  (`.claude/rules/ui-architecture.md`) — фиксируется как факт CURRENT-кода,
  не исправляется в рамках этого документирующего прохода.
- **Существующий параметризованный ключ `error_creating_file_details(Object
  details)` не используется.** В `AppLocalizations` уже есть готовый
  параметризованный ключ с тем же смыслом, что и ручная интерполяция
  `'${l10n.error_creating_file}: $e'` — не зафиксировано, почему выбран
  ручной способ, а не он.
- Не проверено эмпирически на реальном запуске (эмуляторе/устройстве) —
  весь вывод сделан статическим чтением кода `inventory_report_details_view.dart`
  и исходников пакетов `excel`/`pdf`/`printing`/`share_plus`/`path_provider`
  в локальном `~/.pub-cache`, не запуском приложения или виджет-теста.
