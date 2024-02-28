import os
import folder_paths

comfy_path = os.path.dirname(folder_paths.__file__)
js_path = os.path.join(comfy_path, "web", "extensions")
custom_nodes_path = os.path.join(comfy_path, 'custom_nodes')
git_script_path = os.path.join(os.path.dirname(__file__), "git_helper.py")
comfyui_manager_path = os.path.dirname(__file__)
startup_script_path = os.path.join(comfyui_manager_path, "startup-scripts")
