# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'palmettobug'
copyright = '2024, Medical University of South Carolina'
author = 'Ben Caiello'
release = '0.1.0'


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx_rtd_theme',
'sphinx.ext.napoleon',
'autoapi.extension',
'nbsphinx'
]
autoapi_dirs = ['../../palmettobug']
autoapi_ignore = ['*_vendor*', 
                'Assets', 
                '*widget*', 
                '*Widget*', 
                '*_GUI*', 
                '*app_and_entry*',
                '*Exception*',
                '*ANOVA*', 
                '*migrations*']   ## *migrations* is the default in autoapi_ignore, so I leave it in here


templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
