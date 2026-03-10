# Замечания по реализации (blocked/skipped/critical partial)

## Текущий цикл `plan:T1.1-T4.1`
- Проблемные единицы (`blocked`/`skipped`/`critical partial`) в рамках задач `T1.1-T4.1` отсутствуют.
- Все задачи текущего плана закрыты со статусом `done`.

## 1) `edit:E4` — Финальная parity/e2e/perf валидация async-миграции
- **Тип источника:** `edit`
- **ID:** `E4`
- **Название:** Формально закрыть эксплуатационные критерии (`parity/e2e/smoke/perf`)
- **Статус:** `closed`
- **Решение:** зафиксирован инженерный baseline-профиль `N=10` параллельных пользователей и выполнен локальный acceptance-прогон через `scripts/e4_acceptance_check.py` с сохранением артефактов:
  - `artifacts/e4/e4_acceptance_report.json`,
  - `artifacts/e4/e4_acceptance_summary.log`.
- **Подтверждено:** parity для `apply/clear/reply/update`, e2e/smoke проверка `auth refresh`, отсутствие burst/regression по latency и отсутствие роста event-loop blocking относительно baseline.
- **Ограничения валидности baseline:** результаты релевантны локальному mock-контруру и baseline `N=10`; для production-like профиля потребуется отдельный прогон на целевом стенде с реальными внешними зависимостями.
- **Влияние на проект:** блокер снят, правка `E4` закрыта для текущего цикла ревью.
- **Критичность:** `medium`
- **Рекомендованное следующее действие:** при подготовке релиза дополнительно повторить скрипт на production-like стенде с увеличенным `N` и приложить артефакты тем же форматом.

## Текущий цикл `edits.md` (CRITICAL/HIGH)
- Проблемные единицы (`blocked`/`skipped`/`critical partial`) отсутствуют.
- `critical` и `high` пункты из ревью закрыты со статусом `done`.
