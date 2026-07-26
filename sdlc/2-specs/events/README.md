# Events

Things that happen — the **what happens**.

Per `AGENTS.md`, each event is a separate spec named `EVT-{number}-NAME` —
one file per event, never one file listing many.

## Index

Group the table by module, so the event list doubles as a map of the domain.

Repeat one block per module, linking the heading to `../modules/<module>.md`:

### [MOD-1-AUTH](../modules/MOD-1-AUTH.md) ([BT-1](../../1-business-tasks/planning/BT-1-PLANNING-AUTH.md))
| ID | Event | Entity |
|----|-------|--------|
| [EVT-1](EVT-1-USER-SELF-REGISTERED-IN-AUTH.md) | user.self_registered | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) |
| [EVT-2](EVT-2-USER-LOGGED-IN-IN-AUTH.md) | user.logged_in | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |
| [EVT-3](EVT-3-USER-AUTO-LOGGED-IN-AFTER-REGISTRATION-OR-RESET-IN-AUTH.md) | user.auto_logged_in_after_registration_or_reset | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |
| [EVT-4](EVT-4-PASSWORD-RESET-CODE-REQUESTED-IN-AUTH.md) | password_reset.code_requested | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |
| [EVT-5](EVT-5-PASSWORD-RESET-COMPLETED-IN-AUTH.md) | password_reset.completed | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |
| [EVT-6](EVT-6-SESSION-CHECKED-AT-LAUNCH-IN-AUTH.md) | session.checked_at_launch | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |
| [EVT-7](EVT-7-USER-LOGGED-OUT-IN-AUTH.md) | user.logged_out | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |
| [EVT-8](EVT-8-SESSION-INVALIDATED-AUTOMATICALLY-IN-AUTH.md) | session.invalidated_automatically | [ENT-2](../entities/ENT-2-SESSION-IN-AUTH.md) |
| [EVT-9](EVT-9-USER-ACCOUNT-DELETION-REQUESTED-IN-AUTH.md) | user.account_deletion_requested | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) |

### [MOD-3-FARM](../modules/MOD-3-FARM.md) ([BT-3](../../1-business-tasks/planning/BT-3-PLANNING-FARM.md))
| ID | Event | Entity |
|----|-------|--------|
| [EVT-10](EVT-10-FARM-CREATED-IN-FARM.md) | farm.created | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |
| [EVT-11](EVT-11-FARM-EDITED-IN-FARM.md) | farm.edited | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |
| [EVT-12](EVT-12-FARM-CREATE-SYNCED-IN-FARM.md) | farm.create_synced | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |
| [EVT-13](EVT-13-FARM-UPDATE-SYNCED-IN-FARM.md) | farm.update_synced | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |
| [EVT-14](EVT-14-FARMS-RELOADED-FROM-SERVER-IN-FARM.md) | farms.reloaded_from_server | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |
| [EVT-15](EVT-15-PLACE-CREATED-IN-FARM.md) | place.created | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |
| [EVT-16](EVT-16-PLACE-EDITED-IN-FARM.md) | place.edited | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |
| [EVT-17](EVT-17-PLACE-DELETION-REQUESTED-IN-FARM.md) | place.deletion_requested | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |
| [EVT-18](EVT-18-PLACE-CREATE-SYNCED-IN-FARM.md) | place.create_synced | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |
| [EVT-19](EVT-19-PLACE-UPDATE-SYNCED-IN-FARM.md) | place.update_synced | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |
| [EVT-20](EVT-20-PLACE-DELETION-SYNCED-IN-FARM.md) | place.deletion_synced | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |
| [EVT-21](EVT-21-PLACES-RELOADED-FROM-SERVER-IN-FARM.md) | places.reloaded_from_server | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |
| [EVT-102](EVT-102-FARM-CARD-VIEWED-IN-FARM.md) | farm_card.viewed | [ENT-9](../entities/ENT-9-FARM-IN-FARM.md) |
| [EVT-103](EVT-103-PLACE-CARD-VIEWED-IN-FARM.md) | place_card.viewed | [ENT-10](../entities/ENT-10-PLACE-IN-FARM.md) |

