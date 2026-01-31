import json
import os
import random
import math
import builtins
import torch
import numpy as np
from abc import ABC, abstractmethod
from PIL import Image, ImageDraw, ImageFont

class BasePlugin(ABC):
    """
    Abstract Base Class for all Pixlato plugins.
    """
    def __init__(self, metadata):
        self.metadata = metadata
        self.enabled = True

    @abstractmethod
    def run(self, image: Image.Image, params: dict) -> Image.Image:
        """
        Main execution point for the plugin.
        """
        pass

class PluginEngine:
    """
    Handles discovery, sandboxing, and execution of plugins.
    """
    def __init__(self, plugins_dir):
        self.plugins_dir = plugins_dir
        self.plugins = {}
        self.hooks = {
            "PRE_PROCESS": [],
            "PRE_DOWNSAMPLE": [],
            "POST_DOWNSAMPLE": [],
            "POST_PALETTE": [],
            "FINAL_IMAGE": [],
            "UI_PRE_RENDER": [],
            "UI_POST_RENDER": []
        }

    def discover_plugins(self):
        if not os.path.exists(self.plugins_dir):
            return

        for folder in os.listdir(self.plugins_dir):
            path = os.path.join(self.plugins_dir, folder)
            if os.path.isdir(path):
                meta_path = os.path.join(path, "plugin.json")
                script_path = os.path.join(path, "main.py")
                if os.path.exists(meta_path) and os.path.exists(script_path):
                    self._load_plugin(path, meta_path, script_path)

    def _load_plugin(self, folder_path, meta_path, script_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            
            plugin_id = meta.get("id")
            if not plugin_id: return

            with open(script_path, "r", encoding="utf-8") as f:
                code = f.read()

            # --- Hardened Sandbox Policy ---
            # 1. Start with a safe subset of builtins
            safe_builtins = {}
            allowed_builtins = [
                'print', 'range', 'len', 'int', 'float', 'str', 'list', 'dict', 'tuple', 
                'abs', 'min', 'max', 'sum', 'isinstance', 'getattr', 'setattr', 'hasattr',
                'Exception', 'ValueError', 'TypeError', 'bool', 'any', 'all', 'enumerate',
                'zip', 'sorted', 'reversed', '__build_class__', '__import__'
            ]
            for b in allowed_builtins:
                if hasattr(builtins, b):
                    safe_builtins[b] = getattr(builtins, b)

            # 2. Define plugin-level globals
            safe_globals = {
                "__builtins__": safe_builtins,
                "__name__": f"plugins.{plugin_id}",
                "__file__": script_path,
                "BasePlugin": BasePlugin,
                "Image": Image,
                "ImageDraw": ImageDraw,
                "ImageFont": ImageFont,
                "random": random,
                "math": math,
                "torch": torch,
                "np": np
            }
            
            # Execute script to define the plugin class
            local_vars = {}
            exec(code, safe_globals, local_vars)
            
            plugin_class = None
            for item in local_vars.values():
                if isinstance(item, type) and issubclass(item, BasePlugin) and item is not BasePlugin:
                    plugin_class = item
                    break
            
            if not plugin_class:
                print(f"No valid BasePlugin class found in {script_path}")
                return

            self.plugins[plugin_id] = {
                "metadata": meta,
                "class": plugin_class,
                "instance": plugin_class(meta),
                "enabled": False
            }
            
            for hook in meta.get("hooks", []):
                if hook in self.hooks:
                    self.hooks[hook].append(plugin_id)
                    
            print(f"Plugin loaded: {meta.get('name')} ({plugin_id})")
        except Exception as e:
            print(f"Failed to load plugin from {folder_path}: {e}")

    def execute_hook(self, hook_name, image, params):
        if hook_name not in self.hooks:
            return image

        current_image = image
        for plugin_id in self.hooks[hook_name]:
            plugin_data = self.plugins.get(plugin_id)
            if plugin_data and plugin_data["enabled"]:
                try:
                    current_image = plugin_data["instance"].run(current_image, params)
                except Exception as e:
                    print(f"Plugin {plugin_id} failed during {hook_name}: {e}")
            
        return current_image