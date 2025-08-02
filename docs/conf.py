from setuptools_scm import get_version

extensions = ["sphinx.ext.autodoc", "sphinx.ext.viewcode"]
templates_path = ["_templates"]
source_suffix = ".rst"
master_doc = "index"
project = "loggertodb"
copyright = "2004-2020 various entities"
author = "Antonis Christofides"
version = get_version(root="..")
release = version
language = None
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
pygments_style = "sphinx"
todo_include_todos = False
html_theme = "alabaster"
html_static_path = ["_static"]
htmlhelp_basename = "loggertodbdoc"
latex_elements = {}
latex_documents = [
    (
        master_doc,
        "loggertodb.tex",
        "loggertodb Documentation",
        "Antonis Christofides",
        "manual",
    )
]
man_pages = [(master_doc, "loggertodb", "loggertodb Documentation", [author], 1)]
texinfo_documents = [
    (
        master_doc,
        "loggertodb",
        "loggertodb Documentation",
        author,
        "loggertodb",
        "One line description of project.",
        "Miscellaneous",
    )
]
