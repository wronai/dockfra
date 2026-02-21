"""Dockfra i18n — centralised translation system for all 10 supported languages.

Usage:
    from .i18n import t, set_lang, get_lang, LANGUAGES

    set_lang('en')          # set current language (thread-local)
    t('welcome_title')      # → "Dockfra Setup Wizard"
    t('missing_n', n=3)     # → "Fill in 3 missing settings:"
"""
import threading

__all__ = [
    't', 'set_lang', 'get_lang', 'get_lang_name', 'LANGUAGES', 'LANG_NAMES',
    'llm_lang_instruction',
]

LANGUAGES = ('pl', 'en', 'de', 'fr', 'es', 'it', 'pt', 'cs', 'ro', 'nl')

LANG_NAMES = {
    'pl': 'Polski',   'en': 'English',    'de': 'Deutsch',    'fr': 'Français',
    'es': 'Español',  'it': 'Italiano',   'pt': 'Português',  'cs': 'Čeština',
    'ro': 'Română',   'nl': 'Nederlands',
}

# Thread-local language (wizard may handle concurrent sessions)
_tl = threading.local()
_DEFAULT_LANG = 'pl'


def set_lang(lang: str):
    """Set the current language for this thread."""
    _tl.lang = lang if lang in LANGUAGES else _DEFAULT_LANG


def get_lang() -> str:
    """Get the current language for this thread."""
    return getattr(_tl, 'lang', _DEFAULT_LANG)


def get_lang_name(lang: str = '') -> str:
    """Human-readable language name."""
    return LANG_NAMES.get(lang or get_lang(), lang or get_lang())


# ── Translation table ────────────────────────────────────────────────────────
# Keys are semantic identifiers. Values are dicts {lang: string}.
# Strings may contain {named} placeholders for .format(**kwargs).
_STRINGS: dict[str, dict[str, str]] = {}


def _add(key: str, **translations):
    """Register translations for a key. Must include at least 'pl' and 'en'."""
    _STRINGS[key] = translations


def t(key: str, **kwargs) -> str:
    """Translate key to current language, with optional format kwargs."""
    entry = _STRINGS.get(key)
    if not entry:
        return key
    lang = get_lang()
    text = entry.get(lang) or entry.get('en') or entry.get('pl') or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


# ── LLM language instruction (injected into system prompts) ──────────────────
def llm_lang_instruction() -> str:
    """Return an instruction string for the LLM to respond in the current language."""
    lang = get_lang()
    name = get_lang_name(lang)
    if lang == 'en':
        return "Respond in English."
    return f"IMPORTANT: Always respond in {name} ({lang}). All your messages, explanations, diagnoses, and suggestions must be in {name}."


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANSLATIONS — organised by module / functional area
# ═══════════════════════════════════════════════════════════════════════════════

# ── Generic / shared ─────────────────────────────────────────────────────────
_add('menu',
     pl='🏠 Menu', en='🏠 Menu', de='🏠 Menü', fr='🏠 Menu',
     es='🏠 Menú', it='🏠 Menu', pt='🏠 Menu', cs='🏠 Menu',
     ro='🏠 Meniu', nl='🏠 Menu')
_add('back',
     pl='← Wróć', en='← Back', de='← Zurück', fr='← Retour',
     es='← Volver', it='← Indietro', pt='← Voltar', cs='← Zpět',
     ro='← Înapoi', nl='← Terug')
_add('save',
     pl='💾 Zapisz', en='💾 Save', de='💾 Speichern', fr='💾 Enregistrer',
     es='💾 Guardar', it='💾 Salva', pt='💾 Guardar', cs='💾 Uložit',
     ro='💾 Salvează', nl='💾 Opslaan')
_add('cancel',
     pl='Anuluj', en='Cancel', de='Abbrechen', fr='Annuler',
     es='Cancelar', it='Annulla', pt='Cancelar', cs='Zrušit',
     ro='Anulează', nl='Annuleren')
_add('retry',
     pl='🔄 Spróbuj ponownie', en='🔄 Retry', de='🔄 Erneut versuchen', fr='🔄 Réessayer',
     es='🔄 Reintentar', it='🔄 Riprova', pt='🔄 Tentar novamente', cs='🔄 Zkusit znovu',
     ro='🔄 Reîncearcă', nl='🔄 Opnieuw proberen')
_add('settings',
     pl='⚙️ Ustawienia (.env)', en='⚙️ Settings (.env)', de='⚙️ Einstellungen (.env)', fr='⚙️ Paramètres (.env)',
     es='⚙️ Ajustes (.env)', it='⚙️ Impostazioni (.env)', pt='⚙️ Definições (.env)', cs='⚙️ Nastavení (.env)',
     ro='⚙️ Setări (.env)', nl='⚙️ Instellingen (.env)')
_add('all_settings',
     pl='⚙️ Wszystkie ustawienia', en='⚙️ All settings', de='⚙️ Alle Einstellungen', fr='⚙️ Tous les paramètres',
     es='⚙️ Todos los ajustes', it='⚙️ Tutte le impostazioni', pt='⚙️ Todas as definições', cs='⚙️ Všechna nastavení',
     ro='⚙️ Toate setările', nl='⚙️ Alle instellingen')
_add('configure',
     pl='⚙️ Konfiguruj', en='⚙️ Configure', de='⚙️ Konfigurieren', fr='⚙️ Configurer',
     es='⚙️ Configurar', it='⚙️ Configura', pt='⚙️ Configurar', cs='⚙️ Konfigurovat',
     ro='⚙️ Configurează', nl='⚙️ Configureren')
_add('save_and_apply',
     pl='💾 Zapisz i zastosuj', en='💾 Save & apply', de='💾 Speichern & anwenden', fr='💾 Enregistrer & appliquer',
     es='💾 Guardar y aplicar', it='💾 Salva e applica', pt='💾 Guardar e aplicar', cs='💾 Uložit a použít',
     ro='💾 Salvează și aplică', nl='💾 Opslaan & toepassen')
_add('open_full_settings',
     pl='📋 Otwórz pełne ustawienia', en='📋 Open full settings', de='📋 Alle Einstellungen öffnen', fr='📋 Ouvrir tous les paramètres',
     es='📋 Abrir todos los ajustes', it='📋 Apri tutte le impostazioni', pt='📋 Abrir todas as definições', cs='📋 Otevřít plná nastavení',
     ro='📋 Deschide setările complete', nl='📋 Alle instellingen openen')
_add('empty_val',
     pl='(puste)', en='(empty)', de='(leer)', fr='(vide)',
     es='(vacío)', it='(vuoto)', pt='(vazio)', cs='(prázdné)',
     ro='(gol)', nl='(leeg)')

# ── Welcome / connect ────────────────────────────────────────────────────────
_add('welcome_title',
     pl='# 👋 Dockfra Setup Wizard', en='# 👋 Dockfra Setup Wizard', de='# 👋 Dockfra Einrichtungsassistent', fr='# 👋 Dockfra Assistant de configuration',
     es='# 👋 Dockfra Asistente de configuración', it='# 👋 Dockfra Procedura guidata', pt='# 👋 Dockfra Assistente de configuração', cs='# 👋 Dockfra Průvodce nastavením',
     ro='# 👋 Dockfra Expert configurare', nl='# 👋 Dockfra Installatiewizard')
_add('docker_unavailable',
     pl='❌ **Docker niedostępny** — {detail}\n\nUruchom Docker i odśwież.',
     en='❌ **Docker unavailable** — {detail}\n\nStart Docker and refresh.',
     de='❌ **Docker nicht verfügbar** — {detail}\n\nStarten Sie Docker und aktualisieren Sie.',
     fr='❌ **Docker indisponible** — {detail}\n\nDémarrez Docker et actualisez.',
     es='❌ **Docker no disponible** — {detail}\n\nInicie Docker y actualice.',
     it='❌ **Docker non disponibile** — {detail}\n\nAvvia Docker e aggiorna.',
     pt='❌ **Docker indisponível** — {detail}\n\nInicie o Docker e atualize.',
     cs='❌ **Docker nedostupný** — {detail}\n\nSpusťte Docker a obnovte.',
     ro='❌ **Docker indisponibil** — {detail}\n\nPorniți Docker și reîmprospătați.',
     nl='❌ **Docker niet beschikbaar** — {detail}\n\nStart Docker en vernieuw.')
_add('check_again',
     pl='🔄 Sprawdź ponownie', en='🔄 Check again', de='🔄 Erneut prüfen', fr='🔄 Vérifier à nouveau',
     es='🔄 Comprobar de nuevo', it='🔄 Controlla di nuovo', pt='🔄 Verificar novamente', cs='🔄 Zkontrolovat znovu',
     ro='🔄 Verifică din nou', nl='🔄 Opnieuw controleren')
_add('fill_missing_n',
     pl='Uzupełnij **{n}** brakujące ustawienia:',
     en='Fill in **{n}** missing settings:',
     de='Ergänzen Sie **{n}** fehlende Einstellungen:',
     fr='Complétez **{n}** paramètres manquants :',
     es='Complete **{n}** ajustes faltantes:',
     it='Compila **{n}** impostazioni mancanti:',
     pt='Preencha **{n}** definições em falta:',
     cs='Doplňte **{n}** chybějících nastavení:',
     ro='Completați **{n}** setări lipsă:',
     nl='Vul **{n}** ontbrekende instellingen in:')
_add('save_and_run',
     pl='✅ Zapisz i uruchom', en='✅ Save & launch', de='✅ Speichern & starten', fr='✅ Enregistrer & lancer',
     es='✅ Guardar y lanzar', it='✅ Salva e avvia', pt='✅ Guardar e lançar', cs='✅ Uložit a spustit',
     ro='✅ Salvează și lansează', nl='✅ Opslaan & starten')
_add('config_complete',
     pl='✅ Konfiguracja kompletna. Co chcesz zrobić?',
     en='✅ Configuration complete. What would you like to do?',
     de='✅ Konfiguration vollständig. Was möchten Sie tun?',
     fr='✅ Configuration terminée. Que souhaitez-vous faire ?',
     es='✅ Configuración completa. ¿Qué desea hacer?',
     it='✅ Configurazione completa. Cosa vuoi fare?',
     pt='✅ Configuração completa. O que deseja fazer?',
     cs='✅ Konfigurace dokončena. Co chcete udělat?',
     ro='✅ Configurare completă. Ce doriți să faceți?',
     nl='✅ Configuratie compleet. Wat wilt u doen?')
