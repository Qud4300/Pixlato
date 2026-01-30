import json
import os
import weakref

class LocaleManager:
    def __init__(self, assets_dir, default_lang="ko"):
        self.lang_dir = os.path.join(assets_dir, "lang")
        self.current_lang = default_lang
        self.translations = {}
        self._registered_widgets = [] # List of (weakref(widget), key, prefix, suffix)
        self.load_language(default_lang)

    def load_language(self, lang_code):
        file_path = os.path.join(self.lang_dir, f"{lang_code}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.translations = json.load(f)
                self.current_lang = lang_code
                self.refresh_widgets()
                return True
            except Exception as e:
                print(f"Failed to load language {lang_code}: {e}")
        return False

    def get(self, key, default=None):
        return self.translations.get(key, default if default is not None else key)

    def register(self, widget, key, prefix="", suffix=""):
        """Registers a widget to be automatically updated when language changes."""
        # Use weakref to prevent memory leaks when widgets are destroyed
        self._registered_widgets.append((weakref.ref(widget), key, prefix, suffix))
        # Initial set
        self._update_widget(widget, key, prefix, suffix)

    def _update_widget(self, widget, key, prefix, suffix):
        try:
            translated = self.get(key)
            full_text = f"{prefix}{translated}{suffix}"
            if hasattr(widget, "configure"):
                widget.configure(text=full_text)
        except Exception:
            pass

    def refresh_widgets(self):
        """Updates text for all alive registered widgets."""
        still_alive = []
        for ref, key, prefix, suffix in self._registered_widgets:
            widget = ref()
            if widget is not None:
                try:
                    # Check if widget still exists in tkinter sense
                    if widget.winfo_exists():
                        self._update_widget(widget, key, prefix, suffix)
                        still_alive.append((ref, key, prefix, suffix))
                except Exception:
                    pass
        self._registered_widgets = still_alive

    def get_available_languages(self):
        langs = []
        if os.path.exists(self.lang_dir):
            for f in os.listdir(self.lang_dir):
                if f.endswith(".json"):
                    langs.append(f.replace(".json", ""))
        return langs