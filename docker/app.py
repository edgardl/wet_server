import importlib.util
import os
import subprocess
import sys
from flask import Flask, Response, jsonify, request

app = Flask(__name__)
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), 'scripts')

# Cache to store the modification timestamp of processed requirements.txt files
INSTALLED_REQUIREMENTS = {}


def ensure_dependencies(app_dir):
    """Checks for requirements.txt and installs missing packages if updated or uninstalled."""
    req_path = os.path.join(app_dir, 'requirements.txt')

    if not os.path.isfile(req_path):
        return

    # Check the file's last modified time
    current_mtime = os.path.getmtime(req_path)

    # If requirements.txt has not changed since last install, skip
    if INSTALLED_REQUIREMENTS.get(req_path) == current_mtime:
        return

    print(f"[Auto-Installer] Installing dependencies from {req_path}...")

    try:
        # Run pip install using the active Python executable
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "--no-cache-dir",
            "-r", req_path
        ])
        # Update cache with current modification time upon success
        INSTALLED_REQUIREMENTS[req_path] = current_mtime
        print(f"[Auto-Installer] Successfully installed requirements for {os.path.basename(app_dir)}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to install dependencies from requirements.txt: {e}")


@app.route('/<path:app_path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def execute_app(app_path):
    clean_path = app_path[:-3] if app_path.endswith('.py') else app_path
    target_path = os.path.abspath(os.path.join(SCRIPTS_DIR, clean_path))

    # Security check: Prevent path traversal
    if not target_path.startswith(os.path.abspath(SCRIPTS_DIR)):
        return jsonify({"error": "Unauthorized path access"}), 403

    # Resolve target script and module directory
    if os.path.isdir(target_path):
        script_path = os.path.join(target_path, "main.py")
        module_dir = target_path
    elif os.path.isfile(f"{target_path}.py"):
        script_path = f"{target_path}.py"
        module_dir = os.path.dirname(script_path)
    elif os.path.isfile(target_path):
        script_path = target_path
        module_dir = os.path.dirname(script_path)
    else:
        return jsonify({"error": f"App or script '{app_path}' not found"}), 404

    if not os.path.isfile(script_path):
        return jsonify({"error": f"Entrypoint 'main.py' not found in '{clean_path}'"}), 404

    try:
        # 1. Automatically install any requirements before running the module
        ensure_dependencies(module_dir)

        # 2. Add module directory to sys.path for relative imports
        if module_dir not in sys.path:
            sys.path.insert(0, module_dir)

        # 3. Dynamic import with module cache invalidation for hot-reloading
        module_name = f"dynamic_app_{clean_path.replace('/', '_')}"
        if module_name in sys.modules:
            del sys.modules[module_name]

        spec = importlib.util.spec_from_file_location(module_name, script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        if not hasattr(module, 'run'):
            return jsonify(
                {"error": f"Script '{os.path.basename(script_path)}' must define a 'run(request)' function."}), 400

        # 4. Execute script runner
        result = module.run(request)

        # FIX: Allow raw Flask Response returns (HTML pages, media streams, custom headers)
        if isinstance(result, Response):
            return result

        # Default: Wrap dictionary/list results in JSON
        return jsonify({"status": "success", "data": result})

    except Exception as e:
        return jsonify({"error": "App execution failed", "details": str(e)}), 500


if __name__ == '__main__':
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    app.run(host='0.0.0.0', port=9999)