_add('launch_infra',
     pl='🚀 Uruchom infrastrukturę', en='🚀 Launch infrastructure', de='🚀 Infrastruktur starten', fr='🚀 Lancer l\'infrastructure',
     es='🚀 Lanzar infraestructura', it='🚀 Avvia infrastruttura', pt='🚀 Lançar infraestrutura', cs='🚀 Spustit infrastrukturu',
     ro='🚀 Lansează infrastructura', nl='🚀 Infrastructuur starten')
_add('deploy_device',
     pl='📦 Wdróż na urządzenie', en='📦 Deploy to device', de='📦 Auf Gerät bereitstellen', fr='📦 Déployer sur l\'appareil',
     es='📦 Desplegar en dispositivo', it='📦 Distribuisci su dispositivo', pt='📦 Implementar no dispositivo', cs='📦 Nasadit na zařízení',
     ro='📦 Implementează pe dispozitiv', nl='📦 Naar apparaat deployen')

# ── Status ───────────────────────────────────────────────────────────────────
_add('no_containers',
     pl='⚠️ Brak uruchomionych kontenerów.',
     en='⚠️ No running containers.',
     de='⚠️ Keine laufenden Container.',
     fr='⚠️ Aucun conteneur en cours d\'exécution.',
     es='⚠️ Sin contenedores en ejecución.',
     it='⚠️ Nessun container in esecuzione.',
     pt='⚠️ Sem contentores em execução.',
     cs='⚠️ Žádné běžící kontejnery.',
     ro='⚠️ Niciun container rulând.',
     nl='⚠️ Geen draaiende containers.')
_add('launch_now',
     pl='🚀 Uruchom teraz', en='🚀 Launch now', de='🚀 Jetzt starten', fr='🚀 Lancer maintenant',
     es='🚀 Lanzar ahora', it='🚀 Avvia ora', pt='🚀 Lançar agora', cs='🚀 Spustit nyní',
     ro='🚀 Lansează acum', nl='🚀 Nu starten')
_add('system_status',
     pl='## 📊 Stan systemu — {ok} ✅ OK · {fail} 🔴 problemów',
     en='## 📊 System status — {ok} ✅ OK · {fail} 🔴 problems',
     de='## 📊 Systemstatus — {ok} ✅ OK · {fail} 🔴 Probleme',
     fr='## 📊 État du système — {ok} ✅ OK · {fail} 🔴 problèmes',
     es='## 📊 Estado del sistema — {ok} ✅ OK · {fail} 🔴 problemas',
     it='## 📊 Stato del sistema — {ok} ✅ OK · {fail} 🔴 problemi',
     pt='## 📊 Estado do sistema — {ok} ✅ OK · {fail} 🔴 problemas',
     cs='## 📊 Stav systému — {ok} ✅ OK · {fail} 🔴 problémů',
     ro='## 📊 Starea sistemului — {ok} ✅ OK · {fail} 🔴 probleme',
     nl='## 📊 Systeemstatus — {ok} ✅ OK · {fail} 🔴 problemen')
_add('problem_analysis',
     pl='### 🔍 Analiza problemów ({n} kontenerów)',
     en='### 🔍 Problem analysis ({n} containers)',
     de='### 🔍 Problemanalyse ({n} Container)',
     fr='### 🔍 Analyse des problèmes ({n} conteneurs)',
     es='### 🔍 Análisis de problemas ({n} contenedores)',
     it='### 🔍 Analisi problemi ({n} container)',
     pt='### 🔍 Análise de problemas ({n} contentores)',
     cs='### 🔍 Analýza problémů ({n} kontejnerů)',
     ro='### 🔍 Analiză probleme ({n} containere)',
     nl='### 🔍 Probleemanalyse ({n} containers)')
_add('env_status_missing',
     pl='⚠️ Brakuje: `{vars}`',
     en='⚠️ Missing: `{vars}`',
     de='⚠️ Fehlend: `{vars}`',
     fr='⚠️ Manquant : `{vars}`',
     es='⚠️ Faltante: `{vars}`',
     it='⚠️ Mancante: `{vars}`',
     pt='⚠️ Em falta: `{vars}`',
     cs='⚠️ Chybí: `{vars}`',
     ro='⚠️ Lipsă: `{vars}`',
     nl='⚠️ Ontbrekend: `{vars}`')
_add('env_status_ok',
     pl='✅ Konfiguracja kompletna',
     en='✅ Configuration complete',
     de='✅ Konfiguration vollständig',
     fr='✅ Configuration terminée',
     es='✅ Configuración completa',
     it='✅ Configurazione completa',
     pt='✅ Configuração completa',
     cs='✅ Konfigurace dokončena',
     ro='✅ Configurare completă',
     nl='✅ Configuratie compleet')

# ── Launch ───────────────────────────────────────────────────────────────────
_add('launching_stacks',
     pl='## 🚀 Uruchamianie stacków', en='## 🚀 Launching stacks', de='## 🚀 Stacks starten', fr='## 🚀 Lancement des stacks',
     es='## 🚀 Lanzando stacks', it='## 🚀 Avvio degli stack', pt='## 🚀 Lançando stacks', cs='## 🚀 Spouštění stacků',
     ro='## 🚀 Lansare stacks', nl='## 🚀 Stacks starten')
_add('stacks_select_label',
     pl='Stacki do uruchomienia', en='Stacks to launch', de='Zu startende Stacks', fr='Stacks à lancer',
     es='Stacks a lanzar', it='Stack da avviare', pt='Stacks a lançar', cs='Stacky ke spuštění',
     ro='Stacks de lansat', nl='Te starten stacks')
_add('environment_label',
     pl='Środowisko', en='Environment', de='Umgebung', fr='Environnement',
     es='Entorno', it='Ambiente', pt='Ambiente', cs='Prostředí',
     ro='Mediu', nl='Omgeving')
_add('run_btn',
     pl='▶️ Uruchom', en='▶️ Launch', de='▶️ Starten', fr='▶️ Lancer',
     es='▶️ Lanzar', it='▶️ Avvia', pt='▶️ Lançar', cs='▶️ Spustit',
     ro='▶️ Lansează', nl='▶️ Starten')
_add('all_stacks_ok',
     pl='## ✅ Wszystkie stacki uruchomione!', en='## ✅ All stacks launched!', de='## ✅ Alle Stacks gestartet!', fr='## ✅ Tous les stacks lancés !',
     es='## ✅ ¡Todos los stacks lanzados!', it='## ✅ Tutti gli stack avviati!', pt='## ✅ Todos os stacks lançados!', cs='## ✅ Všechny stacky spuštěny!',
     ro='## ✅ Toate stack-urile lansate!', nl='## ✅ Alle stacks gestart!')
_add('infra_ready',
     pl='## ✅ Infrastruktura gotowa!', en='## ✅ Infrastructure ready!', de='## ✅ Infrastruktur bereit!', fr='## ✅ Infrastructure prête !',
     es='## ✅ ¡Infraestructura lista!', it='## ✅ Infrastruttura pronta!', pt='## ✅ Infraestrutura pronta!', cs='## ✅ Infrastruktura připravena!',
     ro='## ✅ Infrastructura pregătită!', nl='## ✅ Infrastructuur gereed!')
_add('error_analysis',
     pl='## 🔍 Analiza błędów', en='## 🔍 Error analysis', de='## 🔍 Fehleranalyse', fr='## 🔍 Analyse des erreurs',
     es='## 🔍 Análisis de errores', it='## 🔍 Analisi errori', pt='## 🔍 Análise de erros', cs='## 🔍 Analýza chyb',
     ro='## 🔍 Analiză erori', nl='## 🔍 Foutenanalyse')
_add('what_to_do',
     pl='Co chcesz zrobić?', en='What would you like to do?', de='Was möchten Sie tun?', fr='Que souhaitez-vous faire ?',
     es='¿Qué desea hacer?', it='Cosa vuoi fare?', pt='O que deseja fazer?', cs='Co chcete udělat?',
     ro='Ce doriți să faceți?', nl='Wat wilt u doen?')
_add('health_checking',
     pl='⏳ Sprawdzam zdrowie kontenerów…', en='⏳ Checking container health…', de='⏳ Überprüfe Container-Zustand…', fr='⏳ Vérification de l\'état des conteneurs…',
     es='⏳ Comprobando estado de contenedores…', it='⏳ Controllo salute container…', pt='⏳ Verificando saúde dos contentores…', cs='⏳ Kontroluji stav kontejnerů…',
     ro='⏳ Verificare stare containere…', nl='⏳ Containerstatus controleren…')
_add('containers_problems_post',
     pl='### ⚠️ {n} kontener(ów) ma problemy po starcie:',
     en='### ⚠️ {n} container(s) have problems after start:',
     de='### ⚠️ {n} Container haben Probleme nach dem Start:',
     fr='### ⚠️ {n} conteneur(s) ont des problèmes après le démarrage :',
     es='### ⚠️ {n} contenedor(es) tienen problemas después del inicio:',
     it='### ⚠️ {n} container hanno problemi dopo l\'avvio:',
     pt='### ⚠️ {n} contentor(es) com problemas após o início:',
     cs='### ⚠️ {n} kontejner(ů) má problémy po spuštění:',
     ro='### ⚠️ {n} container(e) au probleme după pornire:',
     nl='### ⚠️ {n} container(s) hebben problemen na het starten:')
_add('fix_container',
     pl='🔧 Napraw {name}', en='🔧 Fix {name}', de='🔧 {name} reparieren', fr='🔧 Réparer {name}',
     es='🔧 Reparar {name}', it='🔧 Ripara {name}', pt='🔧 Corrigir {name}', cs='🔧 Opravit {name}',
     ro='🔧 Repară {name}', nl='🔧 {name} repareren')
