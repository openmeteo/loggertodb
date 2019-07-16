import os
import re
import sys

sys.path.insert(0, os.path.abspath(".."))


def get_version():
    scriptdir = os.path.dirname(os.path.abspath(__file__))
    init_py_path = os.path.join(scriptdir, "loggertodb", "__init__.py")
    with open(init_py_path) as f:
        return re.search(r'^__version__ = "(.*?)"$', f.read(), re.MULTILINE).group(1)


extensions = ["sphinx.ext.autodoc", "sphinx.ext.viewcode"]
templates_path = ["_templates"]
source_suffix = ".rst"
master_doc = "index"
project = u"loggertodb"
copyright = u"2018, Antonis Christofides"
author = u"Antonis Christofides"
version = get_version()
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
        u"loggertodb Documentation",
        u"Antonis Christofides",
        "manual",
    )
]
man_pages = [(master_doc, "loggertodb", u"loggertodb Documentation", [author], 1)]
texinfo_documents = [
    (
        master_doc,
        "loggertodb",
        u"loggertodb Documentation",
        author,
        "loggertodb",
        "One line description of project.",
        "Miscellaneous",
    )
]
