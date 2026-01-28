import json
import os

class ProjectManager:
    @staticmethod
    def save_project(path, state):
        """
        Saves the current application state to a JSON file.
        
        Args:
            path (str): File path to save to (.pcp).
            state (dict): Dictionary containing app state.
        """
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving project: {e}")
            return False

    @staticmethod
    def load_project(path):
        """
        Loads application state from a JSON file.
        
        Args:
            path (str): File path to load from.
            
        Returns:
            dict or None: The loaded state dictionary, or None if failed.
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading project: {e}")
            return None