_add('skip_continue',
     pl='⏭ Pomiń i kontynuuj', en='⏭ Skip & continue', de='⏭ Überspringen', fr='⏭ Ignorer et continuer',
     es='⏭ Omitir y continuar', it='⏭ Salta e continua', pt='⏭ Pular e continuar', cs='⏭ Přeskočit a pokračovat',
     ro='⏭ Sari și continuă', nl='⏭ Overslaan & doorgaan')

# ── Logs ─────────────────────────────────────────────────────────────────────
_add('pick_container',
     pl='Wybierz kontener:', en='Pick a container:', de='Container auswählen:', fr='Choisir un conteneur :',
     es='Seleccione un contenedor:', it='Scegli un container:', pt='Selecione um contentor:', cs='Vyberte kontejner:',
     ro='Alegeți un container:', nl='Kies een container:')
_add('no_containers_short',
     pl='Brak kontenerów.', en='No containers.', de='Keine Container.', fr='Aucun conteneur.',
     es='Sin contenedores.', it='Nessun container.', pt='Sem contentores.', cs='Žádné kontejnery.',
     ro='Niciun container.', nl='Geen containers.')
_add('logs_title',
     pl='📋 **Logi: `{name}`** (ostatnie {n} linii)',
     en='📋 **Logs: `{name}`** (last {n} lines)',
     de='📋 **Logs: `{name}`** (letzte {n} Zeilen)',
     fr='📋 **Journaux : `{name}`** ({n} dernières lignes)',
     es='📋 **Registros: `{name}`** (últimas {n} líneas)',
     it='📋 **Log: `{name}`** (ultime {n} righe)',
     pt='📋 **Registos: `{name}`** (últimas {n} linhas)',
     cs='📋 **Logy: `{name}`** (posledních {n} řádků)',
     ro='📋 **Jurnale: `{name}`** (ultimele {n} linii)',
     nl='📋 **Logs: `{name}`** (laatste {n} regels)')
_add('refresh',
     pl='🔄 Odśwież', en='🔄 Refresh', de='🔄 Aktualisieren', fr='🔄 Actualiser',
     es='🔄 Actualizar', it='🔄 Aggiorna', pt='🔄 Atualizar', cs='🔄 Obnovit',
     ro='🔄 Reîmprospătează', nl='🔄 Vernieuwen')
_add('other_logs',
     pl='← Inne logi', en='← Other logs', de='← Andere Logs', fr='← Autres journaux',
     es='← Otros registros', it='← Altri log', pt='← Outros registos', cs='← Jiné logy',
     ro='← Alte jurnale', nl='← Andere logs')

# ── Settings ─────────────────────────────────────────────────────────────────
_add('settings_title',
     pl='## ⚙️ Ustawienia — wybierz sekcję',
     en='## ⚙️ Settings — choose section',
     de='## ⚙️ Einstellungen — Abschnitt wählen',
     fr='## ⚙️ Paramètres — choisir la section',
     es='## ⚙️ Ajustes — elegir sección',
     it='## ⚙️ Impostazioni — scegli sezione',
     pt='## ⚙️ Definições — escolher secção',
     cs='## ⚙️ Nastavení — vyberte sekci',
     ro='## ⚙️ Setări — alegeți secțiunea',
     nl='## ⚙️ Instellingen — kies sectie')
_add('saved_to_env',
     pl='✅ **{group}** — zapisano do `dockfra/.env`',
     en='✅ **{group}** — saved to `dockfra/.env`',
     de='✅ **{group}** — in `dockfra/.env` gespeichert',
     fr='✅ **{group}** — enregistré dans `dockfra/.env`',
     es='✅ **{group}** — guardado en `dockfra/.env`',
     it='✅ **{group}** — salvato in `dockfra/.env`',
     pt='✅ **{group}** — guardado em `dockfra/.env`',
     cs='✅ **{group}** — uloženo do `dockfra/.env`',
     ro='✅ **{group}** — salvat în `dockfra/.env`',
     nl='✅ **{group}** — opgeslagen in `dockfra/.env`')
_add('edit_more',
     pl='✏️ Edytuj dalej', en='✏️ Edit more', de='✏️ Weiter bearbeiten', fr='✏️ Modifier encore',
     es='✏️ Editar más', it='✏️ Modifica ancora', pt='✏️ Editar mais', cs='✏️ Upravit dále',
     ro='✏️ Editează mai departe', nl='✏️ Verder bewerken')
_add('all_sections',
     pl='← Wszystkie sekcje', en='← All sections', de='← Alle Abschnitte', fr='← Toutes les sections',
     es='← Todas las secciones', it='← Tutte le sezioni', pt='← Todas as secções', cs='← Všechny sekce',
     ro='← Toate secțiunile', nl='← Alle secties')

# ── Credentials ──────────────────────────────────────────────────────────────
_add('creds_saved',
     pl='✅ Zapisano i zaktualizowano `dockfra/.env`.',
     en='✅ Saved and updated `dockfra/.env`.',
     de='✅ Gespeichert und `dockfra/.env` aktualisiert.',
     fr='✅ Enregistré et mis à jour `dockfra/.env`.',
     es='✅ Guardado y actualizado `dockfra/.env`.',
     it='✅ Salvato e aggiornato `dockfra/.env`.',
     pt='✅ Guardado e atualizado `dockfra/.env`.',
     cs='✅ Uloženo a aktualizováno `dockfra/.env`.',
     ro='✅ Salvat și actualizat `dockfra/.env`.',
     nl='✅ Opgeslagen en `dockfra/.env` bijgewerkt.')
_add('launch_stacks_btn',
     pl='🚀 Uruchom stacki', en='🚀 Launch stacks', de='🚀 Stacks starten', fr='🚀 Lancer les stacks',
     es='🚀 Lanzar stacks', it='🚀 Avvia stack', pt='🚀 Lançar stacks', cs='🚀 Spustit stacky',
     ro='🚀 Lansează stacks', nl='🚀 Stacks starten')

# ── LLM / AI ────────────────────────────────────────────────────────────────
_add('llm_thinking',
     pl='🧠 LLM myśli...', en='🧠 LLM thinking...', de='🧠 LLM denkt...', fr='🧠 LLM réfléchit...',
     es='🧠 LLM pensando...', it='🧠 LLM sta pensando...', pt='🧠 LLM a pensar...', cs='🧠 LLM přemýšlí...',
     ro='🧠 LLM gândește...', nl='🧠 LLM denkt na...')
_add('ai_analyzing',
     pl='🧠 AI analizuje logi...', en='🧠 AI analyzing logs...', de='🧠 AI analysiert Logs...', fr='🧠 AI analyse les journaux...',
     es='🧠 AI analizando registros...', it='🧠 AI analizza i log...', pt='🧠 AI a analisar registos...', cs='🧠 AI analyzuje logy...',
     ro='🧠 AI analizează jurnalele...', nl='🧠 AI analyseert logs...')
_add('ai_analysis_title',
     pl='### 🧠 Analiza AI: `{name}`', en='### 🧠 AI Analysis: `{name}`', de='### 🧠 AI-Analyse: `{name}`', fr='### 🧠 Analyse IA : `{name}`',
     es='### 🧠 Análisis IA: `{name}`', it='### 🧠 Analisi AI: `{name}`', pt='### 🧠 Análise IA: `{name}`', cs='### 🧠 Analýza AI: `{name}`',
     ro='### 🧠 Analiză AI: `{name}`', nl='### 🧠 AI-analyse: `{name}`')
_add('suggest_commands',
     pl='💡 Zaproponuj komendy', en='💡 Suggest commands', de='💡 Befehle vorschlagen', fr='💡 Suggérer des commandes',
     es='💡 Sugerir comandos', it='💡 Suggerisci comandi', pt='💡 Sugerir comandos', cs='💡 Navrhnout příkazy',
     ro='💡 Sugerează comenzi', nl='💡 Commando\'s voorstellen')
_add('cannot_get_logs',
     pl='❌ Nie można pobrać logów: {err}', en='❌ Cannot fetch logs: {err}', de='❌ Logs können nicht abgerufen werden: {err}',
     fr='❌ Impossible de récupérer les journaux : {err}', es='❌ No se pueden obtener los registros: {err}',
     it='❌ Impossibile ottenere i log: {err}', pt='❌ Não é possível obter registos: {err}',
     cs='❌ Nelze získat logy: {err}', ro='❌ Nu se pot obține jurnalele: {err}', nl='❌ Kan logs niet ophalen: {err}')
_add('llm_unavailable',
     pl='⚠️ **LLM niedostępny** — {reason}\n\nSkonfiguruj poprawny `OPENROUTER_API_KEY` poniżej:',
     en='⚠️ **LLM unavailable** — {reason}\n\nConfigure a valid `OPENROUTER_API_KEY` below:',
     de='⚠️ **LLM nicht verfügbar** — {reason}\n\nKonfigurieren Sie einen gültigen `OPENROUTER_API_KEY`:',
     fr='⚠️ **LLM indisponible** — {reason}\n\nConfigurez une clé `OPENROUTER_API_KEY` valide ci-dessous :',
     es='⚠️ **LLM no disponible** — {reason}\n\nConfigure una clave `OPENROUTER_API_KEY` válida abajo:',
     it='⚠️ **LLM non disponibile** — {reason}\n\nConfigura una `OPENROUTER_API_KEY` valida qui sotto:',
     pt='⚠️ **LLM indisponível** — {reason}\n\nConfigure uma `OPENROUTER_API_KEY` válida abaixo:',
     cs='⚠️ **LLM nedostupný** — {reason}\n\nKonfigurujte platný `OPENROUTER_API_KEY` níže:',
     ro='⚠️ **LLM indisponibil** — {reason}\n\nConfigurați un `OPENROUTER_API_KEY` valid mai jos:',
     nl='⚠️ **LLM niet beschikbaar** — {reason}\n\nConfigureer een geldige `OPENROUTER_API_KEY` hieronder:')
