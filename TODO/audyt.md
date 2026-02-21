# Audyt wdrożenia: PLAN-OPTYMALIZACJI vs Stan aktualny

> Porównanie planu z `2026-02-21T10:16` z aktualnym stanem projektu `2026-02-21T16:57`

---

## Werdykt: ❌ Plan pluginowy NIE został wdrożony

Żaden z 30 ticketów z planu optymalizacji wdrożeniowej nie został zaimplementowany. Katalog `dockfra/deployers/` nie istnieje. Nie ma ABC `DeployerPlugin`, registry, pluginów platform, ani `deploy-targets.yaml`.

**Natomiast** projekt rozwijał się aktywnie w innych kierunkach — przybyło dużo wartościowego kodu.

---

## Co się zmieniło (delta 10:16 → 16:57)

### Nowe moduły i pliki

| Nowy plik | Opis |
|-----------|------|
| `app/src/index.js` | Frontend entry point (nowy) |
| `app/src/components/ContactForm.js` | Komponent formularza kontaktowego |
| `app/src/routes/contact.js` | Routing kontaktowy |
| `app/cypress/integration/contact.spec.js` | Testy E2E Cypress |
| `test_parse.py` | Moduł parsowania (pusty — stub?) |

### Rozbudowane moduły (nowe funkcje)

#### `core.py`: 40 → 45 funkcji (+5 nowych)

| Nowa funkcja | Opis |
|---|---|
| `_expand_env_vars(text)` | Rozwiń `${VAR:-default}` w stringach |
| `_eval_post_launch_condition(cond, running_names)` | Ewaluacja warunków post-launch |
| `_render_post_launch(running_names, ssh_roles)` | Buduj przyciski post-launch z dockfra.yaml hooków |
| `save_state()` | Persystuj stan do `.state.json` |
| `load_state()` | Wczytaj stan z `.state.json` |

#### `app.py`: 53 → 57 funkcji (+4 nowe)

| Nowa funkcja | Opis |
|---|---|
| `_ticket_missing_required_fields(ticket_like)` | Walidacja wymaganych pól ticketu |
| `_step_ticket_requirements_form(tid, form)` | Formularz wymagań przed pipeline |
| `_step_ticket_requirements_save(tid, form)` | Zapis wymagań ticketu |
| `_step_pipeline_skip_implement(ticket_id)` | Kontynuuj pipeline z pominięciem implementacji |

`_dispatch()` rozrósł się z 415 do 590 linii (+175 linii nowej logiki routingu).

#### `tests/test_e2e.py`: 78 → 162 testów (+84 nowe!)

| Nowa klasa testowa | Testów | Co testuje |
|---|---|---|
| `TestSaveEnvActions` | 2 | Zapis zmiennych env przez wizard |
| `TestCLIHelpers` | 12 | Kolorowanie logów, renderowanie MD, kolory |
| `TestWizardClient` | 5 | Klient REST: init, ping, offline handling |
| `TestCLICommands` | 11 | Wszystkie komendy CLI w trybie offline |
| `TestPipelineModule` | 20 | StepResult, evaluate, run_step, PipelineState |
| `TestPersistentState` | 4 | save/load state, sekrety, corrupt files |
| `TestSharedLibTicketSystem` | 9 | Shared lib: CRUD, filter, format, sync |
| `TestPostLaunchHooks` | 11 | expand_env_vars, warunki, render hooków |
| `TestTicketDiffAPI` (rozszerzony) | +1 | Odczyt commitów z kontenera developer |

#### Mniejsze zmiany

| Moduł | Zmiana |
|---|---|
| `i18n.py` | 6 → 5 funkcji (usunięto `get_lang_name`) |
| `steps.py` | Bez zmian w liczbie (22), drobne refaktory |
| `discover.py` | `run_ssh_cmd` rozrósł się 126 → 147 linii |
| `_sid_emit()` | 22 → 27 linii, CC 6 → 11 (więcej logiki) |
| `_emit_log_error()` | 109 → 157 linii, CC 37 → 64 (nowe wzorce) |
| `_step_ticket_create_wizard()` | 22 → 26 linii, CC 1 → 7 |

---

## Status planu — ticket po tickecie

### FAZA 1: Fundament pluginowy

