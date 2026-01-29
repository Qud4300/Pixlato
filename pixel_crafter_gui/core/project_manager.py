import json
import os
import hashlib

class ProjectManager:
    @staticmethod
    def _calculate_hash(state_dict):
        """Calculates SHA-256 hash of the state dictionary (excluding signature)."""
        # Ensure consistent key ordering for stable hashing
        data = state_dict.copy()
        data.pop("__integrity_signature__", None)
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()

    @staticmethod
    def save_project(path, state):
        """
        Saves the current application state to a JSON file with an integrity signature.
        """
        try:
            # Add signature
            state["__integrity_signature__"] = None
            signature = ProjectManager._calculate_hash(state)
            state["__integrity_signature__"] = signature
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving project: {e}")
            return False

    @staticmethod
    def load_project(path):
        """
        Loads application state and verifies its integrity.
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            if "__integrity_signature__" not in state:
                print("Warning: Project file has no integrity signature.")
                return state # Allow loading but maybe warn user
                
            expected_sig = state["__integrity_signature__"]
            actual_sig = ProjectManager._calculate_hash(state)
            
            if expected_sig != actual_sig:
                print("Security Error: Project file integrity check failed (Tampering detected).")
                return None
                
            return state
        except Exception as e:
            print(f"Error loading project: {e}")
            return None