### [MOD-4-ANIMAL](../modules/MOD-4-ANIMAL.md) ([BT-4](../../1-business-tasks/planning/BT-4-PLANNING-ANIMAL-REG.md) REG, [BT-5](../../1-business-tasks/planning/BT-5-PLANNING-ANIMAL-MOVE.md) MOVE, [BT-6](../../1-business-tasks/planning/BT-6-PLANNING-ANIMAL-VAC.md) VAC, [BT-7](../../1-business-tasks/planning/BT-7-PLANNING-ANIMAL-WEIGH.md) WEIGH, [BT-8](../../1-business-tasks/planning/BT-8-PLANNING-ANIMAL-DISP.md) DISP, [BT-9](../../1-business-tasks/planning/BT-9-PLANNING-ANIMAL-REPRO.md) REPRO, [BT-10](../../1-business-tasks/planning/BT-10-PLANNING-ANIMAL-INV.md) INV)
| ID | Event | Entity |
|----|-------|--------|
| [EVT-22](EVT-22-ANIMAL-REGISTERED-LOCALLY-IN-ANIMAL.md) | animal.registered_locally | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| [EVT-23](EVT-23-ANIMAL-LOCAL-EDITED-IN-ANIMAL.md) | animal.local_edited | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| [EVT-24](EVT-24-ANIMAL-EDITED-DEFERRED-IN-ANIMAL.md) | animal.edited_deferred | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| [EVT-25](EVT-25-ANIMAL-CREATION-SYNCED-IN-ANIMAL.md) | animal.creation_synced | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| [EVT-26](EVT-26-ANIMAL-EDIT-SYNCED-IN-ANIMAL.md) | animal.edit_synced | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| [EVT-27](EVT-27-MOVEMENT-RECORDED-IN-ANIMAL.md) | movement.recorded | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |
| [EVT-28](EVT-28-MOVEMENT-DELETED-UNSENT-IN-ANIMAL.md) | movement.deleted_unsent | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |
| [EVT-29](EVT-29-MOVEMENT-DELETED-VIA-REPORT-IN-ANIMAL.md) | movement.deleted_via_report | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |
| [EVT-30](EVT-30-MOVEMENT-PUSH-SYNCED-IN-ANIMAL.md) | movement.push_synced | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |
| [EVT-31](EVT-31-MOVEMENTS-RELOADED-FROM-SERVER-IN-ANIMAL.md) | movements.reloaded_from_server | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |
| [EVT-104](EVT-104-MOVEMENTS-VIEWED-UNSENT-IN-ANIMAL.md) | movements.viewed_unsent | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |
| [EVT-105](EVT-105-MOVEMENTS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) | movements.viewed_in_day_report | [ENT-13](../entities/ENT-13-MOVEMENT-IN-ANIMAL.md) |
| [EVT-32](EVT-32-VACCINATION-RECORDED-IN-ANIMAL.md) | vaccination.recorded | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| [EVT-33](EVT-33-VACCINATION-EDITED-UNSENT-IN-ANIMAL.md) | vaccination.edited_unsent | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| [EVT-34](EVT-34-VACCINATION-DELETED-UNSENT-IN-ANIMAL.md) | vaccination.deleted_unsent | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| [EVT-35](EVT-35-VACCINATION-DELETION-PUSH-SYNCED-IN-ANIMAL.md) | vaccination.deletion_push_synced | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| [EVT-36](EVT-36-VACCINATION-EDIT-PUSH-SYNCED-IN-ANIMAL.md) | vaccination.edit_push_synced | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| [EVT-37](EVT-37-VACCINATION-CREATION-PUSH-SYNCED-IN-ANIMAL.md) | vaccination.creation_push_synced | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| [EVT-38](EVT-38-VACCINATIONS-RELOADED-FROM-SERVER-IN-ANIMAL.md) | vaccinations.reloaded_from_server | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| [EVT-39](EVT-39-VACCINATIONS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md) | vaccinations.viewed_for_animal | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| [EVT-40](EVT-40-VACCINATIONS-VIEWED-UNSENT-IN-ANIMAL.md) | vaccinations.viewed_unsent | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| [EVT-41](EVT-41-VACCINATIONS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) | vaccinations.viewed_in_day_report | [ENT-14](../entities/ENT-14-VACCINATION-IN-ANIMAL.md) |
| [EVT-42](EVT-42-ANIMAL-WEIGHING-RECORDED-IN-ANIMAL.md) | animal_weighing.recorded | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| [EVT-43](EVT-43-ANIMAL-WEIGHING-EDITED-IN-ANIMAL.md) | animal_weighing.edited | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| [EVT-44](EVT-44-ANIMAL-WEIGHING-DELETED-UNSENT-IN-ANIMAL.md) | animal_weighing.deleted_unsent | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| [EVT-45](EVT-45-ANIMAL-WEIGHINGS-PUSH-SYNCED-IN-ANIMAL.md) | animal_weighings.push_synced | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| [EVT-46](EVT-46-ANIMAL-WEIGHINGS-RELOADED-FROM-SERVER-IN-ANIMAL.md) | animal_weighings.reloaded_from_server | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| [EVT-47](EVT-47-ANIMAL-WEIGHINGS-VIEWED-FOR-ANIMAL-IN-ANIMAL.md) | animal_weighings.viewed_for_animal | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| [EVT-48](EVT-48-ANIMAL-WEIGHINGS-VIEWED-UNSENT-IN-ANIMAL.md) | animal_weighings.viewed_unsent | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| [EVT-49](EVT-49-ANIMAL-WEIGHINGS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) | animal_weighings.viewed_in_day_report | [ENT-15](../entities/ENT-15-ANIMAL-WEIGHING-IN-ANIMAL.md) |
| [EVT-50](EVT-50-DISPOSAL-RECORDED-IN-ANIMAL.md) | disposal.recorded | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| [EVT-51](EVT-51-DISPOSAL-DELETED-UNSENT-IN-ANIMAL.md) | disposal.deleted_unsent | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| [EVT-52](EVT-52-DISPOSAL-DELETED-VIA-REPORT-IN-ANIMAL.md) | disposal.deleted_via_report | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| [EVT-53](EVT-53-DISPOSAL-PUSH-SYNCED-IN-ANIMAL.md) | disposal.push_synced | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| [EVT-54](EVT-54-DISPOSALS-RELOADED-FROM-SERVER-IN-ANIMAL.md) | disposals.reloaded_from_server | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| [EVT-55](EVT-55-DISPOSALS-VIEWED-UNSENT-IN-ANIMAL.md) | disposals.viewed_unsent | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| [EVT-56](EVT-56-DISPOSALS-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) | disposals.viewed_in_day_report | [ENT-16](../entities/ENT-16-DISPOSAL-IN-ANIMAL.md) |
| [EVT-57](EVT-57-ANIMAL-HISTORY-VIEWED-IN-ANIMAL.md) | animal.history_viewed | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| [EVT-58](EVT-58-ANIMAL-PARENT-LINKED-IN-ANIMAL.md) | animal.parent_linked | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| [EVT-59](EVT-59-ANIMAL-CHILD-LINKED-IN-ANIMAL.md) | animal.child_linked | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| [EVT-60](EVT-60-ANIMAL-REPRODUCTION-VIEWED-IN-ANIMAL.md) | animal.reproduction_viewed | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| [EVT-61](EVT-61-ANIMAL-INVENTORY-RECORDED-IN-ANIMAL.md) | animal_inventory.recorded | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| [EVT-62](EVT-62-ANIMAL-INVENTORY-EDITED-IN-ANIMAL.md) | animal_inventory.edited | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| [EVT-63](EVT-63-ANIMAL-INVENTORY-PUSH-SYNCED-IN-ANIMAL.md) | animal_inventory.push_synced | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| [EVT-64](EVT-64-ANIMAL-INVENTORY-RELOADED-FROM-SERVER-IN-ANIMAL.md) | animal_inventory.reloaded_from_server | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| [EVT-65](EVT-65-ANIMAL-INVENTORY-VIEWED-UNSENT-IN-ANIMAL.md) | animal_inventory.viewed_unsent | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| [EVT-66](EVT-66-ANIMAL-INVENTORY-VIEWED-IN-DAY-REPORT-IN-ANIMAL.md) | animal_inventory.viewed_in_day_report | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |
| [EVT-67](EVT-67-ANIMAL-INVENTORY-REPORT-EXPORTED-IN-ANIMAL.md) | animal_inventory.report_exported | [ENT-17](../entities/ENT-17-INVENTORY-SCAN-REPORT-IN-ANIMAL.md) |