| Ticket | Status | Komentarz |
|--------|--------|-----------|
| T-0100 | ❌ Nie zrobiony | Brak `dockfra/deployers/__init__.py` |
| T-0101 | ❌ Nie zrobiony | Brak `dockfra/deployers/base.py` (ABC) |
| T-0102 | ❌ Nie zrobiony | Brak `dockfra/deployers/registry.py` |
| T-0103 | ❌ Nie zrobiony | Brak `dockfra/deployers/ssh_utils.py` |
| T-0104 | ❌ Nie zrobiony | Brak `dockfra/deployers/manifest.py` |
| T-0105 | ❌ Nie zrobiony | Brak `dockfra/deployers/health.py` |

### FAZA 2: Plugin Docker Compose

| Ticket | Status | Komentarz |
|--------|--------|-----------|
| T-0110 | ❌ Nie zrobiony | Brak pluginu docker_compose |
| T-0111 | ❌ Nie zrobiony | Brak plugin.yaml |
| T-0112 | ❌ Nie zrobiony | Brak test_deployers.py |

### FAZA 3: Nowe pluginy

| Ticket | Status | Komentarz |
|--------|--------|-----------|
| T-0120 | ❌ Nie zrobiony | Brak pluginu Podman |
| T-0121 | ❌ Nie zrobiony | Brak pluginu Kubernetes |
| T-0122 | ❌ Nie zrobiony | Brak pluginu Swarm |
| T-0123 | ❌ Nie zrobiony | Brak pluginu Nomad |
| T-0124 | ❌ Nie zrobiony | Brak pluginu SSH Raw |

### FAZA 4: Integracja

| Ticket | Status | Komentarz |
|--------|--------|-----------|
| T-0130 | ❌ Nie zrobiony | Brak `load_deploy_targets()` w core.py |
| T-0131 | ❌ Nie zrobiony | `step_deploy_device()` bez zmian |
| T-0132 | ❌ Nie zrobiony | pipeline.py bez deploy step |
| T-0133 | ❌ Nie zrobiony | Brak API `/api/deploy-targets` |
| T-0134 | ❌ Nie zrobiony | Brak CLI `cmd_targets`, `cmd_deploy` |
| T-0135 | ❌ Nie zrobiony | discover.py bez deploy targets |

### FAZY 5-7: Multi-OS, UI, Zaawansowane

| Faza | Status |
|------|--------|
| Faza 5 (T-0140..0142) | ❌ Nie zrobione |
| Faza 6 (T-0150..0153) | ❌ Nie zrobione |
| Faza 7 (T-0160..0164) | ❌ Nie zrobione |

---

## Co zostało zrobione zamiast planu (i co jest wartościowe)

Prace poszły w kierunku **stabilizacji i dojrzałości** projektu:

### 1. Persystencja stanu (nowe w core.py)
- `save_state()` / `load_state()` → stan wizard przeżywa restart
- Filtrowanie sekretów z persystowanego stanu (test potwierdza)

### 2. Post-launch hooks (nowe w core.py)
- `_expand_env_vars()` → obsługa `${VAR:-default}` w hookach
- `_eval_post_launch_condition()` → warunki: `stack_exists`, `container_running`
- `_render_post_launch()` → dynamiczne przyciski po uruchomieniu stacków
- 11 testów potwierdzających poprawność

### 3. Walidacja ticketów przed pipeline (nowe w app.py)
- `_ticket_missing_required_fields()` → sprawdź czy ticket ma wystarczające dane
- `_step_ticket_requirements_form()` → formularz uzupełniania wymagań
- `_step_ticket_requirements_save()` → zapis i kontynuacja pipeline
- `_step_pipeline_skip_implement()` → ominięcie kroku implementacji

### 4. Pokrycie testami (+84 testy)
- CLI helpers, WizardClient, offline behavior
- Pipeline module (StepResult, evaluate, retry)
- Persistent state (save/load/corrupt/secrets)
- Shared lib ticket system (CRUD kompletny)
- Post-launch hooks (warunki, expand, render)

### 5. Aplikacja frontendowa
- ContactForm component, routing, testy Cypress

---

## Co jeszcze można zrobić (poza planem)

### A. Natychmiastowe ulepszenia istniejącego kodu