_add('missing_api_key',
     pl='⚠️ **Brakuje klucza API** — skonfiguruj `OPENROUTER_API_KEY` poniżej:',
     en='⚠️ **Missing API key** — configure `OPENROUTER_API_KEY` below:',
     de='⚠️ **API-Schlüssel fehlt** — konfigurieren Sie `OPENROUTER_API_KEY`:',
     fr='⚠️ **Clé API manquante** — configurez `OPENROUTER_API_KEY` ci-dessous :',
     es='⚠️ **Falta clave API** — configure `OPENROUTER_API_KEY` abajo:',
     it='⚠️ **Chiave API mancante** — configura `OPENROUTER_API_KEY` qui sotto:',
     pt='⚠️ **Chave API em falta** — configure `OPENROUTER_API_KEY` abaixo:',
     cs='⚠️ **Chybí API klíč** — konfigurujte `OPENROUTER_API_KEY` níže:',
     ro='⚠️ **Cheie API lipsă** — configurați `OPENROUTER_API_KEY` mai jos:',
     nl='⚠️ **API-sleutel ontbreekt** — configureer `OPENROUTER_API_KEY` hieronder:')
_add('test_connection',
     pl='🧪 Testuj połączenie', en='🧪 Test connection', de='🧪 Verbindung testen', fr='🧪 Tester la connexion',
     es='🧪 Probar conexión', it='🧪 Testa connessione', pt='🧪 Testar ligação', cs='🧪 Otestovat spojení',
     ro='🧪 Testează conexiunea', nl='🧪 Verbinding testen')
_add('save_continue',
     pl='✅ Zapisz i kontynuuj', en='✅ Save & continue', de='✅ Speichern & weiter', fr='✅ Enregistrer & continuer',
     es='✅ Guardar y continuar', it='✅ Salva e continua', pt='✅ Guardar e continuar', cs='✅ Uložit a pokračovat',
     ro='✅ Salvează și continuă', nl='✅ Opslaan & doorgaan')
_add('repeat_action',
     pl='▶️ Powtórz akcję', en='▶️ Repeat action', de='▶️ Aktion wiederholen', fr='▶️ Répéter l\'action',
     es='▶️ Repetir acción', it='▶️ Ripeti azione', pt='▶️ Repetir ação', cs='▶️ Opakovat akci',
     ro='▶️ Repetă acțiunea', nl='▶️ Actie herhalen')
_add('connection_ok',
     pl='✅ **Połączenie OK!**', en='✅ **Connection OK!**', de='✅ **Verbindung OK!**', fr='✅ **Connexion OK !**',
     es='✅ **¡Conexión OK!**', it='✅ **Connessione OK!**', pt='✅ **Ligação OK!**', cs='✅ **Spojení OK!**',
     ro='✅ **Conexiune OK!**', nl='✅ **Verbinding OK!**')
_add('key_saved',
     pl='💾 Klucz i model zapisane.', en='💾 Key and model saved.', de='💾 Schlüssel und Modell gespeichert.', fr='💾 Clé et modèle enregistrés.',
     es='💾 Clave y modelo guardados.', it='💾 Chiave e modello salvati.', pt='💾 Chave e modelo guardados.', cs='💾 Klíč a model uloženy.',
     ro='💾 Cheie și model salvate.', nl='💾 Sleutel en model opgeslagen.')
_add('invalid_api_key',
     pl='❌ **Nieprawidłowy klucz API** (401 Unauthorized)',
     en='❌ **Invalid API key** (401 Unauthorized)',
     de='❌ **Ungültiger API-Schlüssel** (401 Unauthorized)',
     fr='❌ **Clé API invalide** (401 Unauthorized)',
     es='❌ **Clave API inválida** (401 Unauthorized)',
     it='❌ **Chiave API non valida** (401 Unauthorized)',
     pt='❌ **Chave API inválida** (401 Unauthorized)',
     cs='❌ **Neplatný API klíč** (401 Unauthorized)',
     ro='❌ **Cheie API invalidă** (401 Unauthorized)',
     nl='❌ **Ongeldige API-sleutel** (401 Unauthorized)')
_add('no_funds',
     pl='❌ **Brak środków** na koncie OpenRouter (402)',
     en='❌ **No funds** on OpenRouter account (402)',
     de='❌ **Kein Guthaben** auf OpenRouter-Konto (402)',
     fr='❌ **Pas de fonds** sur le compte OpenRouter (402)',
     es='❌ **Sin fondos** en la cuenta OpenRouter (402)',
     it='❌ **Nessun fondo** sull\'account OpenRouter (402)',
     pt='❌ **Sem fundos** na conta OpenRouter (402)',
     cs='❌ **Žádné prostředky** na účtu OpenRouter (402)',
     ro='❌ **Fără fonduri** în contul OpenRouter (402)',
     nl='❌ **Geen tegoed** op OpenRouter-account (402)')

# ── Tickets ──────────────────────────────────────────────────────────────────
_add('create_ticket',
     pl='📝 Utwórz ticket', en='📝 Create ticket', de='📝 Ticket erstellen', fr='📝 Créer un ticket',
     es='📝 Crear ticket', it='📝 Crea ticket', pt='📝 Criar ticket', cs='📝 Vytvořit ticket',
     ro='📝 Creează ticket', nl='📝 Ticket aanmaken')
_add('create_ticket_title',
     pl='## 📝 Utwórz nowy ticket', en='## 📝 Create new ticket', de='## 📝 Neues Ticket erstellen', fr='## 📝 Créer un nouveau ticket',
     es='## 📝 Crear nuevo ticket', it='## 📝 Crea nuovo ticket', pt='## 📝 Criar novo ticket', cs='## 📝 Vytvořit nový ticket',
     ro='## 📝 Creează ticket nou', nl='## 📝 Nieuw ticket aanmaken')
_add('ticket_title_label',
     pl='Tytuł ticketu', en='Ticket title', de='Ticket-Titel', fr='Titre du ticket',
     es='Título del ticket', it='Titolo del ticket', pt='Título do ticket', cs='Název ticketu',
     ro='Titlu ticket', nl='Tickettitel')
_add('ticket_desc_label',
     pl='Opis (opcjonalny)', en='Description (optional)', de='Beschreibung (optional)', fr='Description (optionnelle)',
     es='Descripción (opcional)', it='Descrizione (opzionale)', pt='Descrição (opcional)', cs='Popis (volitelný)',
     ro='Descriere (opțională)', nl='Beschrijving (optioneel)')
_add('priority_label',
     pl='Priorytet', en='Priority', de='Priorität', fr='Priorité',
     es='Prioridad', it='Priorità', pt='Prioridade', cs='Priorita',
     ro='Prioritate', nl='Prioriteit')
_add('assign_to',
     pl='Przydziel do', en='Assign to', de='Zuweisen an', fr='Assigner à',
     es='Asignar a', it='Assegna a', pt='Atribuir a', cs='Přiřadit k',
     ro='Atribuie la', nl='Toewijzen aan')
_add('ticket_title_required',
     pl='❌ Tytuł ticketu jest wymagany.', en='❌ Ticket title is required.', de='❌ Ticket-Titel ist erforderlich.', fr='❌ Le titre du ticket est requis.',
     es='❌ El título del ticket es obligatorio.', it='❌ Il titolo del ticket è obbligatorio.', pt='❌ O título do ticket é obrigatório.', cs='❌ Název ticketu je povinný.',
     ro='❌ Titlul ticketului este obligatoriu.', nl='❌ Tickettitel is verplicht.')
_add('ticket_created',
     pl='## ✅ Ticket utworzony!', en='## ✅ Ticket created!', de='## ✅ Ticket erstellt!', fr='## ✅ Ticket créé !',
     es='## ✅ ¡Ticket creado!', it='## ✅ Ticket creato!', pt='## ✅ Ticket criado!', cs='## ✅ Ticket vytvořen!',
     ro='## ✅ Ticket creat!', nl='## ✅ Ticket aangemaakt!')
_add('create_another',
     pl='📝 Utwórz kolejny', en='📝 Create another', de='📝 Weiteres erstellen', fr='📝 Créer un autre',
     es='📝 Crear otro', it='📝 Crea un altro', pt='📝 Criar outro', cs='📝 Vytvořit další',
     ro='📝 Creează altul', nl='📝 Nog een aanmaken')
_add('ticket_list',
     pl='📋 Lista ticketów', en='📋 Ticket list', de='📋 Ticketliste', fr='📋 Liste des tickets',
     es='📋 Lista de tickets', it='📋 Lista ticket', pt='📋 Lista de tickets', cs='📋 Seznam ticketů',
     ro='📋 Lista ticketelor', nl='📋 Ticketlijst')
_add('sync_services',
     pl='🔗 Sync do GitHub/Jira', en='🔗 Sync to GitHub/Jira', de='🔗 Sync zu GitHub/Jira', fr='🔗 Sync vers GitHub/Jira',
     es='🔗 Sincronizar con GitHub/Jira', it='🔗 Sincronizza con GitHub/Jira', pt='🔗 Sincronizar com GitHub/Jira', cs='🔗 Synchronizovat s GitHub/Jira',
     ro='🔗 Sincronizare cu GitHub/Jira', nl='🔗 Sync naar GitHub/Jira')
_add('ticket_not_found',
     pl='❌ Ticket `{tid}` nie znaleziony.', en='❌ Ticket `{tid}` not found.', de='❌ Ticket `{tid}` nicht gefunden.', fr='❌ Ticket `{tid}` introuvable.',
     es='❌ Ticket `{tid}` no encontrado.', it='❌ Ticket `{tid}` non trovato.', pt='❌ Ticket `{tid}` não encontrado.', cs='❌ Ticket `{tid}` nenalezen.',
     ro='❌ Ticketul `{tid}` nu a fost găsit.', nl='❌ Ticket `{tid}` niet gevonden.')
_add('no_tickets',
     pl='Brak ticketów.', en='No tickets.', de='Keine Tickets.', fr='Aucun ticket.',
     es='Sin tickets.', it='Nessun ticket.', pt='Sem tickets.', cs='Žádné tickety.',
     ro='Niciun ticket.', nl='Geen tickets.')
_add('comments_title',
     pl='### 💬 Komentarze', en='### 💬 Comments', de='### 💬 Kommentare', fr='### 💬 Commentaires',
     es='### 💬 Comentarios', it='### 💬 Commenti', pt='### 💬 Comentários', cs='### 💬 Komentáře',
     ro='### 💬 Comentarii', nl='### 💬 Opmerkingen')
