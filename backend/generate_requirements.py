import os
import ast
import pkg_resources

PROJECT_DIR = "."   
found_imports = set()

def scan_file(path):
    # Purpose: Parse a Python file and collect top-level imported package names.
    # Inputs:
    # - path (str): Path to a Python source file.
    # Outputs:
    # - None: Updates the global found_imports set.
    try:
        with open(path, "r", encoding="utf-8") as f:
            node = ast.parse(f.read(), path)
    except Exception:
        return

    for child in ast.walk(node):
        if isinstance(child, ast.Import):
            for alias in child.names:
                found_imports.add(alias.name.split(".")[0])
        elif isinstance(child, ast.ImportFrom):
            if child.module:
                found_imports.add(child.module.split(".")[0])

def scan_dir(root):
    # Purpose: Recursively scan a directory for Python files to extract imports.
    # Inputs:
    # - root (str): Root directory path to scan.
    # Outputs:
    # - None: Updates the global found_imports set via scan_file.
    for base, dirs, files in os.walk(root):
        for file in files:
            if file.endswith(".py"):
                scan_file(os.path.join(base, file))

if __name__ == "__main__":
    # Purpose: Map detected imports to installed package versions and write a requirements file.
    # Inputs:
    # - found_imports (set[str]): Collected top-level import names from project files.
    # - installed (dict[str, str]): Installed package name -> version mapping.
    # Outputs:
    # - requirements_from_code.txt (file): Sorted, pinned requirements written to disk.
    scan_dir(PROJECT_DIR)
    installed = {dist.project_name.lower(): dist.version for dist in pkg_resources.working_set}

    requirements = []
    for pkg in found_imports:
        if pkg.lower() in installed:
            requirements.append(f"{pkg}=={installed[pkg.lower()]}")

    requirements_path = "requirements_from_code.txt"
    with open(requirements_path, "w") as f:
        f.write("\n".join(sorted(requirements)))

    print(f"Generated {requirements_path} with:")
    print("\n".join(sorted(requirements)))
