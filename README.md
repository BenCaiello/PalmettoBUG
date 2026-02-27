# PalmettoBUG
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/BenCaiello/PalmettoBUG/python-app.yml)
![Codecov](https://img.shields.io/codecov/c/github/BenCaiello/PalmettoBUG)
![Pepy Total Downloads](https://img.shields.io/pepy/dt/palmettobug)
![PyPI - Version](https://img.shields.io/pypi/v/palmettobug)
![Read the Docs](https://img.shields.io/readthedocs/PalmettoBUG)
![Static Badge](https://img.shields.io/badge/License-GPL3-blue)

Badges made in: https://shields.io/

## NOTE: PalmettoBUG is not yet published and is still intended to be reviewed & tested further, be sensible if you use it and keep an eye out for bugs / errors! 

Also please raise an issue if you do encounter a bug, so that it can be fixed!

## What is this branch?

The plan is for this to be a test branch for porting some of the python code / python dependencies into Rust (particularly computationally expensive code, such as the ripley's statistics calculations which were themselves originally ported manually from R's spatstat package into python).

Unlike the rest of the code base, I will be attempting this as a "vibe-coder", using primarily AI to generate the rust files, etc. At least initially, anyway. 

The goal of this branch is:
1). speed up various calculations, using both a faster language (Rust), better optimized algorithms, and better paralellization
2). If possible, simplify the dependencies & installation of palmettobug by replacing some of its existing python dependencies with locally configured rust crates. 
3). Do not change any of the outputs of the existing palmettobug package, except: (a) numerical outputs within reasonable floating point rounding differences and (b) algorithms defined by random seeds can have wider variability. There may be more exceptions, but I want to be extremely cautious about replacing functional, generally understood code with AI-generated mystery code if the outputs are not effectively identical.

Top targets for performance optimization:
- ripley's stats (K / L / g) and spatial edt calculations
- pixel classification (both supervised & unsupervised methods)
- (esp. boolean) image mask manipulations
- FlowSOM / UMAP / Leiden calculations (speculative)

Top targets for dependency simplification:
- opencv (pixel classifier re-write)

## Plan

Setup and test Rust crates in this branch, then merge any Rust additions that are working well back into main. If making this package a hybrid Rust/Python package somehow over-complicates the installation (it shouldn't?) while still significantly improving performace, then I may release this branch as an alternative version of the package.