_add('review_panel',
     pl='📋 Wszystkie tickety do review', en='📋 All tickets for review', de='📋 Alle Tickets zum Review', fr='📋 Tous les tickets à revoir',
     es='📋 Todos los tickets para revisión', it='📋 Tutti i ticket per la revisione', pt='📋 Todos os tickets para revisão', cs='📋 Všechny tickety k recenzi',
     ro='📋 Toate ticketele pentru review', nl='📋 Alle tickets voor review')

# ── Fixes ────────────────────────────────────────────────────────────────────
_add('fixing_container',
     pl='## 🔧 Naprawianie: `{name}` (próba #{n})',
     en='## 🔧 Fixing: `{name}` (attempt #{n})',
     de='## 🔧 Reparatur: `{name}` (Versuch #{n})',
     fr='## 🔧 Réparation : `{name}` (tentative #{n})',
     es='## 🔧 Reparando: `{name}` (intento #{n})',
     it='## 🔧 Riparazione: `{name}` (tentativo #{n})',
     pt='## 🔧 Corrigindo: `{name}` (tentativa #{n})',
     cs='## 🔧 Oprava: `{name}` (pokus #{n})',
     ro='## 🔧 Reparare: `{name}` (încercare #{n})',
     nl='## 🔧 Repareren: `{name}` (poging #{n})')
_add('status_label',
     pl='**Stan:** {status}', en='**Status:** {status}', de='**Status:** {status}', fr='**État :** {status}',
     es='**Estado:** {status}', it='**Stato:** {status}', pt='**Estado:** {status}', cs='**Stav:** {status}',
     ro='**Stare:** {status}', nl='**Status:** {status}')
_add('repeat_attempt',
     pl='⚠️ To już **{n}. próba** naprawy tego kontenera. Uruchamiam analizę AI...',
     en='⚠️ This is attempt **#{n}** to fix this container. Starting AI analysis...',
     de='⚠️ Dies ist Versuch **#{n}** diesen Container zu reparieren. AI-Analyse wird gestartet...',
     fr='⚠️ C\'est la tentative **#{n}** de réparation. Analyse IA en cours...',
     es='⚠️ Este es el intento **#{n}** de reparación. Iniciando análisis IA...',
     it='⚠️ Questo è il tentativo **#{n}** di riparazione. Analisi AI in corso...',
     pt='⚠️ Esta é a tentativa **#{n}** de correção. Iniciando análise IA...',
     cs='⚠️ Toto je **{n}. pokus** o opravu. Spouštím analýzu AI...',
     ro='⚠️ Aceasta este încercarea **#{n}** de reparare. Se pornește analiza AI...',
     nl='⚠️ Dit is poging **#{n}** om te repareren. AI-analyse wordt gestart...')
_add('ai_analyzing_problem',
     pl='🧠 AI analizuje problem...', en='🧠 AI analyzing problem...', de='🧠 AI analysiert Problem...', fr='🧠 AI analyse le problème...',
     es='🧠 AI analizando problema...', it='🧠 AI analizza il problema...', pt='🧠 AI a analisar problema...', cs='🧠 AI analyzuje problém...',
     ro='🧠 AI analizează problema...', nl='🧠 AI analyseert probleem...')
_add('restart_container',
     pl='🔄 Restart kontenera', en='🔄 Restart container', de='🔄 Container neustarten', fr='🔄 Redémarrer le conteneur',
     es='🔄 Reiniciar contenedor', it='🔄 Riavvia container', pt='🔄 Reiniciar contentor', cs='🔄 Restartovat kontejner',
     ro='🔄 Repornește containerul', nl='🔄 Container herstarten')
_add('analyze_ai',
     pl='🧠 Analizuj z AI', en='🧠 Analyze with AI', de='🧠 Mit AI analysieren', fr='🧠 Analyser avec AI',
     es='🧠 Analizar con IA', it='🧠 Analizza con AI', pt='🧠 Analisar com IA', cs='🧠 Analyzovat s AI',
     ro='🧠 Analizează cu AI', nl='🧠 Analyseren met AI')
_add('cmd_executed',
     pl='✅ Komenda wykonana.', en='✅ Command executed.', de='✅ Befehl ausgeführt.', fr='✅ Commande exécutée.',
     es='✅ Comando ejecutado.', it='✅ Comando eseguito.', pt='✅ Comando executado.', cs='✅ Příkaz proveden.',
     ro='✅ Comandă executată.', nl='✅ Commando uitgevoerd.')
_add('cmd_not_allowed',
     pl='⛔ Komenda `{cmd}` nie jest dozwolona (tylko docker/*)',
     en='⛔ Command `{cmd}` is not allowed (docker/* only)',
     de='⛔ Befehl `{cmd}` ist nicht erlaubt (nur docker/*)',
     fr='⛔ La commande `{cmd}` n\'est pas autorisée (docker/* uniquement)',
     es='⛔ El comando `{cmd}` no está permitido (solo docker/*)',
     it='⛔ Il comando `{cmd}` non è consentito (solo docker/*)',
     pt='⛔ O comando `{cmd}` não é permitido (apenas docker/*)',
     cs='⛔ Příkaz `{cmd}` není povolen (pouze docker/*)',
     ro='⛔ Comanda `{cmd}` nu este permisă (doar docker/*)',
     nl='⛔ Commando `{cmd}` is niet toegestaan (alleen docker/*)')
_add('no_commands',
     pl='⚠️ Brak konkretnych komend — spróbuj pełnej analizy AI.',
     en='⚠️ No specific commands — try full AI analysis.',
     de='⚠️ Keine spezifischen Befehle — versuchen Sie die vollständige AI-Analyse.',
     fr='⚠️ Aucune commande spécifique — essayez l\'analyse AI complète.',
     es='⚠️ Sin comandos específicos — intente el análisis IA completo.',
     it='⚠️ Nessun comando specifico — prova l\'analisi AI completa.',
     pt='⚠️ Sem comandos específicos — tente a análise IA completa.',
     cs='⚠️ Žádné konkrétní příkazy — zkuste plnou analýzu AI.',
     ro='⚠️ Fără comenzi specifice — încercați analiza AI completă.',
     nl='⚠️ Geen specifieke commando\'s — probeer volledige AI-analyse.')
_add('docker_perms_title',
     pl='## 🔧 Naprawa uprawnień Docker',
     en='## 🔧 Fix Docker permissions',
     de='## 🔧 Docker-Berechtigungen reparieren',
     fr='## 🔧 Réparer les permissions Docker',
     es='## 🔧 Reparar permisos de Docker',
     it='## 🔧 Riparare i permessi Docker',
     pt='## 🔧 Corrigir permissões Docker',
     cs='## 🔧 Oprava oprávnění Docker',
     ro='## 🔧 Reparare permisiuni Docker',
     nl='## 🔧 Docker-rechten repareren')

# ── Deploy ───────────────────────────────────────────────────────────────────
_add('deploy_title',
     pl='## 📦 Wdrożenie na urządzenie', en='## 📦 Deploy to device', de='## 📦 Auf Gerät bereitstellen', fr='## 📦 Déployer sur l\'appareil',
     es='## 📦 Desplegar en dispositivo', it='## 📦 Distribuisci su dispositivo', pt='## 📦 Implementar no dispositivo', cs='## 📦 Nasazení na zařízení',
     ro='## 📦 Implementare pe dispozitiv', nl='## 📦 Naar apparaat deployen')
_add('device_ip_label',
     pl='IP urządzenia', en='Device IP', de='Geräte-IP', fr='IP de l\'appareil',
     es='IP del dispositivo', it='IP del dispositivo', pt='IP do dispositivo', cs='IP zařízení',
     ro='IP dispozitiv', nl='Apparaat-IP')
_add('ssh_user_label',
     pl='Użytkownik SSH', en='SSH user', de='SSH-Benutzer', fr='Utilisateur SSH',
     es='Usuario SSH', it='Utente SSH', pt='Utilizador SSH', cs='SSH uživatel',
     ro='Utilizator SSH', nl='SSH-gebruiker')
_add('ssh_port_label',
     pl='Port SSH', en='SSH port', de='SSH-Port', fr='Port SSH',
     es='Puerto SSH', it='Porta SSH', pt='Porta SSH', cs='SSH port',
     ro='Port SSH', nl='SSH-poort')
_add('test_connection_btn',
     pl='🔍 Testuj połączenie', en='🔍 Test connection', de='🔍 Verbindung testen', fr='🔍 Tester la connexion',
     es='🔍 Probar conexión', it='🔍 Testa connessione', pt='🔍 Testar ligação', cs='🔍 Otestovat připojení',
     ro='🔍 Testează conexiunea', nl='🔍 Verbinding testen')
_add('deploy_btn',
     pl='🚀 Wdróż', en='🚀 Deploy', de='🚀 Bereitstellen', fr='🚀 Déployer',
     es='🚀 Desplegar', it='🚀 Distribuisci', pt='🚀 Implementar', cs='🚀 Nasadit',
     ro='🚀 Implementează', nl='🚀 Deployen')
_add('provide_ip',
     pl='❌ Podaj IP!', en='❌ Provide IP!', de='❌ IP eingeben!', fr='❌ Fournissez l\'IP !',
     es='❌ ¡Proporcione la IP!', it='❌ Inserire l\'IP!', pt='❌ Forneça o IP!', cs='❌ Zadejte IP!',
     ro='❌ Introduceți IP-ul!', nl='❌ Voer IP in!')
_add('connection_works',
     pl='✅ Połączenie działa!', en='✅ Connection works!', de='✅ Verbindung funktioniert!', fr='✅ Connexion réussie !',
     es='✅ ¡Conexión exitosa!', it='✅ Connessione riuscita!', pt='✅ Ligação funciona!', cs='✅ Spojení funguje!',
     ro='✅ Conexiunea funcționează!', nl='✅ Verbinding werkt!')