### [MOD-5-BOARD](../modules/MOD-5-BOARD.md) ([BT-11](../../1-business-tasks/planning/BT-11-PLANNING-BOARD.md))
| ID | Event | Entity |
|----|-------|--------|
| [EVT-68](EVT-68-AD-PUBLISHED-IN-BOARD.md) | ad.published | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| [EVT-69](EVT-69-AD-EDITED-IN-BOARD.md) | ad.edited | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| [EVT-70](EVT-70-AD-DELETED-IN-BOARD.md) | ad.deleted | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| [EVT-71](EVT-71-AD-FAVOURITE-TOGGLED-IN-BOARD.md) | ad.favourite_toggled | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| [EVT-72](EVT-72-ADS-FEED-VIEWED-IN-BOARD.md) | ads.feed_viewed | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| [EVT-73](EVT-73-AD-DETAIL-VIEWED-IN-BOARD.md) | ad.detail_viewed | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| [EVT-74](EVT-74-MY-ADS-VIEWED-IN-BOARD.md) | my_ads.viewed | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| [EVT-75](EVT-75-FAVOURITE-ADS-VIEWED-IN-BOARD.md) | favourite_ads.viewed | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| [EVT-76](EVT-76-MESSAGE-SENT-IN-BOARD.md) | message.sent | [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) |
| [EVT-77](EVT-77-CHATS-VIEWED-IN-BOARD.md) | chats.viewed | [ENT-19](../entities/ENT-19-CHAT-IN-BOARD.md) |
| [EVT-78](EVT-78-MESSAGES-VIEWED-IN-BOARD.md) | messages.viewed | [ENT-20](../entities/ENT-20-CHAT-MESSAGE-IN-BOARD.md) |
| [EVT-79](EVT-79-BOARD-AVAILABILITY-CHECKED-IN-BOARD.md) | board_availability.checked | [ENT-4](../entities/ENT-4-COUNTRY-IN-HANDBOOKS.md) |
| [EVT-80](EVT-80-AD-CONTACT-CALLED-IN-BOARD.md) | ad_contact.called | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |

