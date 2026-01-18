import os
import ast

ROOT = r"D:\DATA_LLM\dev\lifepim-desktop\src"
EXCLUDE_DIRS = {".venv", "__pycache__", ".git", "node_modules"}

def walk_tree(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        rel = os.path.relpath(dirpath, root)
        indent = "  " * (rel.count(os.sep))
        print(f"{indent}{os.path.basename(dirpath)}/")

        for fn in sorted(filenames):
            if fn.endswith(".py"):
                print(f"{indent}  {fn}")
                dump_symbols(os.path.join(dirpath, fn), indent + "    ")

def dump_symbols(path, indent):
    try:
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
    except Exception as e:
        print(f"{indent}# parse error: {e}")
        return

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            sig = f"{node.name}({', '.join(a.arg for a in node.args.args)})"
            doc = ast.get_docstring(node)
            docline = doc.splitlines()[0] if doc else ""
            print(f"{indent}def {sig}  # {docline}")
        elif isinstance(node, ast.ClassDef):
            print(f"{indent}class {node.name}:")
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    sig = f"{item.name}({', '.join(a.arg for a in item.args.args)})"
                    doc = ast.get_docstring(item)
                    docline = doc.splitlines()[0] if doc else ""
                    print(f"{indent}  def {sig}  # {docline}")

if __name__ == "__main__":
    walk_tree(ROOT)