_add('no_connection',
     pl='❌ Brak połączenia z `{host}:{port}`', en='❌ No connection to `{host}:{port}`', de='❌ Keine Verbindung zu `{host}:{port}`',
     fr='❌ Pas de connexion à `{host}:{port}`', es='❌ Sin conexión con `{host}:{port}`',
     it='❌ Nessuna connessione a `{host}:{port}`', pt='❌ Sem ligação a `{host}:{port}`',
     cs='❌ Žádné spojení s `{host}:{port}`', ro='❌ Fără conexiune la `{host}:{port}`', nl='❌ Geen verbinding met `{host}:{port}`')
_add('deploy_now',
     pl='🚀 Wdróż teraz', en='🚀 Deploy now', de='🚀 Jetzt bereitstellen', fr='🚀 Déployer maintenant',
     es='🚀 Desplegar ahora', it='🚀 Distribuisci ora', pt='🚀 Implementar agora', cs='🚀 Nasadit nyní',
     ro='🚀 Implementează acum', nl='🚀 Nu deployen')
_add('change_btn',
     pl='← Zmień', en='← Change', de='← Ändern', fr='← Modifier',
     es='← Cambiar', it='← Cambia', pt='← Alterar', cs='← Změnit',
     ro='← Schimbă', nl='← Wijzigen')

# ── Integrations ─────────────────────────────────────────────────────────────
_add('integrations_title',
     pl='## 🔗 Integracje z systemami zadań', en='## 🔗 Task system integrations', de='## 🔗 Aufgabensystem-Integrationen',
     fr='## 🔗 Intégrations des systèmes de tâches', es='## 🔗 Integraciones de sistemas de tareas',
     it='## 🔗 Integrazioni sistemi di task', pt='## 🔗 Integrações de sistemas de tarefas',
     cs='## 🔗 Integrace se systémy úkolů', ro='## 🔗 Integrări cu sisteme de sarcini', nl='## 🔗 Taaksysteem-integraties')
_add('integrations_desc',
     pl='Skonfiguruj połączenia z zewnętrznymi systemami zarządzania zadaniami.\nTickety będą synchronizowane automatycznie.',
     en='Configure connections to external task management systems.\nTickets will be synced automatically.',
     de='Konfigurieren Sie Verbindungen zu externen Aufgabenverwaltungssystemen.\nTickets werden automatisch synchronisiert.',
     fr='Configurez les connexions aux systèmes de gestion de tâches externes.\nLes tickets seront synchronisés automatiquement.',
     es='Configure conexiones a sistemas externos de gestión de tareas.\nLos tickets se sincronizarán automáticamente.',
     it='Configura le connessioni ai sistemi esterni di gestione attività.\nI ticket saranno sincronizzati automaticamente.',
     pt='Configure ligações a sistemas externos de gestão de tarefas.\nOs tickets serão sincronizados automaticamente.',
     cs='Konfigurujte připojení k externím systémům pro správu úkolů.\nTickety budou synchronizovány automaticky.',
     ro='Configurați conexiunile la sistemele externe de gestionare a sarcinilor.\nTicketele vor fi sincronizate automat.',
     nl='Configureer verbindingen met externe taakbeheersystemen.\nTickets worden automatisch gesynchroniseerd.')
_add('save_integrations',
     pl='💾 Zapisz integracje', en='💾 Save integrations', de='💾 Integrationen speichern', fr='💾 Enregistrer les intégrations',
     es='💾 Guardar integraciones', it='💾 Salva integrazioni', pt='💾 Guardar integrações', cs='💾 Uložit integrace',
     ro='💾 Salvează integrările', nl='💾 Integraties opslaan')
_add('sync_now',
     pl='🔄 Synchronizuj teraz', en='🔄 Sync now', de='🔄 Jetzt synchronisieren', fr='🔄 Synchroniser maintenant',
     es='🔄 Sincronizar ahora', it='🔄 Sincronizza ora', pt='🔄 Sincronizar agora', cs='🔄 Synchronizovat nyní',
     ro='🔄 Sincronizează acum', nl='🔄 Nu synchroniseren')
_add('no_data_to_save',
     pl='⚠️ Brak danych do zapisania.', en='⚠️ No data to save.', de='⚠️ Keine Daten zum Speichern.', fr='⚠️ Aucune donnée à enregistrer.',
     es='⚠️ Sin datos para guardar.', it='⚠️ Nessun dato da salvare.', pt='⚠️ Sem dados para guardar.', cs='⚠️ Žádná data k uložení.',
     ro='⚠️ Niciun dat de salvat.', nl='⚠️ Geen gegevens om op te slaan.')
_add('integrations_saved',
     pl='## ✅ Integracje zapisane', en='## ✅ Integrations saved', de='## ✅ Integrationen gespeichert', fr='## ✅ Intégrations enregistrées',
     es='## ✅ Integraciones guardadas', it='## ✅ Integrazioni salvate', pt='## ✅ Integrações guardadas', cs='## ✅ Integrace uloženy',
     ro='## ✅ Integrări salvate', nl='## ✅ Integraties opgeslagen')
_add('edit_integrations',
     pl='🔗 Edytuj integracje', en='🔗 Edit integrations', de='🔗 Integrationen bearbeiten', fr='🔗 Modifier les intégrations',
     es='🔗 Editar integraciones', it='🔗 Modifica integrazioni', pt='🔗 Editar integrações', cs='🔗 Upravit integrace',
     ro='🔗 Editează integrările', nl='🔗 Integraties bewerken')
_add('configure_integrations',
     pl='🔗 Konfiguruj integracje', en='🔗 Configure integrations', de='🔗 Integrationen konfigurieren', fr='🔗 Configurer les intégrations',
     es='🔗 Configurar integraciones', it='🔗 Configura integrazioni', pt='🔗 Configurar integrações', cs='🔗 Konfigurovat integrace',
     ro='🔗 Configurează integrările', nl='🔗 Integraties configureren')

# ── Sync ─────────────────────────────────────────────────────────────────────
_add('syncing_tickets',
     pl='🔄 Synchronizuję tickety z zewnętrznymi usługami...',
     en='🔄 Syncing tickets with external services...',
     de='🔄 Synchronisiere Tickets mit externen Diensten...',
     fr='🔄 Synchronisation des tickets avec les services externes...',
     es='🔄 Sincronizando tickets con servicios externos...',
     it='🔄 Sincronizzazione ticket con servizi esterni...',
     pt='🔄 Sincronizando tickets com serviços externos...',
     cs='🔄 Synchronizuji tickety s externími službami...',
     ro='🔄 Sincronizare tickete cu servicii externe...',
     nl='🔄 Tickets synchroniseren met externe diensten...')
_add('sync_results',
     pl='## 🔄 Wyniki synchronizacji', en='## 🔄 Sync results', de='## 🔄 Synchronisierungsergebnisse', fr='## 🔄 Résultats de la synchronisation',
     es='## 🔄 Resultados de sincronización', it='## 🔄 Risultati sincronizzazione', pt='## 🔄 Resultados da sincronização', cs='## 🔄 Výsledky synchronizace',
     ro='## 🔄 Rezultate sincronizare', nl='## 🔄 Synchronisatieresultaten')
_add('sync_pulled',
     pl='✅ **{svc}** — pobrano {n} nowych ticketów',
     en='✅ **{svc}** — pulled {n} new tickets',
     de='✅ **{svc}** — {n} neue Tickets abgerufen',
     fr='✅ **{svc}** — {n} nouveaux tickets récupérés',
     es='✅ **{svc}** — {n} nuevos tickets obtenidos',
     it='✅ **{svc}** — {n} nuovi ticket scaricati',
     pt='✅ **{svc}** — {n} novos tickets obtidos',
     cs='✅ **{svc}** — staženo {n} nových ticketů',
     ro='✅ **{svc}** — {n} tickete noi preluate',
     nl='✅ **{svc}** — {n} nieuwe tickets opgehaald')
_add('no_integrations_configured',
     pl='⚠️ Brak skonfigurowanych integracji. Kliknij **🔗 Konfiguruj integracje** aby dodać.',
     en='⚠️ No integrations configured. Click **🔗 Configure integrations** to add.',
     de='⚠️ Keine Integrationen konfiguriert. Klicken Sie auf **🔗 Integrationen konfigurieren**.',
     fr='⚠️ Aucune intégration configurée. Cliquez sur **🔗 Configurer les intégrations**.',
     es='⚠️ Sin integraciones configuradas. Haga clic en **🔗 Configurar integraciones**.',
     it='⚠️ Nessuna integrazione configurata. Fai clic su **🔗 Configura integrazioni**.',
     pt='⚠️ Sem integrações configuradas. Clique em **🔗 Configurar integrações**.',
     cs='⚠️ Žádné integrace nejsou konfigurovány. Klikněte na **🔗 Konfigurovat integrace**.',
     ro='⚠️ Nicio integrare configurată. Faceți clic pe **🔗 Configurează integrările**.',
     nl='⚠️ Geen integraties geconfigureerd. Klik op **🔗 Integraties configureren**.')

# ── Stats ────────────────────────────────────────────────────────────────────
_add('project_stats',
     pl='📊 Statystyki projektu', en='📊 Project stats', de='📊 Projektstatistik', fr='📊 Statistiques du projet',
     es='📊 Estadísticas del proyecto', it='📊 Statistiche progetto', pt='📊 Estatísticas do projeto', cs='📊 Statistiky projektu',
     ro='📊 Statistici proiect', nl='📊 Projectstatistieken')
_add('project_stats_title',
     pl='## 📊 Statystyki projektu', en='## 📊 Project statistics', de='## 📊 Projektstatistik', fr='## 📊 Statistiques du projet',
     es='## 📊 Estadísticas del proyecto', it='## 📊 Statistiche del progetto', pt='## 📊 Estatísticas do projeto', cs='## 📊 Statistiky projektu',
     ro='## 📊 Statistici proiect', nl='## 📊 Projectstatistieken')
_add('total_tickets',
     pl='**Razem:** {n} ticketów', en='**Total:** {n} tickets', de='**Gesamt:** {n} Tickets', fr='**Total :** {n} tickets',
     es='**Total:** {n} tickets', it='**Totale:** {n} ticket', pt='**Total:** {n} tickets', cs='**Celkem:** {n} ticketů',
     ro='**Total:** {n} tickete', nl='**Totaal:** {n} tickets')