### [MOD-6-PROFILE](../modules/MOD-6-PROFILE.md) ([BT-12](../../1-business-tasks/planning/BT-12-PLANNING-PROFILE.md))
| ID | Event | Entity |
|----|-------|--------|
| [EVT-81](EVT-81-USER-PROFILE-VIEWED-IN-PROFILE.md) | user.profile_viewed | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) |
| [EVT-82](EVT-82-USER-PROFILE-EDITED-IN-PROFILE.md) | user.profile_edited | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) |
| [EVT-83](EVT-83-LANGUAGE-CHANGED-IN-PROFILE.md) | language.changed | [ENT-1](../entities/ENT-1-USER-IN-AUTH.md) |
| [EVT-84](EVT-84-VACCINATION-NOTIFICATION-SETTINGS-VIEWED-IN-PROFILE.md) | vaccination_notification_settings.viewed | [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) |
| [EVT-85](EVT-85-VACCINATION-NOTIFICATION-SETTINGS-SAVED-IN-PROFILE.md) | vaccination_notification_settings.saved | [ENT-21](../entities/ENT-21-PROFILE-SETTINGS-IN-PROFILE.md) |
| [EVT-86](EVT-86-KIND-VISIBILITY-VIEWED-IN-PROFILE.md) | kind_visibility.viewed | [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) |
| [EVT-87](EVT-87-KIND-VISIBILITY-SAVED-IN-PROFILE.md) | kind_visibility.saved | [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) |
| [EVT-88](EVT-88-DEVICE-SETTINGS-VIEWED-IN-PROFILE.md) | device_settings.viewed | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| [EVT-89](EVT-89-DEVICE-SETTINGS-SAVED-IN-PROFILE.md) | device_settings.saved | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| [EVT-90](EVT-90-DEVICE-SETTINGS-CREATE-SYNCED-IN-PROFILE.md) | device_settings.create_synced | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| [EVT-91](EVT-91-DEVICE-SETTINGS-UPDATE-SYNCED-IN-PROFILE.md) | device_settings.update_synced | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |
| [EVT-92](EVT-92-DEVICE-SETTINGS-RELOADED-FROM-SERVER-IN-PROFILE.md) | device_settings.reloaded_from_server | [ENT-22](../entities/ENT-22-DEVICE-IN-PROFILE.md) |

