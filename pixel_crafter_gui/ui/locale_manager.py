import json
import os

class LocaleManager:
    def __init__(self, assets_dir, default_lang="ko"):
        self.lang_dir = os.path.join(assets_dir, "lang")
        self.current_lang = default_lang
        self.translations = {}
        self.load_language(default_lang)

    def load_language(self, lang_code):
        file_path = os.path.join(self.lang_dir, f"{lang_code}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.translations = json.load(f)
                self.current_lang = lang_code
                return True
            except Exception as e:
                print(f"Failed to load language {lang_code}: {e}")
        return False

    def get(self, key, default=None):
        return self.translations.get(key, default if default is not None else key)

    def get_available_languages(self):
        langs = []
        if os.path.exists(self.lang_dir):
            for f in os.listdir(self.lang_dir):
                if f.endswith(".json"):
                    langs.append(f.replace(".json", ""))
        return langs