_add('containers_section',
     pl='### 🐳 Kontenery', en='### 🐳 Containers', de='### 🐳 Container', fr='### 🐳 Conteneurs',
     es='### 🐳 Contenedores', it='### 🐳 Container', pt='### 🐳 Contentores', cs='### 🐳 Kontejnery',
     ro='### 🐳 Containere', nl='### 🐳 Containers')
_add('git_section',
     pl='### 📂 Git', en='### 📂 Git', de='### 📂 Git', fr='### 📂 Git',
     es='### 📂 Git', it='### 📂 Git', pt='### 📂 Git', cs='### 📂 Git',
     ro='### 📂 Git', nl='### 📂 Git')
_add('branch_label',
     pl='**Gałąź:** `{branch}` | **Commity dziś:** {n}',
     en='**Branch:** `{branch}` | **Commits today:** {n}',
     de='**Branch:** `{branch}` | **Commits heute:** {n}',
     fr='**Branche :** `{branch}` | **Commits aujourd\'hui :** {n}',
     es='**Rama:** `{branch}` | **Commits hoy:** {n}',
     it='**Branch:** `{branch}` | **Commit oggi:** {n}',
     pt='**Branch:** `{branch}` | **Commits hoje:** {n}',
     cs='**Větev:** `{branch}` | **Commity dnes:** {n}',
     ro='**Branch:** `{branch}` | **Commituri azi:** {n}',
     nl='**Branch:** `{branch}` | **Commits vandaag:** {n}')
_add('no_git',
     pl='### 📂 Git\n⚠️ Brak repozytorium git lub błąd odczytu.',
     en='### 📂 Git\n⚠️ No git repository found or read error.',
     de='### 📂 Git\n⚠️ Kein Git-Repository gefunden oder Lesefehler.',
     fr='### 📂 Git\n⚠️ Aucun dépôt git trouvé ou erreur de lecture.',
     es='### 📂 Git\n⚠️ No se encontró repositorio git o error de lectura.',
     it='### 📂 Git\n⚠️ Nessun repository git trovato o errore di lettura.',
     pt='### 📂 Git\n⚠️ Nenhum repositório git encontrado ou erro de leitura.',
     cs='### 📂 Git\n⚠️ Žádný git repozitář nebyl nalezen nebo chyba čtení.',
     ro='### 📂 Git\n⚠️ Niciun depozit git găsit sau eroare de citire.',
     nl='### 📂 Git\n⚠️ Geen git-repository gevonden of leesfout.')

# ── Engines ──────────────────────────────────────────────────────────────────
_add('engines_title',
     pl='## 🔧 Silniki deweloperskie — wybierz narzędzie AI',
     en='## 🔧 Dev engines — choose AI tool',
     de='## 🔧 Entwicklungs-Engines — AI-Tool wählen',
     fr='## 🔧 Moteurs de développement — choisir l\'outil IA',
     es='## 🔧 Motores de desarrollo — elegir herramienta IA',
     it='## 🔧 Motori di sviluppo — scegli strumento AI',
     pt='## 🔧 Motores de desenvolvimento — escolher ferramenta IA',
     cs='## 🔧 Vývojové motory — vyberte AI nástroj',
     ro='## 🔧 Motoare de dezvoltare — alegeți instrumentul AI',
     nl='## 🔧 Ontwikkelingsengines — kies AI-tool')
_add('detecting_engines',
     pl='🔍 Wykrywam dostępne silniki...', en='🔍 Detecting available engines...', de='🔍 Erkennung verfügbarer Engines...', fr='🔍 Détection des moteurs disponibles...',
     es='🔍 Detectando motores disponibles...', it='🔍 Rilevamento motori disponibili...', pt='🔍 Detetando motores disponíveis...', cs='🔍 Detekuji dostupné motory...',
     ro='🔍 Detectare motoare disponibile...', nl='🔍 Beschikbare engines detecteren...')
_add('testing_engines',
     pl='🧪 Testuję silniki...', en='🧪 Testing engines...', de='🧪 Teste Engines...', fr='🧪 Test des moteurs...',
     es='🧪 Probando motores...', it='🧪 Test dei motori...', pt='🧪 A testar motores...', cs='🧪 Testuji motory...',
     ro='🧪 Testare motoare...', nl='🧪 Engines testen...')
_add('engine_set',
     pl='✅ **Silnik ustawiony:** `{name}`\n\nPipeline będzie używał tego silnika do implementacji.',
     en='✅ **Engine set:** `{name}`\n\nPipeline will use this engine for implementation.',
     de='✅ **Engine gesetzt:** `{name}`\n\nDie Pipeline wird diese Engine zur Implementierung verwenden.',
     fr='✅ **Moteur défini :** `{name}`\n\nLe pipeline utilisera ce moteur pour l\'implémentation.',
     es='✅ **Motor configurado:** `{name}`\n\nEl pipeline usará este motor para la implementación.',
     it='✅ **Motore impostato:** `{name}`\n\nLa pipeline userà questo motore per l\'implementazione.',
     pt='✅ **Motor definido:** `{name}`\n\nO pipeline usará este motor para implementação.',
     cs='✅ **Motor nastaven:** `{name}`\n\nPipeline bude tento motor používat k implementaci.',
     ro='✅ **Motor setat:** `{name}`\n\nPipeline-ul va folosi acest motor pentru implementare.',
     nl='✅ **Engine ingesteld:** `{name}`\n\nDe pipeline zal deze engine gebruiken voor implementatie.')
_add('no_engine_works',
     pl='❌ **Żaden silnik nie działa.**', en='❌ **No engine works.**', de='❌ **Keine Engine funktioniert.**', fr='❌ **Aucun moteur ne fonctionne.**',
     es='❌ **Ningún motor funciona.**', it='❌ **Nessun motore funziona.**', pt='❌ **Nenhum motor funciona.**', cs='❌ **Žádný motor nefunguje.**',
     ro='❌ **Niciun motor nu funcționează.**', nl='❌ **Geen engine werkt.**')
_add('change_engine',
     pl='🔧 Zmień silnik', en='🔧 Change engine', de='🔧 Engine ändern', fr='🔧 Changer de moteur',
     es='🔧 Cambiar motor', it='🔧 Cambia motore', pt='🔧 Mudar motor', cs='🔧 Změnit motor',
     ro='🔧 Schimbă motorul', nl='🔧 Engine wijzigen')

# ── Manager / Review ─────────────────────────────────────────────────────────
_add('manager_panel',
     pl='## 📋 Panel Managera — Przegląd Ticketów',
     en='## 📋 Manager Panel — Ticket Review',
     de='## 📋 Manager-Panel — Ticket-Überprüfung',
     fr='## 📋 Panneau Manager — Revue des tickets',
     es='## 📋 Panel de Manager — Revisión de Tickets',
     it='## 📋 Pannello Manager — Revisione Ticket',
     pt='## 📋 Painel do Gestor — Revisão de Tickets',
     cs='## 📋 Panel Managera — Přehled Ticketů',
     ro='## 📋 Panou Manager — Revizuire Tickete',
     nl='## 📋 Managerpaneel — Ticketoverzicht')
_add('for_review',
     pl='**Do review:** {review} | **W trakcie:** {progress} | **Otwarte:** {open} | **Zakończone:** {done}',
     en='**To review:** {review} | **In progress:** {progress} | **Open:** {open} | **Done:** {done}',
     de='**Zum Review:** {review} | **In Bearbeitung:** {progress} | **Offen:** {open} | **Erledigt:** {done}',
     fr='**À revoir :** {review} | **En cours :** {progress} | **Ouverts :** {open} | **Terminés :** {done}',
     es='**Para revisión:** {review} | **En progreso:** {progress} | **Abiertos:** {open} | **Terminados:** {done}',
     it='**Da revisionare:** {review} | **In corso:** {progress} | **Aperti:** {open} | **Completati:** {done}',
     pt='**Para revisão:** {review} | **Em progresso:** {progress} | **Abertos:** {open} | **Concluídos:** {done}',
     cs='**K revizi:** {review} | **Probíhající:** {progress} | **Otevřené:** {open} | **Dokončené:** {done}',
     ro='**De revizuit:** {review} | **În progres:** {progress} | **Deschise:** {open} | **Finalizate:** {done}',
     nl='**Te reviewen:** {review} | **In uitvoering:** {progress} | **Open:** {open} | **Afgerond:** {done}')
_add('waiting_review',
     pl='### 👁️ Czekają na review', en='### 👁️ Awaiting review', de='### 👁️ Warten auf Review', fr='### 👁️ En attente de revue',
     es='### 👁️ Esperando revisión', it='### 👁️ In attesa di revisione', pt='### 👁️ Aguardando revisão', cs='### 👁️ Čekají na revizi',
     ro='### 👁️ Așteaptă review', nl='### 👁️ Wacht op review')
_add('in_progress_title',
     pl='### 🔄 W trakcie pracy', en='### 🔄 In progress', de='### 🔄 In Bearbeitung', fr='### 🔄 En cours',
     es='### 🔄 En progreso', it='### 🔄 In corso', pt='### 🔄 Em progresso', cs='### 🔄 Probíhající',
     ro='### 🔄 În progres', nl='### 🔄 In uitvoering')
_add('open_ready',
     pl='### ○ Otwarte (gotowe do przydzielenia)', en='### ○ Open (ready to assign)', de='### ○ Offen (bereit zur Zuweisung)',
     fr='### ○ Ouverts (prêts à être assignés)', es='### ○ Abiertos (listos para asignar)',
     it='### ○ Aperti (pronti per l\'assegnazione)', pt='### ○ Abertos (prontos para atribuição)',
     cs='### ○ Otevřené (připravené k přiřazení)', ro='### ○ Deschise (pregătite pentru atribuire)', nl='### ○ Open (klaar om toe te wijzen)')
_add('suggest_features',
     pl='🤖 AI: zaproponuj features', en='🤖 AI: suggest features', de='🤖 AI: Features vorschlagen', fr='🤖 IA : suggérer des features',
     es='🤖 IA: sugerir features', it='🤖 AI: suggerisci features', pt='🤖 IA: sugerir features', cs='🤖 AI: navrhnout features',
     ro='🤖 AI: sugerează features', nl='🤖 AI: features voorstellen')