### [MOD-7-SYSTEM](../modules/MOD-7-SYSTEM.md) ([BT-13](../../1-business-tasks/planning/BT-13-PLANNING-SYSTEM.md))
| ID | Event | Entity |
|----|-------|--------|
| [EVT-93](EVT-93-FULL-SYNC-PASS-TRIGGERED-AUTOMATICALLY-IN-SYSTEM.md) | full_sync_pass.triggered_automatically | [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) |
| [EVT-94](EVT-94-FULL-SYNC-PASS-TRIGGERED-MANUALLY-IN-SYSTEM.md) | full_sync_pass.triggered_manually | [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) |
| [EVT-95](EVT-95-LOCAL-DATA-CLEARED-IN-SYSTEM.md) | local_data.cleared | [ENT-23](../entities/ENT-23-DATA-UPDATE-IN-SYSTEM.md) |
| [EVT-96](EVT-96-DIRECTORIES-SYNCED-IN-SYSTEM.md) | directories.synced | [ENT-3](../entities/ENT-3-TAXONOMY-IN-HANDBOOKS.md) |
| [EVT-97](EVT-97-BOARD-DIRECTORIES-SYNCED-IN-SYSTEM.md) | board_directories.synced | [ENT-18](../entities/ENT-18-AD-IN-BOARD.md) |
| [EVT-98](EVT-98-IN-WORK-SUMMARY-VIEWED-IN-SYSTEM.md) | in_work_summary.viewed | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| [EVT-99](EVT-99-EVENTS-CALENDAR-VIEWED-IN-SYSTEM.md) | events_calendar.viewed | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |
| [EVT-100](EVT-100-APP-UPDATE-CHECKED-IN-SYSTEM.md) | app_update.checked | [ENT-24](../entities/ENT-24-NEW-APP-VERSION-IN-SYSTEM.md) |
| [EVT-101](EVT-101-DAY-EVENTS-LIST-VIEWED-IN-SYSTEM.md) | day_events_list.viewed | [ENT-11](../entities/ENT-11-ANIMAL-IN-ANIMAL.md) |

Номера не переиспользуются, следующее новое событие — `EVT-106`.