| Propozycja | Uzasadnienie | Wysiłek |
|---|---|---|
| **Rozbić `_dispatch()` (590 linii, CC=71)** | Najwyższy cyclomatic complexity w projekcie. Ciężki do testowania i utrzymania. Wydzielić dispatch table / command pattern. | 🟡 1 dzień |
| **Rozbić `_emit_log_error()` (157 linii, CC=64)** | Drugi najwyższy CC. Wydzielić wzorce do konfiguracji / reguł. | 🟡 1 dzień |
| **Rozbić `_detect_suggestions()` (202 linii, CC=88)** | Trzeci najwyższy CC. Każdy detector jako osobna funkcja. | 🟡 1 dzień |
| **Dodać type hints** | core.py, steps.py, app.py mają minimalne type hints | 🟢 2 dni |
| **Dodać docstrings** | Wiele funkcji w steps.py ma placeholder "step X" bez opisu | 🟢 1 dzień |

### B. Architekturalne ulepszenia

| Propozycja | Uzasadnienie |
|---|---|
| **Config as Code** | `dockfra.yaml` obsługuje env vars i hooks, ale brak walidacji schematu (np. jsonschema/pydantic) |
| **Async pipeline** | Pipeline wykonuje się synchronicznie — dla wielu targetów potrzebny async/concurrent |
| **Plugin system dla engines** | `engines.py` ma hardcoded 5 silników z identycznym wzorcem detect/test/implement — ten sam ABC pattern co w planie deployers |
| **Webhook/notification system** | Brak powiadomień o wynikach pipeline/deploy |
| **Rate limiting API** | `/api/*` endpointy bez rate limit |
| **API authentication** | Brak auth na API (ważne dla produkcji) |

### C. Ulepszenia testów

| Propozycja | Obecny stan | Cel |
|---|---|---|
| Testy integrations (GitHub/Jira/Trello/Linear) | 0 testów, tylko `sync_all_no_integrations` | Mock API testy |
| Testy engines.py | 0 testów jednostkowych | Mock container testy |
| Testy fixes.py | 0 testów | Mock docker testy |
| Testy discover.py | 0 testów | Filesystem mock testy |
| Testy wizard.js | 0 testów JS | Jest/Vitest |
| Coverage report | Brak | pytest-cov z progiem 80% |

### D. DevOps / CI

| Propozycja | Opis |
|---|---|
| **GitHub Actions CI** | Automatyczny pytest na PR |
| **Pre-commit hooks** | ruff/black/mypy |
| **Release automation** | Automatyczny bump VERSION + CHANGELOG |
| **Docker image publish** | Push do GHCR na tag |

---

## Rekomendowana kolejność dalszych prac

```
PRIORYTET 1 — Stabilność (tydzień 1)
├── Rozbij _dispatch() na dispatch table        → CC 71 → ~10
├── Rozbij _emit_log_error() na rule engine     → CC 64 → ~8
├── Rozbij _detect_suggestions() na detectors   → CC 88 → ~5
├── Dodaj testy dla engines.py (mock)           → 0 → ~15 testów
└── Dodaj testy dla fixes.py (mock)             → 0 → ~10 testów

PRIORYTET 2 — Plan pluginowy, Sprint 1 (tydzień 2-3)
├── T-0100..T-0105: Fundament deployers/
├── T-0110..T-0112: Plugin Docker Compose
└── T-0130..T-0135: Integracja z wizard/CLI/pipeline

PRIORYTET 3 — Plan pluginowy, Sprint 2 (tydzień 3-4)
├── T-0120..T-0124: Pluginy platform (Podman, K8s, Swarm, Nomad, SSH)
├── T-0140..T-0142: Multi-OS
└── T-0150..T-0153: UI + dokumentacja

PRIORYTET 4 — Dojrzałość (tydzień 5+)
├── API auth + rate limiting
├── CI/CD pipeline (GitHub Actions)
├── Plugin system dla engines.py (analogiczny do deployers)
├── Async pipeline execution
└── Faza 7 planu (blue-green, canary, OCI push, notifications)
```

---

## Statystyki porównawcze

| Metryka | Przed (10:16) | Teraz (16:57) | Delta |
|---------|---------------|---------------|-------|
| Moduły | 26 | 31 | +5 |
| Funkcje łącznie | ~490 | ~580 | +~90 |
| Testy E2E | 78 | 162 | **+84** |
| core.py funkcje | 40 | 45 | +5 |
| app.py funkcje | 53 | 57 | +4 |
| app.py `_dispatch` linii | 415 | 590 | +175 |
| Max CC (cyclomatic) | 88 | 88 | = |
| Moduły deployers/ | 0 | 0 | **0** |
| Tickety z planu zrealizowane | — | 0/30 | **0%** |