_add('ticket_approved',
     pl='## ✅ Ticket `{tid}` zatwierdzony', en='## ✅ Ticket `{tid}` approved', de='## ✅ Ticket `{tid}` genehmigt', fr='## ✅ Ticket `{tid}` approuvé',
     es='## ✅ Ticket `{tid}` aprobado', it='## ✅ Ticket `{tid}` approvato', pt='## ✅ Ticket `{tid}` aprovado', cs='## ✅ Ticket `{tid}` schválen',
     ro='## ✅ Ticketul `{tid}` aprobat', nl='## ✅ Ticket `{tid}` goedgekeurd')
_add('ticket_rejected',
     pl='## 🔄 Ticket `{tid}` odrzucony → in_progress', en='## 🔄 Ticket `{tid}` rejected → in_progress', de='## 🔄 Ticket `{tid}` abgelehnt → in_progress',
     fr='## 🔄 Ticket `{tid}` rejeté → in_progress', es='## 🔄 Ticket `{tid}` rechazado → in_progress',
     it='## 🔄 Ticket `{tid}` rifiutato → in_progress', pt='## 🔄 Ticket `{tid}` rejeitado → in_progress',
     cs='## 🔄 Ticket `{tid}` zamítnut → in_progress', ro='## 🔄 Ticketul `{tid}` respins → in_progress', nl='## 🔄 Ticket `{tid}` afgewezen → in_progress')

# ── Preflight ────────────────────────────────────────────────────────────────
_add('missing_vars_title',
     pl='## ⚠️ Brakujące zmienne', en='## ⚠️ Missing variables', de='## ⚠️ Fehlende Variablen', fr='## ⚠️ Variables manquantes',
     es='## ⚠️ Variables faltantes', it='## ⚠️ Variabili mancanti', pt='## ⚠️ Variáveis em falta', cs='## ⚠️ Chybějící proměnné',
     ro='## ⚠️ Variabile lipsă', nl='## ⚠️ Ontbrekende variabelen')
_add('full_settings',
     pl='⚙️ Pełne ustawienia', en='⚙️ Full settings', de='⚙️ Alle Einstellungen', fr='⚙️ Paramètres complets',
     es='⚙️ Ajustes completos', it='⚙️ Impostazioni complete', pt='⚙️ Definições completas', cs='⚙️ Plná nastavení',
     ro='⚙️ Setări complete', nl='⚙️ Volledige instellingen')

# ── Validate ─────────────────────────────────────────────────────────────────
_add('no_key',
     pl='brak klucza', en='no key', de='kein Schlüssel', fr='pas de clé',
     es='sin clave', it='nessuna chiave', pt='sem chave', cs='žádný klíč',
     ro='fără cheie', nl='geen sleutel')
_add('llm_module_unavailable',
     pl='moduł LLM niedostępny', en='LLM module unavailable', de='LLM-Modul nicht verfügbar', fr='module LLM indisponible',
     es='módulo LLM no disponible', it='modulo LLM non disponibile', pt='módulo LLM indisponível', cs='modul LLM nedostupný',
     ro='modul LLM indisponibil', nl='LLM-module niet beschikbaar')
_add('connection_ok_short',
     pl='połączenie OK', en='connection OK', de='Verbindung OK', fr='connexion OK',
     es='conexión OK', it='connessione OK', pt='ligação OK', cs='spojení OK',
     ro='conexiune OK', nl='verbinding OK')
_add('invalid_key_401',
     pl='nieprawidłowy klucz API (401 Unauthorized)', en='invalid API key (401 Unauthorized)', de='ungültiger API-Schlüssel (401 Unauthorized)',
     fr='clé API invalide (401 Unauthorized)', es='clave API inválida (401 Unauthorized)',
     it='chiave API non valida (401 Unauthorized)', pt='chave API inválida (401 Unauthorized)',
     cs='neplatný API klíč (401 Unauthorized)', ro='cheie API invalidă (401 Unauthorized)', nl='ongeldige API-sleutel (401 Unauthorized)')
_add('no_funds_402',
     pl='brak środków na koncie OpenRouter (402)', en='no funds on OpenRouter account (402)', de='kein Guthaben auf OpenRouter-Konto (402)',
     fr='pas de fonds sur le compte OpenRouter (402)', es='sin fondos en la cuenta OpenRouter (402)',
     it='nessun fondo sull\'account OpenRouter (402)', pt='sem fundos na conta OpenRouter (402)',
     cs='žádné prostředky na účtu OpenRouter (402)', ro='fără fonduri pe contul OpenRouter (402)', nl='geen tegoed op OpenRouter-account (402)')
_add('docker_not_installed',
     pl='Docker nie jest zainstalowany', en='Docker is not installed', de='Docker ist nicht installiert', fr='Docker n\'est pas installé',
     es='Docker no está instalado', it='Docker non è installato', pt='Docker não está instalado', cs='Docker není nainstalován',
     ro='Docker nu este instalat', nl='Docker is niet geïnstalleerd')
_add('docker_not_running',
     pl='Docker daemon nie działa — uruchom Docker Desktop lub `sudo systemctl start docker`',
     en='Docker daemon not running — start Docker Desktop or `sudo systemctl start docker`',
     de='Docker-Daemon läuft nicht — starten Sie Docker Desktop oder `sudo systemctl start docker`',
     fr='Docker daemon ne fonctionne pas — démarrez Docker Desktop ou `sudo systemctl start docker`',
     es='Docker daemon no está ejecutándose — inicie Docker Desktop o `sudo systemctl start docker`',
     it='Docker daemon non in esecuzione — avvia Docker Desktop o `sudo systemctl start docker`',
     pt='Docker daemon não está a correr — inicie Docker Desktop ou `sudo systemctl start docker`',
     cs='Docker daemon neběží — spusťte Docker Desktop nebo `sudo systemctl start docker`',
     ro='Docker daemon nu rulează — porniți Docker Desktop sau `sudo systemctl start docker`',
     nl='Docker daemon draait niet — start Docker Desktop of `sudo systemctl start docker`')
_add('docker_timeout',
     pl='Docker nie odpowiada (timeout)', en='Docker not responding (timeout)', de='Docker antwortet nicht (Timeout)',
     fr='Docker ne répond pas (timeout)', es='Docker no responde (timeout)',
     it='Docker non risponde (timeout)', pt='Docker não responde (timeout)',
     cs='Docker neodpovídá (timeout)', ro='Docker nu răspunde (timeout)', nl='Docker reageert niet (timeout)')

# ── Misc CLI ─────────────────────────────────────────────────────────────────
_add('available_commands',
     pl='Dostępne komendy:', en='Available commands:', de='Verfügbare Befehle:', fr='Commandes disponibles :',
     es='Comandos disponibles:', it='Comandi disponibili:', pt='Comandos disponíveis:', cs='Dostupné příkazy:',
     ro='Comenzi disponibile:', nl='Beschikbare commando\'s:')
_add('type_manually',
     pl='✏️ Wpisz ręcznie…', en='✏️ Type manually…', de='✏️ Manuell eingeben…', fr='✏️ Saisir manuellement…',
     es='✏️ Escribir manualmente…', it='✏️ Digita manualmente…', pt='✏️ Digitar manualmente…', cs='✏️ Zadat ručně…',
     ro='✏️ Introduceți manual…', nl='✏️ Handmatig invoeren…')
_add('select_param',
     pl='— wybierz {param} —', en='— select {param} —', de='— {param} auswählen —', fr='— choisir {param} —',
     es='— seleccionar {param} —', it='— seleziona {param} —', pt='— selecionar {param} —', cs='— vyberte {param} —',
     ro='— selectați {param} —', nl='— {param} selecteren —')
_add('loading',
     pl='⏳ Ładowanie…', en='⏳ Loading…', de='⏳ Laden…', fr='⏳ Chargement…',
     es='⏳ Cargando…', it='⏳ Caricamento…', pt='⏳ A carregar…', cs='⏳ Načítání…',
     ro='⏳ Se încarcă…', nl='⏳ Laden…')
_add('detect_auto',
     pl='Wykryj automatycznie', en='Auto-detect', de='Automatisch erkennen', fr='Détecter automatiquement',
     es='Detectar automáticamente', it='Rileva automaticamente', pt='Detetar automaticamente', cs='Detekovat automaticky',
     ro='Detectare automată', nl='Automatisch detecteren')
_add('show_hide',
     pl='Pokaż/ukryj', en='Show/hide', de='Anzeigen/Verbergen', fr='Afficher/masquer',
     es='Mostrar/ocultar', it='Mostra/nascondi', pt='Mostrar/ocultar', cs='Zobrazit/skrýt',
     ro='Afișare/ascundere', nl='Tonen/verbergen')
_add('get_api_key',
     pl='Pobierz API key →', en='Get API key →', de='API-Schlüssel holen →', fr='Obtenir la clé API →',
     es='Obtener clave API →', it='Ottieni chiave API →', pt='Obter chave API →', cs='Získat API klíč →',
     ro='Obțineți cheia API →', nl='API-sleutel ophalen →')
_add('requires_terminal',
     pl='Wymaga terminala SSH', en='Requires SSH terminal', de='Erfordert SSH-Terminal', fr='Nécessite un terminal SSH',
     es='Requiere terminal SSH', it='Richiede terminale SSH', pt='Requer terminal SSH', cs='Vyžaduje SSH terminál',
     ro='Necesită terminal SSH', nl='Vereist SSH-terminal')
_add('open_api_portal',
     pl='Otwórz portal klucza API', en='Open API key portal', de='API-Schlüssel-Portal öffnen', fr='Ouvrir le portail de clé API',
     es='Abrir portal de clave API', it='Apri portale chiave API', pt='Abrir portal de chave API', cs='Otevřít portál API klíče',
     ro='Deschideți portalul cheii API', nl='API-sleutelportaal openen')
_add('fix_it',
     pl='🔧 Napraw to', en='🔧 Fix it', de='🔧 Reparieren', fr='🔧 Réparer',
     es='🔧 Reparar', it='🔧 Ripara', pt='🔧 Corrigir', cs='🔧 Opravit',
     ro='🔧 Repară', nl='🔧 Repareren')
