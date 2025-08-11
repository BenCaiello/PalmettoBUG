
project = 'palmettobug'
copyright = '2024-2025, Medical University of South Carolina'
author = 'Ben Caiello'
release = '0.2.7'


extensions = ['sphinx_rtd_theme',
# 'sphinx.ext.napoleon',
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


html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
